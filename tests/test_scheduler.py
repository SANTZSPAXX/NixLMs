import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from nixlms_core.scheduler import TaskScheduler


class TaskSchedulerTests(unittest.TestCase):
    def make_scheduler(self, root, **kwargs):
        scheduler = TaskScheduler(Path(root) / "scheduler.sqlite3", **kwargs)
        return scheduler

    def test_one_shot_persists_executes_and_records_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            scheduler = self.make_scheduler(tmp)
            scheduler.register_handler("record", lambda payload: calls.append(payload["value"]) or {"ok": True})
            job_id = scheduler.schedule_once("record", {"value": 42})
            self.assertTrue(scheduler.run_once())
            self.assertEqual(calls, [42])
            job = scheduler.list_jobs()[0]
            self.assertEqual(job["id"], job_id)
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["last_result"], {"ok": True})
            self.assertEqual(scheduler.events(job_id)[-1]["event"], "scheduled")
            self.assertEqual(scheduler.stats()["by_status"]["completed"], 1)

    def test_jobs_survive_scheduler_recreation_and_handlers_are_re_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scheduler.sqlite3"
            first = TaskScheduler(path)
            first.register_handler("persisted", lambda payload: payload["x"])
            job_id = first.schedule_once("persisted", {"x": 1}, delay_seconds=30)
            second = TaskScheduler(path)
            second.register_handler("persisted", lambda payload: payload["x"])
            self.assertEqual(second.list_jobs()[0]["id"], job_id)
            self.assertEqual(second.list_jobs()[0]["status"], "pending")

    def test_recurring_job_is_rescheduled_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self.make_scheduler(tmp)
            calls = []
            scheduler.register_handler("tick", lambda payload: calls.append("tick") or len(calls))
            job_id = scheduler.schedule_interval("tick", 60, first_delay_seconds=60)
            with sqlite3.connect(scheduler.path) as db:
                db.execute("UPDATE scheduled_jobs SET run_at=? WHERE id=?", (time.time() - 1, job_id))
            self.assertTrue(scheduler.run_once())
            job = scheduler.list_jobs()[0]
            self.assertEqual(job["status"], "pending")
            self.assertEqual(job["attempts"], 0)
            self.assertGreater(job["run_at"], time.time() + 40)
            self.assertEqual(calls, ["tick"])

    def test_cancel_only_cancels_pending_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self.make_scheduler(tmp)
            scheduler.register_handler("noop", lambda payload: None)
            job_id = scheduler.schedule_once("noop", delay_seconds=60)
            self.assertTrue(scheduler.cancel(job_id))
            self.assertFalse(scheduler.cancel(job_id))
            self.assertEqual(scheduler.list_jobs()[0]["status"], "cancelled")

    def test_unknown_handlers_and_invalid_payloads_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self.make_scheduler(tmp)
            with self.assertRaises(ValueError):
                scheduler.schedule_once("shell", {"command": "echo unsafe"})
            scheduler.register_handler("safe", lambda payload: None)
            with self.assertRaises(ValueError):
                scheduler.schedule_once("safe", {"not_json": object()})
            with self.assertRaises(ValueError):
                scheduler.schedule_once("safe", ["not", "an", "object"])

    def test_retry_then_dead_letter_after_attempt_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self.make_scheduler(tmp)
            scheduler.register_handler("broken", lambda payload: (_ for _ in ()).throw(RuntimeError("expected")))
            job_id = scheduler.schedule_once("broken", max_attempts=2)
            self.assertTrue(scheduler.run_once())
            job = scheduler.list_jobs()[0]
            self.assertEqual(job["status"], "pending")
            self.assertIn("expected", job["last_error"])
            with sqlite3.connect(scheduler.path) as db:
                db.execute("UPDATE scheduled_jobs SET run_at=? WHERE id=?", (time.time() - 1, job_id))
            self.assertTrue(scheduler.run_once())
            self.assertEqual(scheduler.list_jobs()[0]["status"], "failed")
            events = [event["event"] for event in scheduler.events(job_id)]
            self.assertIn("retry_scheduled", events)
            self.assertIn("failed", events)

    def test_priority_is_respected_for_due_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self.make_scheduler(tmp)
            calls = []
            scheduler.register_handler("record", lambda payload: calls.append(payload["name"]))
            scheduler.schedule_once("record", {"name": "low"}, priority=0)
            scheduler.schedule_once("record", {"name": "high"}, priority=10)
            scheduler.run_due()
            self.assertEqual(calls, ["high", "low"])

    def test_worker_start_stop_is_explicit_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self.make_scheduler(tmp, poll_interval=0.1)
            self.assertFalse(scheduler.running)
            self.assertTrue(scheduler.start())
            self.assertFalse(scheduler.start())
            self.assertTrue(scheduler.running)
            self.assertTrue(scheduler.stop())
            self.assertFalse(scheduler.running)

    def test_agent_registers_internal_cognitive_handlers(self):
        from nixlms_core import NixLMsNeuralCore
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            self.assertEqual(
                set(ai.scheduler.stats()["registered_handlers"]),
                {"memory_housekeeping", "dataset_audit", "goal_review"},
            )
            job_id = ai.scheduler.schedule_once("dataset_audit")
            self.assertTrue(ai.scheduler.run_once())
            job = next(item for item in ai.scheduler.list_jobs() if item["id"] == job_id)
            self.assertEqual(job["status"], "completed")
            self.assertTrue(job["last_result"]["valid"])
            self.assertFalse(ai.scheduler.running)

    def test_nonpositive_run_limit_does_not_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self.make_scheduler(tmp)
            calls = []
            scheduler.register_handler("record", lambda payload: calls.append(1))
            scheduler.schedule_once("record")
            self.assertEqual(scheduler.run_due(0), 0)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
