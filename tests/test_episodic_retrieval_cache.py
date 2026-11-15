import hashlib
import json
from datetime import datetime, timedelta, timezone
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


class EpisodicCacheParityTests(unittest.TestCase):
    def _paired_memories(self, tmp):
        source_path = Path(tmp) / "source.json"
        source = EpisodicMemory(source_path)
        source.record("Como usar Python", "Python é uma linguagem.")
        source.record("Como usar Java", "Java executa na JVM.")

        payload = source_path.read_bytes()
        baseline_path = Path(tmp) / "baseline.json"
        cached_path = Path(tmp) / "cached.json"
        baseline_path.write_bytes(payload)
        cached_path.write_bytes(payload)

        baseline = EpisodicMemory(baseline_path, embedding_cache_size=0)
        cached = EpisodicMemory(cached_path, embedding_cache_size=2)
        return baseline, cached

    def _assert_equivalent(self, expected, actual):
        expected_ids = [item["id"] for _, item in expected]
        actual_ids = [item["id"] for _, item in actual]
        self.assertEqual(expected_ids, actual_ids)

        expected_scores = {item["id"]: score for score, item in expected}
        actual_scores = {item["id"]: score for score, item in actual}
        self.assertEqual(set(expected_scores), set(actual_scores))
        for episode_id, expected_score in expected_scores.items():
            self.assertLessEqual(
                abs(expected_score - actual_scores[episode_id]),
                1e-5,
                msg="Diferença de score acima da tolerância float32 para " + episode_id,
            )

    def test_cache_disabled_and_enabled_preserve_ids_order_scores_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, cached = self._paired_memories(tmp)
            baseline_encoder = CountingEncoder()
            cached_encoder = CountingEncoder()
            baseline_hash = hashlib.sha256(baseline.path.read_bytes()).hexdigest()
            cached_hash = hashlib.sha256(cached.path.read_bytes()).hexdigest()

            baseline_first = baseline.recall(
                "usar Python", baseline_encoder, limit=10, min_score=0
            )
            baseline_second = baseline.recall(
                "usar Python", baseline_encoder, limit=10, min_score=0
            )
            cached_cold = cached.recall(
                "usar Python", cached_encoder, limit=10, min_score=0
            )
            cached_warm = cached.recall(
                "usar Python", cached_encoder, limit=10, min_score=0
            )

            self._assert_equivalent(baseline_first, cached_cold)
            self._assert_equivalent(baseline_second, cached_warm)
            self.assertEqual(baseline_encoder.encoded_passages, 4)
            self.assertEqual(cached_encoder.encoded_passages, 2)
            self.assertEqual(
                cached.stats()["episodic_embedding_cache_hits"], 2
            )
            self.assertEqual(
                baseline.stats()["episodic_embedding_cache_entries"], 0
            )
            self.assertEqual(
                hashlib.sha256(baseline.path.read_bytes()).hexdigest(),
                baseline_hash,
            )
            self.assertEqual(
                hashlib.sha256(cached.path.read_bytes()).hexdigest(),
                cached_hash,
            )

    def test_feedback_importance_and_recency_are_recalculated_without_reencoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, cached = self._paired_memories(tmp)
            baseline_encoder = CountingEncoder()
            cached_encoder = CountingEncoder()

            baseline_initial = baseline.recall(
                "usar Python", baseline_encoder, limit=10, min_score=0
            )
            cached_initial = cached.recall(
                "usar Python", cached_encoder, limit=10, min_score=0
            )
            self._assert_equivalent(baseline_initial, cached_initial)
            target_id = baseline.items[0]["id"]

            for memory in (baseline, cached):
                target = next(item for item in memory.items if item["id"] == target_id)
                target["feedback"] = "positive"
                target["importance"] = 0.95

            baseline_positive = baseline.recall(
                "usar Python", baseline_encoder, limit=10, min_score=0
            )
            cached_positive = cached.recall(
                "usar Python", cached_encoder, limit=10, min_score=0
            )
            self._assert_equivalent(baseline_positive, cached_positive)

            score_before = next(score for score, item in baseline_initial if item["id"] == target_id)
            score_positive = next(score for score, item in baseline_positive if item["id"] == target_id)
            self.assertGreater(score_positive, score_before)

            old_timestamp = (
                datetime.now(timezone.utc) - timedelta(days=180)
            ).isoformat()
            for memory in (baseline, cached):
                target = next(item for item in memory.items if item["id"] == target_id)
                target["timestamp"] = old_timestamp

            baseline_aged = baseline.recall(
                "usar Python", baseline_encoder, limit=10, min_score=0
            )
            cached_aged = cached.recall(
                "usar Python", cached_encoder, limit=10, min_score=0
            )
            self._assert_equivalent(baseline_aged, cached_aged)

            score_aged = next(score for score, item in baseline_aged if item["id"] == target_id)
            self.assertLess(score_aged, score_positive)
            self.assertEqual(cached_encoder.encoded_passages, 2)
            self.assertEqual(baseline_encoder.encoded_passages, 6)


if __name__ == "__main__":
    unittest.main()
