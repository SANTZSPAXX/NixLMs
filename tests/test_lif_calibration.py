"""Tests for validation-split LIF readout calibration."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nixlms_core import NixLMsNeuralCore
from nixlms_core.learning import DatasetStore
from nixlms_core.utils import save_json


class LIFCalibrationTests(unittest.TestCase):
    def _add_validation_cases(self, ai):
        rows = [
            ("val pergunta alfa", "Resposta Alfa."),
            ("val pergunta beta", "Resposta Beta."),
            ("val pergunta gama", "Resposta Gama."),
            ("val pergunta delta", "Resposta Delta."),
        ]
        for index, (question, answer) in enumerate(rows):
            ai.learning.dataset.add(question, answer, split="validation")
            ai.memory.remember(f"treino candidato {index}", answer)
        return rows

    def test_dataset_accepts_validation_split_and_reports_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DatasetStore(Path(tmp) / "dataset.json")
            store.add("pergunta de validação", "resposta", "validation")
            report = store.audit_splits()

            self.assertTrue(report["valid"])
            self.assertEqual(report["counts"]["qa_validation"], 1)

    def test_training_uses_train_only_and_keeps_validation_rows_out_of_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("pergunta de treino", "resposta de treino", "train")
            ai.learning.dataset.add("pergunta de validação", "resposta de validação", "validation")

            ai.learning.train(epochs=1)

            questions = {item["question"] for item in ai.memory.knowledge}
            self.assertIn("pergunta de treino", questions)
            self.assertNotIn("pergunta de validação", questions)

    def test_validation_and_test_texts_do_not_expand_training_vocabulary(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            ai.learning.dataset.add("trainvocabtoken alpha", "resposta de treino", "train")
            ai.learning.dataset.add("validationvocabtoken beta", "resposta de validação", "validation")
            ai.learning.dataset.add("testvocabtoken gamma", "resposta de teste", "test")

            restored = NixLMsNeuralCore(data_dir)

            self.assertIn("trainvocabtoken", restored.encoder.vocab)
            self.assertNotIn("validationvocabtoken", restored.encoder.vocab)
            self.assertNotIn("testvocabtoken", restored.encoder.vocab)

    def test_calibration_selects_threshold_from_validation_top_candidate_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            rows = self._add_validation_cases(ai)
            ai.learning.dataset.add("pergunta exclusiva de teste", "Resposta de teste.", split="test")
            ai.network.output_updates = 12
            outcomes = iter([
                (0.90, "Resposta Alfa."),
                (0.80, "Resposta Beta."),
                (0.85, "Resposta Incorreta."),
                (0.20, "Outra Resposta Incorreta."),
            ])

            def fake_respond(question, **_kwargs):
                score, answer = next(outcomes)
                ai.last_trace = {
                    "lif_top_candidate_score": score,
                    "lif_top_candidate_answer": answer,
                }
                return answer

            with patch.object(ai, "respond", side_effect=fake_respond):
                report = ai.learning.calibrate_lif_threshold()

            self.assertTrue(report["calibrated"])
            self.assertAlmostEqual(report["threshold"], 0.80)
            self.assertEqual(report["metrics"]["positive_top1"], 2)
            self.assertEqual(report["metrics"]["negative_top1"], 2)
            self.assertEqual(report["validation_samples"], 4)
            self.assertTrue((Path(tmp) / "lif_calibration.json").exists())
            self.assertEqual(ai.config.lif_retrieval_threshold, report["threshold"])

    def test_calibration_refuses_missing_or_insufficient_validation_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.network.output_updates = 10
            report = ai.learning.calibrate_lif_threshold()
            self.assertFalse(report["calibrated"])
            self.assertEqual(report["reason"], "validation_split_empty")
            self.assertEqual(ai.config.lif_retrieval_threshold, 0.45)

            ai.learning.dataset.add("uma pergunta", "uma resposta", "validation")
            report = ai.learning.calibrate_lif_threshold()
            self.assertFalse(report["calibrated"])
            self.assertEqual(report["reason"], "insufficient_validation_samples")

    def test_calibration_requires_a_trained_lif_readout(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            self._add_validation_cases(ai)
            report = ai.learning.calibrate_lif_threshold()
            self.assertFalse(report["calibrated"])
            self.assertEqual(report["reason"], "lif_readout_untrained")

    def test_calibration_does_not_change_neural_weights_or_record_episodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            self._add_validation_cases(ai)
            ai.network.output_updates = 12
            before_weights = ai.network.state_dict()
            before_episodes = list(ai.episodic.items)
            outcomes = iter([
                (0.90, "Resposta Alfa."),
                (0.80, "Resposta Beta."),
                (0.85, "Resposta Incorreta."),
                (0.20, "Outra Resposta Incorreta."),
            ])

            def fake_respond(_question, **_kwargs):
                score, answer = next(outcomes)
                ai.last_trace = {
                    "lif_top_candidate_score": score,
                    "lif_top_candidate_answer": answer,
                }
                return answer

            with patch.object(ai, "respond", side_effect=fake_respond):
                ai.learning.calibrate_lif_threshold()

            self.assertEqual(ai.network.state_dict(), before_weights)
            self.assertEqual(ai.episodic.items, before_episodes)

    def test_persisted_calibration_loads_only_for_matching_model_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            ai.network.output_updates = 12
            ai.encoder.updates = 7
            save_json(data_dir / "neural_weights.json", ai.network.state_dict())
            ai._save_encoder()
            save_json(data_dir / "lif_calibration.json", {
                "schema_version": 1,
                "threshold": 0.80,
                "readout_updates": 12,
                "encoder_updates": 7,
                "encoder_vocab_size": len(ai.encoder.vocab),
                "validation_fingerprint": ai.learning.validation_fingerprint(),
                "candidate_memory_fingerprint": ai.learning.lif_candidate_fingerprint(),
            })

            restored = NixLMsNeuralCore(data_dir)
            self.assertEqual(restored.network.output_updates, 12)
            self.assertEqual(restored.encoder.updates, 7)
            self.assertEqual(len(restored.encoder.vocab), len(ai.encoder.vocab))
            self.assertEqual(
                restored.learning.validation_fingerprint(),
                ai.learning.validation_fingerprint(),
            )
            self.assertEqual(
                restored.learning.lif_candidate_fingerprint(),
                ai.learning.lif_candidate_fingerprint(),
            )
            self.assertAlmostEqual(restored.config.lif_retrieval_threshold, 0.80)

            restored.network.output_updates = 13
            save_json(data_dir / "neural_weights.json", restored.network.state_dict())
            stale = NixLMsNeuralCore(data_dir)
            self.assertAlmostEqual(stale.config.lif_retrieval_threshold, 0.45)

    def test_calibration_is_ignored_when_validation_dataset_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            ai.network.output_updates = 12
            ai.encoder.updates = 7
            ai.learning.dataset.add("validation question one", "validation answer one", "validation")
            save_json(data_dir / "neural_weights.json", ai.network.state_dict())
            ai._save_encoder()
            save_json(data_dir / "lif_calibration.json", {
                "schema_version": 1,
                "threshold": 0.80,
                "readout_updates": 12,
                "encoder_updates": 7,
                "encoder_vocab_size": len(ai.encoder.vocab),
                "validation_fingerprint": ai.learning.validation_fingerprint(),
                "candidate_memory_fingerprint": ai.learning.lif_candidate_fingerprint(),
            })

            ai.learning.dataset.add("validation question two", "validation answer two", "validation")
            restored = NixLMsNeuralCore(data_dir)

            self.assertAlmostEqual(restored.config.lif_retrieval_threshold, 0.45)

    def test_calibration_is_ignored_when_candidate_memory_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            ai.network.output_updates = 12
            ai.encoder.updates = 7
            save_json(data_dir / "neural_weights.json", ai.network.state_dict())
            ai._save_encoder()
            save_json(data_dir / "lif_calibration.json", {
                "schema_version": 1,
                "threshold": 0.80,
                "readout_updates": 12,
                "encoder_updates": 7,
                "encoder_vocab_size": len(ai.encoder.vocab),
                "validation_fingerprint": ai.learning.validation_fingerprint(),
                "candidate_memory_fingerprint": ai.learning.lif_candidate_fingerprint(),
            })

            ai.memory.remember("novo candidato", "nova resposta candidata")
            restored = NixLMsNeuralCore(data_dir)

            self.assertAlmostEqual(restored.config.lif_retrieval_threshold, 0.45)

    def test_new_training_invalidates_persisted_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ai = NixLMsNeuralCore(data_dir)
            ai.learning.dataset.add("pergunta treino", "resposta treino", "train")
            ai.config.lif_retrieval_threshold = 0.82
            save_json(data_dir / "lif_calibration.json", {
                "schema_version": 1,
                "threshold": 0.82,
                "readout_updates": 0,
                "encoder_updates": 0,
                "encoder_vocab_size": len(ai.encoder.vocab),
            })

            ai.learning.train(epochs=1)

            self.assertFalse((data_dir / "lif_calibration.json").exists())
            self.assertAlmostEqual(ai.config.lif_retrieval_threshold, 0.45)


if __name__ == "__main__":
    unittest.main()
