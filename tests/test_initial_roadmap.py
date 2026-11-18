import tempfile
import unittest
from pathlib import Path

from nixlms_core.planning import GoalManager
from nixlms_core.roadmap import INITIAL_ROADMAP, seed_initial_roadmap


class InitialRoadmapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.goals = GoalManager(Path(self.temp.name) / "goals.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_seeds_goals_and_dependency_ordered_steps(self):
        result = seed_initial_roadmap(self.goals)
        self.assertEqual(result["created_goals"], len(INITIAL_ROADMAP))
        self.assertEqual(result["created_steps"], sum(len(row["steps"]) for row in INITIAL_ROADMAP))
        self.assertEqual(len(self.goals.list_goals()), len(INITIAL_ROADMAP))
        for goal in self.goals.list_goals():
            steps = goal["steps"]
            self.assertTrue(steps)
            self.assertTrue(all(step["status"] == "pending" for step in steps))
            known = {step["id"] for step in steps}
            self.assertTrue(all(set(step["depends_on"]).issubset(known) for step in steps))

    def test_seed_is_idempotent(self):
        first = seed_initial_roadmap(self.goals)
        second = seed_initial_roadmap(self.goals)
        self.assertEqual(first["created_goals"], len(INITIAL_ROADMAP))
        self.assertEqual(first["created_steps"], sum(len(row["steps"]) for row in INITIAL_ROADMAP))
        self.assertEqual(second["created_goals"], 0)
        self.assertEqual(second["created_steps"], 0)

    def test_preserves_existing_goal_progress_and_unrelated_goals(self):
        existing = self.goals.create_goal(INITIAL_ROADMAP[0]["title"], "Descrição customizada")
        step = self.goals.add_step(existing["id"], INITIAL_ROADMAP[0]["steps"][0][0])
        self.goals.set_step_status(existing["id"], step["id"], "in_progress")
        unrelated = self.goals.create_goal("Objetivo do operador")
        seed_initial_roadmap(self.goals)
        stored = self.goals.get_goal(existing["id"])
        self.assertEqual(stored["description"], "Descrição customizada")
        self.assertEqual(stored["steps"][0]["status"], "in_progress")
        self.assertIsNotNone(self.goals.get_goal(unrelated["id"]))


if __name__ == "__main__":
    unittest.main()
