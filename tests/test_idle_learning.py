import unittest

from nixlms_core.idle_learning import IdleLearningManager


class FakeDataset:
    def __init__(self, audit=None, rows=None):
        self.audit = audit or {"valid": True, "violations": []}
        self.rows = rows or []

    def audit_splits(self):
        return self.audit

    def load(self):
        return list(self.rows)


class FakeLearning:
    def __init__(self, dataset, report=None):
        self.dataset = dataset
        self.report = report or {"accepted": True, "checkpoint_id": "checkpoint-test"}
        self.calls = []

    def train_incremental(self, **kwargs):
        self.calls.append(kwargs)
        return self.report


class FakeAgent:
    def __init__(self, dataset, report=None):
        self.learning = FakeLearning(dataset, report)


class IdleLearningManagerTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.rows = [
            {"type": "qa", "split": "train", "question": "q1", "answer": "a1"},
            {"type": "qa", "split": "validation", "question": "q2", "answer": "a2"},
            {"type": "qa", "split": "validation", "question": "q3", "answer": "a3"},
            {"type": "qa", "split": "validation", "question": "q4", "answer": "a4"},
            {"type": "qa", "split": "validation", "question": "q5", "answer": "a5"},
        ]
        self.dataset = FakeDataset(rows=self.rows)
        self.agent = FakeAgent(self.dataset)
        self.manager = IdleLearningManager(
            self.agent, idle_after_seconds=300, cooldown_seconds=1800,
            clock=lambda: self.now,
        )

    def test_skips_until_idle_threshold(self):
        self.now += 299
        result = self.manager.run_if_idle()
        self.assertEqual(result["reason"], "not_idle")
        self.assertEqual(self.agent.learning.calls, [])

    def test_activity_resets_idle_timer(self):
        self.now += 400
        self.manager.mark_activity()
        self.now += 100
        self.assertEqual(self.manager.run_if_idle()["reason"], "not_idle")

    def test_idle_cycle_runs_one_validation_gated_epoch(self):
        self.now += 301
        result = self.manager.run_if_idle()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(self.agent.learning.calls), 1)
        self.assertEqual(self.agent.learning.calls[0]["epochs"], 1)

    def test_blocks_dataset_integrity_violations(self):
        self.dataset.audit = {"valid": False, "violations": [{"type": "overlap"}]}
        self.now += 301
        result = self.manager.run_if_idle()
        self.assertEqual(result["reason"], "dataset_integrity_failed")
        self.assertEqual(self.agent.learning.calls, [])

    def test_skips_when_validation_is_insufficient(self):
        self.dataset.rows = self.rows[:2]
        self.now += 301
        result = self.manager.run_if_idle()
        self.assertEqual(result["reason"], "insufficient_validation_samples")
        self.assertEqual(self.agent.learning.calls, [])

    def test_respects_training_row_budget(self):
        self.dataset.rows = self.rows + [
            {"type": "qa", "split": "train", "question": "extra", "answer": "row"}
        ] * 501
        self.now += 301
        result = self.manager.run_if_idle()
        self.assertEqual(result["reason"], "training_budget_exceeded")
        self.assertEqual(self.agent.learning.calls, [])

    def test_cooldown_prevents_repeated_training(self):
        self.now += 301
        self.manager.run_if_idle()
        self.now += 301
        result = self.manager.run_if_idle()
        self.assertEqual(result["reason"], "cooldown")
        self.assertEqual(len(self.agent.learning.calls), 1)

    def test_rejected_candidate_is_not_reported_as_learning_success(self):
        self.agent.learning.report = {"accepted": False, "reason": "no_improvement"}
        self.now += 301
        self.assertEqual(self.manager.run_if_idle()["status"], "no_improvement")


if __name__ == "__main__":
    unittest.main()
