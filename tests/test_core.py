import tempfile
import unittest
from pathlib import Path

from nixlms_core import NixLMsNeuralCore
from nixlms_core.eeg import EEGInspiredEngine
from nixlms_core.mental_map import MentalMap
from nixlms_core.neural import LIFNetwork
from nixlms_core.encoding import SemanticEncoder
from nixlms_core.memory import MemorySystem
from nixlms_core.utils import cosine


class CoreTests(unittest.TestCase):
    def test_eeg_bands(self):
        engine = EEGInspiredEngine()
        bands = engine.band_energy(engine.synthesize(1.0))
        self.assertEqual(set(bands), {"delta", "theta", "alpha", "beta", "gamma"})
        self.assertAlmostEqual(sum(bands.values()), 1.0, places=5)

    def test_learn_and_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learn("qual é a capital do Brasil", "Brasília")
            self.assertEqual(ai.respond("qual é a capital do Brasil", use_language=False), "Brasília")
            self.assertGreater(ai.status()["semantic_items"], 0)

    def test_empty_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("Digite", NixLMsNeuralCore(Path(tmp)).respond("  "))

    def test_recurrent_weights_persist(self):
        net = LIFNetwork()
        clone = LIFNetwork()
        self.assertTrue(clone.load_state_dict(net.state_dict()))
        self.assertEqual(len(clone.w_rec), clone.hidden_size)

    def test_lif_spike_telemetry_and_inference_is_not_plastic(self):
        net = LIFNetwork(threshold=.08)
        vector = [1.0 / (net.input_size ** .5)] * net.input_size
        before = [row[:] for row in net.eligibility_in]
        net.forward(vector)
        self.assertEqual(len(net.last_spike_counts), net.hidden_size)
        self.assertEqual(sum(net.last_spike_counts),
                         sum(sum(step) for step in net.last_spike_history))
        self.assertEqual(before, net.eligibility_in)

    def test_mental_map_association(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = MentalMap(Path(tmp) / "map.json")
            graph.observe("python programa linguagem")
            self.assertTrue(graph.associate("python"))

    def test_semantic_encoder_learns_positive_pair(self):
        encoder = SemanticEncoder(dimensions=32, seed=7)
        a, b = "estou feliz", "estou contente"
        encoder.fit_vocabulary([a, b])
        before = cosine(encoder.encode(a), encoder.encode(b))
        for _ in range(80):
            encoder.fit_pair(a, b, 1)
        after = cosine(encoder.encode(a), encoder.encode(b))
        self.assertGreater(after, before)
        self.assertGreater(encoder.updates, 0)

    def test_semantic_encoder_learns_negative_pair(self):
        encoder = SemanticEncoder(dimensions=32, seed=11)
        a, b = "o cachorro persegue o gato", "o gato persegue o cachorro"
        encoder.fit_vocabulary([a, b])
        before = cosine(encoder.encode(a), encoder.encode(b))
        for _ in range(80):
            encoder.fit_pair(a, b, 0)
        after = cosine(encoder.encode(a), encoder.encode(b))
        self.assertLess(after, before)

    def test_encoder_inference_does_not_mutate_vocabulary(self):
        encoder = SemanticEncoder(dimensions=16)
        before = len(encoder.vocab)
        encoder.encode("termo totalmente novo")
        self.assertEqual(len(encoder.vocab), before)

    def test_semantic_encoder_state_roundtrip(self):
        encoder = SemanticEncoder(dimensions=16)
        encoder.fit_pair("bom dia", "olá bom dia", 1)
        clone = SemanticEncoder(dimensions=16)
        self.assertTrue(clone.load_state_dict(encoder.state_dict()))
        self.assertEqual(encoder.encode("bom dia"), clone.encode("bom dia"))

    def test_memory_upsert_prevents_duplicates_and_recall_skips_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemorySystem(Path(tmp))
            memory.remember("capital do Brasil", "Brasília")
            memory.remember("capital do Brasil", "Brasília é a capital.")
            class ForbiddenNetwork:
                def forward(self, *_args, **_kwargs):
                    raise AssertionError("recall não deve executar a rede neural")
            encoder = SemanticEncoder()
            encoder.fit_vocabulary(["capital do Brasil"])
            self.assertEqual(len(memory.knowledge), 1)
            self.assertEqual(memory.recall("capital do Brasil", encoder, ForbiddenNetwork())[0][1]["answer"],
                             "Brasília é a capital.")
            self.assertNotIn("_embedding", memory.knowledge[0])

    def test_training_is_idempotent_for_qa_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("o que é Python", "Python é uma linguagem.", "train")
            ai.learning.dataset.add_pair("estou feliz", "estou contente", 1, "train")
            result = ai.learning.train(epochs=3)
            matches = [x for x in ai.memory.knowledge if x.get("question") == "o que é Python"]
            self.assertEqual(len(matches), 1)
            self.assertEqual(result["contrastive_pairs"], 1)
            self.assertGreater(ai.encoder.updates, 0)

    def test_contrastive_dataset_deduplicates_and_prevents_split_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            store = ai.learning.dataset
            store.add_pair("estou feliz", "estou contente", 1, "train")
            store.add_pair("estou contente", "estou feliz", 1, "train")
            self.assertEqual(len([r for r in store.load() if r.get("type") == "pair"]), 1)
            with self.assertRaises(ValueError):
                store.add_pair("estou feliz", "estou contente", 1, "test")
            store.add("capital brasileira", "Brasília", "train")
            with self.assertRaises(ValueError):
                store.add("capital brasileira", "Brasília", "test")

    def test_dataset_metrics_separate_retrieval_and_contrastive(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            ai.learning.dataset.add("capital do Brasil", "Brasília", "test")
            ai.learning.dataset.add_pair("estou alegre", "estou contente", 1, "test")
            metrics = ai.learning.evaluate()
            self.assertEqual(metrics["retrieval"]["samples"], 1)
            self.assertEqual(metrics["contrastive"]["samples"], 1)

    def test_cosine_rejects_dimension_mismatch(self):
        with self.assertRaises(ValueError):
            cosine([1.0, 0.0], [1.0])

    def test_dataset_import_rejects_invalid_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "bad.jsonl"
            source.write_text('{"question":"x","answer":"y","split":"validation"}', encoding="utf-8")
            ai = NixLMsNeuralCore(Path(tmp) / "data")
            with self.assertRaises(ValueError):
                ai.learning.dataset.import_jsonl(source)


if __name__ == "__main__":
    unittest.main()
