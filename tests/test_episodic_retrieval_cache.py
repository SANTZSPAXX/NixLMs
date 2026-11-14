import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from nixlms_core.episodic import EpisodicMemory
from nixlms_core.pretrained_encoder import TransformersSentenceEncoder


class CountingEncoder:
    dimensions = 2
    updates = 0
    semantic_weight = 1.0

    def __init__(self):
        self.passage_batches = []

    @staticmethod
    def _vector(text):
        value = sum(byte for byte in text.encode("utf-8")) % 251
        return [1.0, (value + 1) / 252.0]

    def encode_query(self, text):
        return [1.0, 0.25]

    def encode_passages(self, texts, batch_size=8):
        self.passage_batches.append((list(texts), batch_size))
        return [self._vector(text) for text in texts]

    def encode_passage(self, text):
        return self._vector(text)

    @property
    def encoded_passages(self):
        return sum(len(batch[0]) for batch in self.passage_batches)


class EpisodicRetrievalCacheTests(unittest.TestCase):
    def _memory(self, tmp, **kwargs):
        memory = EpisodicMemory(Path(tmp) / "episodic.json", **kwargs)
        memory.record("Como usar Python", "Python é uma linguagem.")
        memory.record("Como usar Java", "Java executa na JVM.")
        return memory

    def test_warm_recall_reuses_embeddings_without_changing_ranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = self._memory(tmp)
            encoder = CountingEncoder()

            cold = memory.recall("usar Python", encoder, limit=10, min_score=0)
            warm = memory.recall("usar Python", encoder, limit=10, min_score=0)

            self.assertEqual(
                [item["id"] for _, item in cold],
                [item["id"] for _, item in warm],
            )
            for (cold_score, _), (warm_score, _) in zip(cold, warm):
                self.assertAlmostEqual(cold_score, warm_score, places=6)
            self.assertEqual(encoder.encoded_passages, 2)
            stats = memory.stats()
            self.assertEqual(stats["episodic_embedding_cache_hits"], 2)
            self.assertEqual(stats["episodic_embedding_cache_misses"], 2)
            self.assertEqual(stats["episodic_encoded_passages"], 2)
            self.assertEqual(stats["episodic_passage_encoder_calls"], 1)

    def test_new_episode_and_feedback_do_not_reencode_existing_passages(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = self._memory(tmp)
            encoder = CountingEncoder()
            before = memory.recall("usar Python", encoder, limit=10, min_score=0)
            python_id = next(item["id"] for _, item in before if item["user_input"] == "Como usar Python")
            old_score = next(score for score, item in before if item["id"] == python_id)

            memory.set_feedback("Como usar Python", True)
            memory.record("Como usar Rust", "Rust prioriza segurança de memória.")
            after = memory.recall("usar Python", encoder, limit=10, min_score=0)

            new_score = next(score for score, item in after if item["id"] == python_id)
            self.assertGreater(new_score, old_score)
            self.assertEqual(encoder.encoded_passages, 3)
            self.assertEqual(memory.stats()["episodic_embedding_cache_hits"], 2)

    def test_changed_content_invalidates_only_its_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = self._memory(tmp)
            encoder = CountingEncoder()
            memory.recall("usar", encoder, limit=10, min_score=0)
            memory.items[0]["assistant_output"] = "Resposta alterada para Python."

            memory.recall("usar", encoder, limit=10, min_score=0)

            stats = memory.stats()
            self.assertEqual(encoder.encoded_passages, 3)
            self.assertEqual(stats["episodic_embedding_cache_entries"], 2)
            self.assertEqual(stats["episodic_embedding_cache_hits"], 1)
            self.assertEqual(stats["episodic_embedding_cache_evictions"], 1)

    def test_encoder_identity_change_invalidates_previous_vectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = self._memory(tmp)
            first_encoder = CountingEncoder()
            second_encoder = CountingEncoder()

            memory.recall("usar", first_encoder, limit=10, min_score=0)
            memory.recall("usar", second_encoder, limit=10, min_score=0)

            self.assertEqual(first_encoder.encoded_passages, 2)
            self.assertEqual(second_encoder.encoded_passages, 2)
            self.assertEqual(memory.stats()["episodic_embedding_cache_evictions"], 2)

    def test_encoder_update_counter_invalidates_previous_vectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = self._memory(tmp)
            encoder = CountingEncoder()

            memory.recall("usar", encoder, limit=10, min_score=0)
            encoder.updates += 1
            memory.recall("usar", encoder, limit=10, min_score=0)

            self.assertEqual(encoder.encoded_passages, 4)
            self.assertEqual(memory.stats()["episodic_embedding_cache_evictions"], 2)

    def test_lru_cache_obeys_configured_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = self._memory(tmp, embedding_cache_size=1)
            encoder = CountingEncoder()

            memory.recall("usar", encoder, limit=10, min_score=0)

            stats = memory.stats()
            self.assertEqual(stats["episodic_embedding_cache_entries"], 1)
            self.assertEqual(stats["episodic_embedding_cache_limit"], 1)
            self.assertEqual(stats["episodic_embedding_cache_evictions"], 1)

    def test_record_retention_releases_cache_entry_for_removed_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(
                Path(tmp) / "episodic.json", max_items=2
            )
            memory.record("primeira pergunta", "primeira resposta")
            memory.record("segunda pergunta", "segunda resposta")
            encoder = CountingEncoder()
            memory.recall("pergunta", encoder, limit=10, min_score=0)

            memory.record("terceira pergunta", "terceira resposta")

            stats = memory.stats()
            self.assertEqual(stats["episodic_embedding_cache_entries"], 1)
            self.assertEqual(stats["episodic_embedding_cache_evictions"], 1)
            memory.recall("pergunta", encoder, limit=10, min_score=0)
            self.assertEqual(encoder.encoded_passages, 3)

    def test_missing_passages_are_encoded_in_bounded_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(
                Path(tmp) / "episodic.json",
                max_items=20,
                passage_batch_size=8,
            )
            for index in range(17):
                memory.record("pergunta " + str(index), "resposta " + str(index))
            encoder = CountingEncoder()

            memory.recall("pergunta", encoder, limit=5, min_score=0)

            self.assertEqual(
                [len(batch[0]) for batch in encoder.passage_batches],
                [8, 8, 1],
            )
            self.assertTrue(all(batch[1] == 8 for batch in encoder.passage_batches))

    def test_legacy_episode_without_id_uses_content_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "episodic.json"
            path.write_text(json.dumps([{
                "timestamp": "2026-11-14T12:00:00+00:00",
                "user_input": "pergunta legada",
                "assistant_output": "resposta legada",
                "tags": [],
                "outcome": "",
                "importance": 0.5,
                "feedback": None,
            }]), encoding="utf-8")
            memory = EpisodicMemory(path)
            encoder = CountingEncoder()

            memory.recall("pergunta legada", encoder, min_score=0)
            memory.recall("pergunta legada", encoder, min_score=0)

            self.assertEqual(encoder.encoded_passages, 1)
            self.assertEqual(memory.stats()["episodic_embedding_cache_hits"], 1)

    def test_encoder_without_batch_api_uses_cached_single_passage_fallback(self):
        class SinglePassageEncoder:
            dimensions = 2
            def __init__(self):
                self.calls = 0
            def encode_query(self, _text):
                return [1.0, 0.0]
            def encode_passage(self, _text):
                self.calls += 1
                return [1.0, 0.0]

        with tempfile.TemporaryDirectory() as tmp:
            memory = self._memory(tmp)
            encoder = SinglePassageEncoder()
            memory.recall("usar", encoder, limit=10, min_score=0)
            memory.recall("usar", encoder, limit=10, min_score=0)
            self.assertEqual(encoder.calls, 2)
            self.assertEqual(memory.stats()["episodic_passage_encoder_calls"], 2)


class PretrainedEncoderBatchTests(unittest.TestCase):
    def test_passages_are_encoded_in_bounded_batches_with_e5_prefix(self):
        class FakeModel:
            def __init__(self):
                self.batches = []
            def get_sentence_embedding_dimension(self):
                return 2
            def encode(self, texts, **kwargs):
                self.batches.append(list(texts))
                return [[3.0, 4.0] for _ in texts]

        model = FakeModel()
        encoder = TransformersSentenceEncoder(
            "local/e5", model_loader=lambda **kwargs: model
        )

        vectors = encoder.encode_passages(
            ["primeiro", "segundo", "", "terceiro"], batch_size=2
        )

        self.assertEqual(model.batches, [
            ["passage: primeiro", "passage: segundo"],
            ["passage: terceiro"],
        ])
        self.assertEqual(len(vectors), 4)
        self.assertAlmostEqual(vectors[0][0], 0.6, places=6)
        self.assertAlmostEqual(vectors[0][1], 0.8, places=6)
        self.assertEqual(vectors[2], [0.0, 0.0])

    def test_passage_batch_size_must_be_positive(self):
        encoder = TransformersSentenceEncoder(
            "local/e5", model_loader=lambda **kwargs: None
        )
        with self.assertRaises(ValueError):
            encoder.encode_passages(["texto"], batch_size=0)


class EpisodicBenchmarkSmokeTests(unittest.TestCase):
    def test_synthetic_benchmark_reports_zero_warm_reencoding(self):
        root = Path(__file__).resolve().parents[1]
        script = root / "benchmarks" / "episodic_retrieval.py"
        completed = subprocess.run(
            [
                sys.executable, str(script),
                "--sizes", "10",
                "--batch-size", "4",
            ],
            cwd=str(root),
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(completed.stdout)
        result = report["results"][0]
        self.assertEqual(result["episodes"], 10)
        self.assertEqual(result["cold_encoded_passages"], 10)
        self.assertEqual(result["warm_additional_encoded_passages"], 0)
        self.assertEqual(result["warm_additional_encoder_calls"], 0)


if __name__ == "__main__":
    unittest.main()
