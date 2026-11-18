import tempfile
import unittest
from pathlib import Path

from nixlms_core.simulation import WorldSimulator
from nixlms_core.world_model import WorldModel
from nixlms_core import NixLMsNeuralCore


class WorldSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.world = WorldModel(Path(self.tmp.name) / "world.json")
        self.world.assert_fact("NixLMs", "runs_on", "CPU", source="test")
        self.simulator = WorldSimulator(self.world)

    def tearDown(self):
        self.tmp.cleanup()

    def test_simulation_is_counterfactual_and_does_not_persist(self):
        before = list(self.world.facts)
        result = self.simulator.simulate_fact("NixLMs", "runs_on", "GPU")
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["persisted"])
        self.assertEqual(result["external_actions"], 0)
        self.assertEqual(len(result["new_conflicts"]), 1)
        self.assertEqual(self.world.facts, before)

    def test_replace_changes_only_simulated_copy(self):
        result = self.simulator.simulate([{
            "action": "replace",
            "subject": "NixLMs",
            "predicate": "runs_on",
            "object": "CPU",
            "source": "scenario",
        }])
        self.assertEqual(result["result_conflicts"], [])
        self.assertEqual(self.world.query("NixLMs", "runs_on")[0]["object"], "CPU")

    def test_exact_duplicate_updates_hypothetical_evidence(self):
        result = self.simulator.simulate_fact(
            "NixLMs", "runs_on", "CPU", confidence=0.7
        )
        self.assertEqual(result["result_fact_count"], 1)
        self.assertEqual(result["facts_preview"][-1]["confidence"], 0.7)
        self.assertTrue(result["facts_preview"][-1]["hypothetical"])

    def test_rejects_invalid_changes_and_limits(self):
        with self.assertRaises(ValueError):
            self.simulator.simulate([])
        with self.assertRaises(ValueError):
            self.simulator.simulate([{"subject": "x", "predicate": "", "object": "y"}])
        with self.assertRaises(ValueError):
            self.simulator.simulate([{
                "subject": "x", "predicate": "p", "object": "y", "confidence": 2
            }])
        with self.assertRaises(ValueError):
            self.simulator.simulate([
                {"subject": "x", "predicate": "p", "object": str(i)}
                for i in range(self.simulator.MAX_CHANGES + 1)
            ])


    def test_neural_core_exposes_simulator_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = NixLMsNeuralCore(Path(tmp))
            status = ai.status()
            self.assertTrue(status["simulation"]["enabled"])
            self.assertFalse(status["simulation"]["persists_results"])

    def test_simulation_identifier_is_deterministic(self):
        change = [{"subject": "x", "predicate": "p", "object": "y"}]
        self.assertEqual(
            self.simulator.simulate(change)["simulation_id"],
            self.simulator.simulate(change)["simulation_id"],
        )


if __name__ == "__main__":
    unittest.main()
