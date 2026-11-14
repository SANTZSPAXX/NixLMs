"""Safe candidate training, validation gates and checkpoint rollback."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nixlms_core import NixLMsNeuralCore
from nixlms_core.learning import LearningEngine


class SafeIncrementalLearningTests(unittest.TestCase):
    def _agent(self, root):
        ai = NixLMsNeuralCore(Path(root))
        ai.learning.dataset.add("pergunta treino alfa", "resposta treino alfa", "train")
        ai.learning.dataset.add("pergunta treino beta", "resposta treino beta", "train")
        ai.learning.dataset.add("pergunta valida alfa", "resposta valida alfa", "validation")
        ai.learning.dataset.add("pergunta valida beta", "resposta valida beta", "validation")
        return ai

    @staticmethod
    def _metrics(loss, generation_f1, lif_loss, margin=0.1):
        return {
            "samples": 2,
            "metrics": {
                "decoder_loss": loss,
                "decoder_token_accuracy": 0.5,
                "decoder_oov_rate": 0.2,
                "generation_token_f1": generation_f1,
                "lif_output_loss": lif_loss,
                "representation_margin": margin,
                "representation_pairwise_accuracy": 0.5,
            },
            "protocol": {"validation_split_used": True, "test_split_used": False,
                         "weights_updated": False},
        }

    def test_validation_metrics_never_read_test_rows_or_update_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = self._agent(tmp)
            ai.learning.dataset.add("pergunta teste isolada", "resposta teste isolada", "test")
            before = {
                "encoder": ai.encoder.state_dict(),
                "network": ai.network.state_dict(),
                "decoder": ai.decoder.state_dict(),
            }

            report = ai.learning._validation_metrics()

            self.assertEqual(report["samples"], 2)
            self.assertTrue(report["protocol"]["validation_split_used"])
            self.assertFalse(report["protocol"]["test_split_used"])
            self.assertFalse(report["protocol"]["weights_updated"])
            self.assertEqual(ai.encoder.state_dict(), before["encoder"])
            self.assertEqual(ai.network.state_dict(), before["network"])
            self.assertEqual(ai.decoder.state_dict(), before["decoder"])

    def test_safe_training_refuses_without_validation_and_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("pergunta treino", "resposta treino", "train")
            before = ai.encoder.state_dict()

            report = ai.learning.train_incremental(epochs=1)

            self.assertFalse(report["accepted"])
            self.assertEqual(report["reason"], "insufficient_validation_samples")
            self.assertEqual(ai.encoder.state_dict(), before)
            self.assertFalse((Path(tmp) / "checkpoints" / "incremental").exists())

    def test_real_candidate_training_completes_and_keeps_rollback_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = self._agent(tmp)
            before = {
                "encoder": ai.encoder.state_dict(),
                "network": ai.network.state_dict(),
                "decoder": ai.decoder.state_dict(),
            }

            report = ai.learning.train_incremental(epochs=1)

            self.assertIn(report["reason"], {
                "accepted", "validation_regression", "no_measurable_improvement"
            })
            self.assertTrue(report["checkpoint_id"])
            self.assertTrue(report["rollback_available"])
            if report["accepted"]:
                self.assertNotEqual(ai.decoder.state_dict(), before["decoder"])
            else:
                self.assertEqual(ai.encoder.state_dict(), before["encoder"])
                self.assertEqual(ai.network.state_dict(), before["network"])
                self.assertEqual(ai.decoder.state_dict(), before["decoder"])

            restored = ai.learning.restore_incremental_checkpoint(report["checkpoint_id"])
            self.assertTrue(restored["restored"])
            self.assertEqual(ai.encoder.state_dict(), before["encoder"])
            self.assertEqual(ai.network.state_dict(), before["network"])
            self.assertEqual(ai.decoder.state_dict(), before["decoder"])

    def test_regressing_candidate_is_rejected_without_touching_live_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = self._agent(tmp)
            before = {
                "encoder": ai.encoder.state_dict(),
                "network": ai.network.state_dict(),
                "decoder": ai.decoder.state_dict(),
            }
            metrics = [
                self._metrics(1.0, 0.4, 0.5),
                self._metrics(1.4, 0.2, 0.8),
            ]
            with patch.object(LearningEngine, "_validation_metrics", side_effect=metrics):
                report = ai.learning.train_incremental(epochs=1)

            self.assertFalse(report["accepted"])
            self.assertEqual(report["reason"], "validation_regression")
            self.assertEqual(ai.encoder.state_dict(), before["encoder"])
            self.assertEqual(ai.network.state_dict(), before["network"])
            self.assertEqual(ai.decoder.state_dict(), before["decoder"])
            self.assertTrue(report["checkpoint_id"])

    def test_improving_candidate_is_committed_and_checkpoint_can_restore_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = self._agent(tmp)
            before = {
                "encoder": ai.encoder.state_dict(),
                "network": ai.network.state_dict(),
                "decoder": ai.decoder.state_dict(),
                "knowledge": list(ai.memory.knowledge),
                "mental_map": {
                    "nodes": dict(ai.mental_map.nodes),
                    "edges": dict(ai.mental_map.edges),
                },
            }
            metrics = [
                self._metrics(1.0, 0.4, 0.5),
                self._metrics(0.8, 0.6, 0.3, margin=0.2),
            ]
            with patch.object(LearningEngine, "_validation_metrics", side_effect=metrics):
                report = ai.learning.train_incremental(epochs=1)

            self.assertTrue(report["accepted"])
            self.assertTrue(report["rollback_available"])
            self.assertNotEqual(ai.decoder.state_dict(), before["decoder"])
            self.assertGreaterEqual(len(ai.memory.knowledge), len(before["knowledge"]))
            self.assertNotEqual(ai.mental_map.nodes, before["mental_map"]["nodes"])

            restored = ai.learning.restore_incremental_checkpoint(report["checkpoint_id"])

            self.assertTrue(restored["restored"])
            self.assertEqual(ai.encoder.state_dict(), before["encoder"])
            self.assertEqual(ai.network.state_dict(), before["network"])
            self.assertEqual(ai.decoder.state_dict(), before["decoder"])
            self.assertEqual(ai.memory.knowledge, before["knowledge"])
            self.assertEqual(ai.mental_map.nodes, before["mental_map"]["nodes"])
            self.assertEqual(ai.mental_map.edges, before["mental_map"]["edges"])

    def test_training_is_rejected_if_dataset_changes_during_candidate_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = self._agent(tmp)
            calls = {"count": 0}

            def metrics_with_concurrent_dataset_change():
                calls["count"] += 1
                if calls["count"] == 1:
                    return self._metrics(1.0, 0.4, 0.5)
                ai.learning.dataset.add(
                    "pergunta adicionada durante treino",
                    "resposta adicionada durante treino",
                    "train",
                )
                return self._metrics(0.8, 0.6, 0.3, margin=0.2)

            with patch.object(
                LearningEngine, "_validation_metrics",
                side_effect=metrics_with_concurrent_dataset_change,
            ):
                report = ai.learning.train_incremental(epochs=1)

            self.assertFalse(report["accepted"])
            self.assertEqual(
                report["reason"], "dataset_changed_during_candidate_training"
            )

    def test_checkpoint_tampering_is_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = self._agent(tmp)
            metrics = [
                self._metrics(1.0, 0.4, 0.5),
                self._metrics(0.8, 0.6, 0.3, margin=0.2),
            ]
            with patch.object(LearningEngine, "_validation_metrics", side_effect=metrics):
                report = ai.learning.train_incremental(epochs=1)
            checkpoint_dir = (
                Path(tmp) / "checkpoints" / "incremental" / report["checkpoint_id"]
            )
            weights = checkpoint_dir / "neural_weights.json"
            weights.write_text("{} corrupted", encoding="utf-8")

            with self.assertRaises(ValueError):
                ai.learning.restore_incremental_checkpoint(report["checkpoint_id"])

    def test_checkpoint_identifier_cannot_escape_checkpoint_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            with self.assertRaises(ValueError):
                ai.learning.restore_incremental_checkpoint("../outside")


if __name__ == "__main__":
    unittest.main()
