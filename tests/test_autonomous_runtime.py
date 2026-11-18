"""Integration tests for the scheduled autonomy lifecycle."""
import os
import tempfile
import unittest
from unittest.mock import patch

from nixlms_core.agent import NixLMsNeuralCore


class AutonomousRuntimeTests(unittest.TestCase):
    def test_startup_schedules_bounded_goal_orchestration(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "NIXLMS_AUTONOMY_ENABLED": "1",
                "NIXLMS_AUTONOMY_INTERVAL_SECONDS": "60",
                "NIXLMS_DISABLE_STARTER_DATASET": "1",
            },
        ):
            ai = NixLMsNeuralCore(data_dir=directory)
            try:
                runtime = ai.start_runtime()
                self.assertTrue(runtime["scheduler_started"])
                self.assertTrue(runtime["autonomy_enabled"])
                self.assertEqual(runtime["autonomy_interval_seconds"], 60)
                self.assertIn(
                    "autonomy_cycle",
                    ai.scheduler.stats()["registered_handlers"],
                )
                jobs = ai.scheduler.list_jobs(limit=1000)
                autonomy_jobs = [
                    job for job in jobs
                    if job["id"] == "nixlms-autonomy-cycle-v1"
                ]
                self.assertEqual(len(autonomy_jobs), 1)
                self.assertEqual(autonomy_jobs[0]["handler"], "autonomy_cycle")
                self.assertEqual(autonomy_jobs[0]["interval_seconds"], 60)
            finally:
                ai.scheduler.stop()

    def test_autonomy_cycle_starts_only_ready_internal_steps(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"NIXLMS_DISABLE_STARTER_DATASET": "1"}
        ):
            ai = NixLMsNeuralCore(data_dir=directory)
            goal = ai.goals.create_goal("Objetivo de teste")
            step = ai.goals.add_step(goal["id"], "Etapa interna")
            try:
                result = ai._scheduled_autonomy_cycle({"limit": 1})
                self.assertEqual(result["processed"], 1)
                updated = ai.goals.get_goal(goal["id"])
                self.assertEqual(updated["steps"][0]["status"], "in_progress")
                self.assertEqual(step["id"], updated["steps"][0]["id"])
                self.assertFalse(
                    any(item["status"] == "completed" for item in updated["steps"])
                )
            finally:
                ai.scheduler.stop()


if __name__ == "__main__":
    unittest.main()
