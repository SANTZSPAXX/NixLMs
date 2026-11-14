"""Surrogate-gradient and readout-independent contrastive learning for LIF recurrence."""
import tempfile
import unittest
from pathlib import Path

from nixlms_core import NixLMsNeuralCore
from nixlms_core.neural import LIFNetwork


class LIFRecurrentLearningTests(unittest.TestCase):
    def _network(self):
        return LIFNetwork(
            input_size=8, hidden_size=10, output_size=4, steps=12,
            threshold=0.06, leak=0.86, seed=19,
        )

    def test_contrastive_recurrent_training_updates_core_not_readout(self):
        net = self._network()
        left = [0.35, -0.1, 0.22, 0.4, -0.2, 0.15, 0.05, 0.3]
        right = [0.30, -0.08, 0.25, 0.38, -0.18, 0.12, 0.07, 0.28]
        before_in = [row[:] for row in net.w_in]
        before_rec = [row[:] for row in net.w_rec]
        before_out = [row[:] for row in net.w_out]

        report = net.train_recurrent_pair(
            left, right, label=1, learning_rate=0.002,
            margin=0.25, surrogate_width=0.5,
        )

        self.assertTrue(report["updated"])
        self.assertGreater(net.recurrent_updates, 0)
        self.assertNotEqual(net.w_in, before_in)
        self.assertNotEqual(net.w_rec, before_rec)
        self.assertEqual(net.w_out, before_out)
        self.assertTrue(all(net.w_rec[i][i] == 0.0 for i in range(net.hidden_size)))

    def test_recurrent_output_training_backpropagates_into_input_and_recurrent_weights(self):
        net = self._network()
        vector = [0.2, -0.1, 0.4, 0.3, -0.2, 0.1, 0.25, 0.15]
        target = [0.8, -0.4, 0.2, 0.6]
        before_in = [row[:] for row in net.w_in]
        before_rec = [row[:] for row in net.w_rec]
        before_out = [row[:] for row in net.w_out]

        report = net.train_recurrent(
            vector, target, learning_rate=0.001, surrogate_width=0.5
        )

        self.assertTrue(report["updated"])
        self.assertGreater(net.recurrent_updates, 0)
        self.assertNotEqual(net.w_in, before_in)
        self.assertNotEqual(net.w_rec, before_rec)
        self.assertEqual(net.w_out, before_out)

    def test_recurrent_learning_rejects_invalid_values_without_mutating_weights(self):
        net = self._network()
        before = net.state_dict()
        with self.assertRaises(ValueError):
            net.train_recurrent_pair([float("nan")] * 8, [0.1] * 8, label=1)
        with self.assertRaises(ValueError):
            net.train_recurrent([0.1] * 8, [float("inf")] * 4)
        self.assertEqual(net.state_dict(), before)

    def test_recurrent_update_counter_roundtrips_and_old_checkpoints_load(self):
        net = self._network()
        net.train_recurrent_pair(
            [0.2, -0.1, 0.4, 0.3, -0.2, 0.1, 0.25, 0.15],
            [0.18, -0.08, 0.35, 0.28, -0.15, 0.12, 0.2, 0.17],
            label=1,
        )
        state = net.state_dict()
        restored = self._network()

        self.assertTrue(restored.load_state_dict(state))
        self.assertEqual(restored.recurrent_updates, net.recurrent_updates)
        self.assertEqual(restored.state_dict(), state)

        legacy = dict(state)
        legacy.pop("recurrent_updates")
        legacy_restored = self._network()
        self.assertTrue(legacy_restored.load_state_dict(legacy))
        self.assertEqual(legacy_restored.recurrent_updates, 0)

    def test_lif_validation_benchmark_uses_validation_pairs_only_without_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add_pair(
                "estou feliz", "estou contente", 1, "validation"
            )
            ai.learning.dataset.add_pair(
                "o céu é azul", "um número é par", 0, "validation"
            )
            ai.learning.dataset.add_pair(
                "teste positivo", "teste semelhante", 1, "test"
            )
            before = ai.network.state_dict()

            report = ai.learning.evaluate_lif_representations()

            self.assertEqual(report["samples"], 2)
            self.assertEqual(report["positive_samples"], 1)
            self.assertEqual(report["negative_samples"], 1)
            self.assertTrue(report["protocol"]["validation_split_used"])
            self.assertFalse(report["protocol"]["test_split_used"])
            self.assertFalse(report["protocol"]["weights_updated"])
            self.assertEqual(ai.network.state_dict(), before)

    def test_learning_engine_trains_lif_recurrence_from_qa_and_contrastive_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("pergunta alfa", "resposta alfa", "train")
            ai.learning.dataset.add_pair(
                "estou contente", "estou feliz", 1, "train"
            )

            report = ai.learning.train(epochs=2)

            self.assertGreater(report["lif_recurrent_updates"], 0)
            self.assertGreater(report["lif_pair_updates"], 0)
            self.assertIsNotNone(report["mean_lif_recurrent_loss"])
            self.assertIsNotNone(report["mean_lif_pair_loss"])
            self.assertGreater(ai.network.recurrent_updates, 0)


if __name__ == "__main__":
    unittest.main()
