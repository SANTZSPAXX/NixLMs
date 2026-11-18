import tempfile
import unittest
from pathlib import Path

from nixlms_core.autonomy import AutonomyEngine
from nixlms_core.autonomy_planner import AutonomyPlanner
from nixlms_core.planning import GoalManager


class AutonomyPlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.goals = GoalManager(root / "goals.json")
        self.engine = AutonomyEngine(root / "autonomy.sqlite3")
        self.planner = AutonomyPlanner(self.goals, self.engine)

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_is_read_only_and_selects_only_ready_step(self):
        goal = self.goals.create_goal("Preparar ambiente", "Tarefa definida pelo operador")
        first = self.goals.add_step(goal["id"], "Verificar dependências")
        self.goals.add_step(goal["id"], "Executar testes", depends_on=[first["id"]])
        preview = self.planner.preview()
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]["payload"]["step_id"], first["id"])
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][0]["status"], "pending")

    def test_cycle_starts_manual_step_but_does_not_claim_completion(self):
        goal = self.goals.create_goal("Auditar memória")
        step = self.goals.add_step(goal["id"], "Inspecionar consistência")
        result = self.planner.run_cycle()
        self.assertEqual(result["proposed"], 1)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["results"][0]["status"], "completed")
        self.assertEqual(result["results"][0]["result"]["status"], "in_progress")
        stored = self.goals.get_goal(goal["id"])["steps"][0]
        self.assertEqual(stored["id"], step["id"])
        self.assertEqual(stored["status"], "in_progress")

    def test_manual_step_never_marked_completed_by_scheduler(self):
        goal = self.goals.create_goal("Treinar modelo")
        self.goals.add_step(goal["id"], "Avaliar dataset")
        self.planner.run_cycle()
        self.assertEqual(self.goals.get_goal(goal["id"])["status"], "active")
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][0]["status"], "in_progress")

    def test_dependent_step_waits_until_dependency_is_completed(self):
        goal = self.goals.create_goal("Pipeline")
        first = self.goals.add_step(goal["id"], "Validar dados")
        second = self.goals.add_step(goal["id"], "Treinar", depends_on=[first["id"]])
        self.planner.run_cycle()
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][1]["status"], "pending")
        self.assertEqual(self.planner.preview(), [])
        self.goals.set_step_status(goal["id"], first["id"], "completed")
        preview = self.planner.preview()
        self.assertEqual(preview[0]["payload"]["step_id"], second["id"])

    def test_cycle_respects_configured_action_limit(self):
        goal = self.goals.create_goal("Lote")
        for index in range(4):
            self.goals.add_step(goal["id"], "Etapa " + str(index))
        result = self.planner.run_cycle(limit=1)
        self.assertEqual(result["processed"], 1)
        states = [step["status"] for step in self.goals.get_goal(goal["id"])["steps"]]
        self.assertEqual(states.count("in_progress"), 1)
        self.assertEqual(states.count("pending"), 3)

    def test_stale_or_blocked_step_cannot_be_started(self):
        goal = self.goals.create_goal("Concorrência")
        step = self.goals.add_step(goal["id"], "Executar")
        self.planner.run_cycle()
        with self.assertRaises(ValueError):
            self.planner._start_step({"goal_id": goal["id"], "step_id": step["id"]})

    def test_zero_preview_limit_returns_no_actions(self):
        goal = self.goals.create_goal("Limite zero")
        self.goals.add_step(goal["id"], "Não iniciar")
        self.assertEqual(self.planner.preview(limit=0), [])

    def test_empty_goals_produce_no_action(self):
        self.assertEqual(self.planner.run_cycle()["processed"], 0)
        self.assertEqual(self.planner.status()["ready_steps"], 0)

    def test_registered_task_executes_and_completes_only_after_verification(self):
        calls = []
        self.planner.register_task(
            "count_records",
            lambda payload: calls.append(payload["table"]) or {"count": 3},
            lambda result, payload: result.get("count") == payload["expected"],
        )
        goal = self.goals.create_goal("Auditoria de dados")
        step = self.goals.add_step(
            goal["id"], "Contar registros",
            task={"name": "count_records", "payload": {"table": "events", "expected": 3}},
        )
        preview = self.planner.preview()
        self.assertEqual(preview[0]["action"], "goal.task.count_records")
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][0]["status"], "pending")
        result = self.planner.run_cycle()
        self.assertEqual(result["verified_completed"], 1)
        stored = self.goals.get_goal(goal["id"])["steps"][0]
        self.assertEqual(stored["id"], step["id"])
        self.assertEqual(stored["status"], "completed")
        self.assertEqual(calls, ["events"])

    def test_task_that_fails_verification_is_not_completed(self):
        self.planner.register_task(
            "check_value", lambda payload: {"ok": False},
            lambda result, payload: result.get("ok") is True,
        )
        goal = self.goals.create_goal("Verificação")
        self.goals.add_step(goal["id"], "Validar resultado",
                            task={"name": "check_value", "payload": {}})
        result = self.planner.run_cycle()
        self.assertEqual(result["verified_completed"], 0)
        self.assertEqual(result["results"][0]["status"], "failed")
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][0]["status"], "failed")

    def test_unregistered_task_is_never_executed(self):
        goal = self.goals.create_goal("Não permitido")
        self.goals.add_step(goal["id"], "Executar ação desconhecida",
                            task={"name": "not_registered", "payload": {}})
        result = self.planner.run_cycle()
        self.assertEqual(result["results"][0]["result"]["status"], "in_progress")
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][0]["status"], "in_progress")

    def test_task_payload_must_be_json_and_bounded(self):
        goal = self.goals.create_goal("Payload")
        with self.assertRaises(ValueError):
            self.goals.add_step(goal["id"], "Invalida", task={"name": "x", "payload": object()})
        with self.assertRaises(ValueError):
            self.goals.add_step(goal["id"], "Grande",
                                task={"name": "x", "payload": {"data": "x" * 9000}})


    def test_non_json_task_result_is_not_marked_completed(self):
        self.planner.register_task("bad_result", lambda payload: object(),
                                   lambda result, payload: True)
        goal = self.goals.create_goal("Resultado inválido")
        self.goals.add_step(goal["id"], "Executar", task={"name": "bad_result", "payload": {}})
        result = self.planner.run_cycle()
        self.assertEqual(result["results"][0]["status"], "failed")
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][0]["status"], "failed")

    def test_oversized_task_result_is_not_marked_completed(self):
        self.engine.policy.max_result_bytes = 256
        self.planner.register_task("large_result", lambda payload: {"data": "x" * 500},
                                   lambda result, payload: True)
        goal = self.goals.create_goal("Resultado grande")
        self.goals.add_step(goal["id"], "Executar", task={"name": "large_result", "payload": {}})
        result = self.planner.run_cycle()
        self.assertEqual(result["results"][0]["status"], "failed")
        self.assertEqual(self.goals.get_goal(goal["id"])["steps"][0]["status"], "failed")

    def test_duplicate_task_registration_is_rejected(self):
        callback = lambda payload: True
        verifier = lambda result, payload: result is True
        self.planner.register_task("one", callback, verifier)
        with self.assertRaises(ValueError):
            self.planner.register_task("one", callback, verifier)


if __name__ == "__main__":
    unittest.main()
