"""Tests for supervised LIF readout and neural language conditioning."""
import tempfile
import unittest
from pathlib import Path

from nixlms_core import CoreConfig, NixLMsNeuralCore
from nixlms_core.neural import LIFNetwork


class LIFReadoutTests(unittest.TestCase):
    def test_supervised_output_readout_reduces_embedding_loss(self):
        network = LIFNetwork(input_size=8, hidden_size=10, output_size=4, seed=7)
        _, hidden = network.forward([0.2, -0.1, 0.4, 0.3, 0.0, 0.1, -0.2, 0.5])
        target = [0.7, -0.4, 0.2, 0.5]
        initial = network.train_output(hidden, target, learning_rate=0.08)
        losses = [
            network.train_output(hidden, target, learning_rate=0.08)
            for _ in range(120)
        ]
        self.assertLess(losses[-1], initial)
        self.assertEqual(network.output_updates, 121)

    def test_readout_update_counter_survives_state_roundtrip(self):
        network = LIFNetwork(input_size=4, hidden_size=5, output_size=3)
        _, hidden = network.forward([0.1, 0.2, 0.3, 0.4])
        network.train_output(hidden, [0.2, 0.3, 0.4])
        restored = LIFNetwork(input_size=4, hidden_size=5, output_size=3)
        self.assertTrue(restored.load_state_dict(network.state_dict()))
        self.assertEqual(restored.output_updates, 1)

    def test_legacy_weights_load_without_readout_counter(self):
        network = LIFNetwork(input_size=4, hidden_size=5, output_size=3)
        state = network.state_dict()
        state.pop("output_updates")
        restored = LIFNetwork(input_size=4, hidden_size=5, output_size=3)
        self.assertTrue(restored.load_state_dict(state))
        self.assertEqual(restored.output_updates, 0)

    def test_qa_training_activates_lif_as_response_readout(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CoreConfig(lif_retrieval_threshold=0.0,
                                lif_output_learning_rate=0.06)
            ai = NixLMsNeuralCore(Path(tmp), config=config)
            ai.learning.dataset.add(
                "O que a água faz com a luz?",
                "A água pode refletir e refratar a luz."
            )
            report = ai.learning.train(epochs=40)
            self.assertGreater(report["lif_output_updates"], 0)
            self.assertEqual(report["lif_qa_examples_trained"], 1)

            answer = ai.respond("O que a água faz com a luz?", use_language=False)
            self.assertEqual(answer, "A água pode refletir e refratar a luz.")
            self.assertEqual(ai.last_trace["response_source"], "lif_associative_readout")
            self.assertEqual(ai.last_trace["neural_generation_path"],
                             "lif_associative_readout")
            self.assertGreater(ai.last_trace["lif_retrieval_candidates"], 0)

    def test_untrained_lif_readout_is_not_used_as_a_language_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            self.assertEqual(ai._lif_recall([0.1] * ai.network.output_size), [])
            self.assertEqual(ai.network.output_updates, 0)


if __name__ == "__main__":
    unittest.main()
