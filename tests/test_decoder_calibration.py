"""Validation-only confidence calibration tests for the neural decoder."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nixlms_core import CoreConfig, NixLMsNeuralCore
from nixlms_core.utils import save_json


class DecoderCalibrationTests(unittest.TestCase):
    def _add_cases(self, ai):
        rows = [
            ("pergunta alfa", "A água reflete a luz."),
            ("pergunta beta", "A água refrata a luz."),
            ("pergunta gama", "O sol está quente."),
            ("pergunta delta", "Gato dorme."),
        ]
        for question, answer in rows:
            ai.learning.dataset.add(question, answer, "validation")
        return rows

    def _outputs(self):
        return iter([
            {"text": "A água reflete a luz.", "tokens": ["a", "água", "reflete", "a", "luz"],
             "token_count": 5, "confidence": 0.90, "terminated": True, "reason": None},
            {"text": "A água refrata a luz.", "tokens": ["a", "água", "refrata", "a", "luz"],
             "token_count": 5, "confidence": 0.80, "terminated": True, "reason": None},
            {"text": "A água reflete a luz.", "tokens": ["a", "água", "reflete", "a", "luz"],
             "token_count": 5, "confidence": 0.70, "terminated": True, "reason": None},
            {"text": "A água reflete a luz.", "tokens": ["a", "água", "reflete", "a", "luz"],
             "token_count": 5, "confidence": 0.20, "terminated": True, "reason": None},
        ])

    def _prepare_trained(self, ai):
        ai.network.output_updates = 10
        ai.decoder.trained_steps = 10
        ai.decoder.trained_tokens = 50
        save_json(ai.data_dir / "neural_weights.json", ai.network.state_dict())
        ai._save_decoder()
        ai._save_encoder()

    def test_calibration_selects_threshold_from_validation_f1(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            rows = self._add_cases(ai)
            self._prepare_trained(ai)
            before = ai.decoder.state_dict()
            outputs = self._outputs()

            with patch.object(ai.decoder, "generate", side_effect=lambda *_a, **_k: next(outputs)):
                report = ai.learning.calibrate_decoder_confidence(
                    min_validation_samples=4,
                    min_correct=2,
                    min_incorrect=2,
                    min_token_f1=0.65,
                )

            self.assertTrue(report["calibrated"])
            self.assertAlmostEqual(report["threshold"], 0.80)
            self.assertEqual(report["validation_samples"], len(rows))
            self.assertEqual(report["metrics"]["positive_generations"], 2)
            self.assertEqual(report["metrics"]["negative_generations"], 2)
            self.assertAlmostEqual(ai.config.decoder_min_confidence, 0.80)
            self.assertEqual(ai.decoder.state_dict(), before)
            self.assertFalse(report["protocol"]["test_split_used"])

    def test_calibration_refuses_insufficient_positive_negative_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            self._add_cases(ai)
            self._prepare_trained(ai)
            outputs = iter([
                {"text": "A água reflete a luz.", "tokens": ["a", "água", "reflete", "a", "luz"],
                 "token_count": 5, "confidence": 0.9},
                {"text": "A água reflete a luz.", "tokens": ["a", "água", "reflete", "a", "luz"],
                 "token_count": 5, "confidence": 0.8},
                {"text": "A água reflete a luz.", "tokens": ["a", "água", "reflete", "a", "luz"],
                 "token_count": 5, "confidence": 0.7},
                {"text": "A água reflete a luz.", "tokens": ["a", "água", "reflete", "a", "luz"],
                 "token_count": 5, "confidence": 0.6},
            ])
            with patch.object(ai.decoder, "generate", side_effect=lambda *_a, **_k: next(outputs)):
                report = ai.learning.calibrate_decoder_confidence(
                    min_validation_samples=4, min_correct=2, min_incorrect=2, min_token_f1=0.90
                )

            self.assertFalse(report["calibrated"])
            self.assertEqual(report["reason"], "insufficient_generation_class_balance")
            self.assertFalse(ai.decoder_calibration_path.exists())
            self.assertAlmostEqual(ai.config.decoder_min_confidence, 0.15)

    def test_calibration_persists_and_reloads_for_same_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            self._add_cases(ai)
            self._prepare_trained(ai)
            outputs = self._outputs()
            with patch.object(ai.decoder, "generate", side_effect=lambda *_a, **_k: next(outputs)):
                report = ai.learning.calibrate_decoder_confidence(
                    min_validation_samples=4, min_correct=2, min_incorrect=2,
                    min_token_f1=0.65,
                )
            self.assertTrue(report["calibrated"])

            restored = NixLMsNeuralCore(data_dir)

            self.assertAlmostEqual(restored.config.decoder_min_confidence, 0.80)
            self.assertTrue(restored.status()["decoder_calibration"]["loaded"])

    def test_validation_change_invalidates_saved_decoder_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            self._add_cases(ai)
            self._prepare_trained(ai)
            outputs = self._outputs()
            with patch.object(ai.decoder, "generate", side_effect=lambda *_a, **_k: next(outputs)):
                ai.learning.calibrate_decoder_confidence(
                    min_validation_samples=4, min_correct=2, min_incorrect=2,
                    min_token_f1=0.65,
                )
            self.assertAlmostEqual(ai.config.decoder_min_confidence, 0.80)

            ai.learning.dataset.add("nova pergunta", "nova resposta", "validation")
            ai.status()

            self.assertAlmostEqual(ai.config.decoder_min_confidence, 0.15)

    def test_training_invalidates_decoder_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            self._add_cases(ai)
            ai.learning.dataset.add("pergunta treino", "resposta treino", "train")
            self._prepare_trained(ai)
            outputs = self._outputs()
            with patch.object(ai.decoder, "generate", side_effect=lambda *_a, **_k: next(outputs)):
                report = ai.learning.calibrate_decoder_confidence(
                    min_validation_samples=4, min_correct=2, min_incorrect=2,
                    min_token_f1=0.65,
                )
            self.assertTrue(report["calibrated"])

            ai.learning.train(epochs=1)

            self.assertFalse(ai.decoder_calibration_path.exists())
            self.assertAlmostEqual(ai.config.decoder_min_confidence, 0.15)

    def test_explicit_decoder_confidence_overrides_saved_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            self._add_cases(ai)
            self._prepare_trained(ai)
            outputs = self._outputs()
            with patch.object(ai.decoder, "generate", side_effect=lambda *_a, **_k: next(outputs)):
                ai.learning.calibrate_decoder_confidence(
                    min_validation_samples=4, min_correct=2, min_incorrect=2,
                    min_token_f1=0.65,
                )

            restored = NixLMsNeuralCore(
                data_dir, config=CoreConfig(decoder_min_confidence=0.42)
            )

            self.assertAlmostEqual(restored.config.decoder_min_confidence, 0.42)

    def test_decoder_calibration_requires_trained_lif_and_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            self._add_cases(ai)

            report = ai.learning.calibrate_decoder_confidence()

            self.assertFalse(report["calibrated"])
            self.assertEqual(report["reason"], "decoder_or_lif_readout_untrained")


if __name__ == "__main__":
    unittest.main()
