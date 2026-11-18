import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from benchmarks.episodic_retrieval_quality_ptbr import (
    calculate_query_metrics,
    compute_dataset_hash,
    evaluate_dataset,
    load_dataset,
    load_encoder,
    validate_dataset,
)
from nixlms_core.encoding import SemanticEncoder
from nixlms_core.episodic import EpisodicMemory


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "datasets" / "episodic_retrieval_ptbr"
SCRIPT = ROOT / "benchmarks" / "episodic_retrieval_quality_ptbr.py"


class EpisodicRetrievalQualityMetricTests(unittest.TestCase):
    def test_perfect_ranking_has_all_metrics_equal_to_one(self):
        metrics = calculate_query_metrics(
            ["ep-a", "ep-b", "ep-c"],
            {"ep-a": 2, "ep-b": 1},
            k=2,
        )
        self.assertEqual(metrics["ndcg_at_k"], 1.0)
        self.assertEqual(metrics["mrr_at_k"], 1.0)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["precision_at_k"], 1.0)
        self.assertEqual(metrics["first_relevant_rank"], 1)

    def test_metrics_penalize_relevant_items_below_cutoff(self):
        metrics = calculate_query_metrics(
            ["irrelevant", "ep-a", "ep-b"],
            {"ep-a": 2, "ep-b": 1},
            k=2,
        )
        expected_ndcg = (
            (3.0 / math.log2(3.0))
            / (3.0 + 1.0 / math.log2(3.0))
        )
        self.assertAlmostEqual(metrics["ndcg_at_k"], expected_ndcg, places=12)
        self.assertEqual(metrics["mrr_at_k"], 0.5)
        self.assertEqual(metrics["recall_at_k"], 0.5)
        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["first_relevant_rank"], 2)

    def test_metrics_require_positive_cutoff_and_relevance_judgments(self):
        with self.assertRaises(ValueError):
            calculate_query_metrics(["ep-a"], {"ep-a": 2}, k=0)
        with self.assertRaises(ValueError):
            calculate_query_metrics(["ep-a"], {}, k=5)


class EpisodicRetrievalQualityDatasetTests(unittest.TestCase):
    def test_pilot_has_fifty_episodes_thirty_queries_and_valid_qrels(self):
        episodes, queries, qrels, qrels_by_query, digest = load_dataset(DATA_DIR)
        self.assertEqual(len(episodes), 50)
        self.assertEqual(len(queries), 30)
        self.assertEqual(len(qrels), 32)
        self.assertEqual(len(qrels_by_query), 24)
        self.assertEqual(len(digest), 64)
        self.assertEqual(
            sum(bool(row["expects_no_answer"]) for row in queries),
            6,
        )

    def test_answerable_query_without_qrels_is_rejected(self):
        episodes, queries, qrels, _, _ = load_dataset(DATA_DIR)
        with self.assertRaisesRegex(ValueError, "sem qrels"):
            validate_dataset(episodes, queries, qrels[:-2])

    def test_duplicate_qrel_is_rejected(self):
        episodes, queries, qrels, _, _ = load_dataset(DATA_DIR)
        invalid_qrels = list(qrels) + [dict(qrels[0])]
        with self.assertRaisesRegex(ValueError, "qrel duplicado"):
            validate_dataset(episodes, queries, invalid_qrels)

    def test_no_answer_category_must_match_expectation_flag(self):
        episodes, queries, qrels, _, _ = load_dataset(DATA_DIR)
        changed_queries = [dict(row) for row in queries]
        changed_queries[-1]["expects_no_answer"] = False
        with self.assertRaisesRegex(ValueError, "inconsistentes"):
            validate_dataset(episodes, changed_queries, qrels)

    def test_qrel_for_unanswerable_query_is_rejected(self):
        episodes, queries, qrels, _, _ = load_dataset(DATA_DIR)
        invalid_qrels = list(qrels) + [{
            "query_id": "q025",
            "episode_id": "ep001",
            "relevance": 1,
        }]
        with self.assertRaisesRegex(ValueError, "sem resposta"):
            validate_dataset(episodes, queries, invalid_qrels)

    def test_evaluation_is_deterministic_and_does_not_mutate_dataset(self):
        before = compute_dataset_hash(DATA_DIR)
        first = evaluate_dataset(DATA_DIR)
        second = evaluate_dataset(DATA_DIR)
        after = compute_dataset_hash(DATA_DIR)

        self.assertEqual(first, second)
        self.assertEqual(before, after)
        self.assertEqual(first["dataset"]["sha256"], before)
        self.assertEqual(first["metrics"]["overall"]["query_count"], 30)
        self.assertEqual(
            set(first["metrics"]["by_category"]),
            {"parafrase", "coloquial", "variacao_ortografica", "consulta_curta", "sem_resposta"},
        )
        self.assertEqual(
            first["metrics"]["overall"]["abstention"]["no_answer_query_count"],
            6,
        )
        self.assertEqual(
            first["metrics"]["overall"]["abstention"]["false_positive_rate"],
            0.0,
        )
        self.assertNotIn(str(DATA_DIR.resolve()), json.dumps(first, ensure_ascii=False))

    def test_equal_score_ranking_is_independent_of_episode_file_order(self):
        timestamp = "2026-01-15T12:00:00+00:00"
        rows = [
            {
                "id": "episode-a",
                "timestamp": timestamp,
                "user_input": "alpha beta",
                "assistant_output": "shared content",
                "context": {},
                "outcome": "",
                "importance": 0.5,
                "feedback": None,
                "tags": [],
            },
            {
                "id": "episode-b",
                "timestamp": timestamp,
                "user_input": "alpha beta",
                "assistant_output": "shared content",
                "context": {},
                "outcome": "",
                "importance": 0.5,
                "feedback": None,
                "tags": [],
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            first_path = Path(temporary) / "first.json"
            second_path = Path(temporary) / "second.json"
            first_path.write_text(json.dumps(rows), encoding="utf-8")
            second_path.write_text(json.dumps(list(reversed(rows))), encoding="utf-8")
            first = EpisodicMemory(first_path).recall("alpha beta", limit=2, min_score=0)
            second = EpisodicMemory(second_path).recall("alpha beta", limit=2, min_score=0)

        self.assertEqual([item["id"] for _, item in first],
                         [item["id"] for _, item in second])
        self.assertEqual([item["id"] for _, item in first],
                         ["episode-b", "episode-a"])

    def test_local_native_checkpoint_must_be_explicit_and_compatible(self):
        encoder = SemanticEncoder(dimensions=8)
        encoder.fit_vocabulary(["memória episódica em português"])
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "semantic_encoder.json"
            checkpoint.write_text(
                json.dumps(encoder.state_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            loaded, info = load_encoder(native_checkpoint=checkpoint)
            self.assertEqual(info["mode"], "native")
            self.assertEqual(info["dimensions"], 8)
            self.assertEqual(loaded.updates, encoder.updates)

    def test_missing_native_checkpoint_fails_without_fallback_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                load_encoder(native_checkpoint=missing)

    def test_e5_requires_an_existing_local_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing-model"
            with self.assertRaises(FileNotFoundError):
                load_encoder(e5_model_path=missing)

    def test_cli_runs_offline_lexical_mode_and_emits_machine_readable_json(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(report["encoder"]["mode"], "lexical")
        self.assertEqual(report["dataset"]["episode_count"], 50)
        self.assertEqual(report["dataset"]["query_count"], 30)
        self.assertEqual(report["evaluation"]["k"], 5)
        self.assertNotIn(str(ROOT.resolve()), completed.stdout)


if __name__ == "__main__":
    unittest.main()
