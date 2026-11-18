"""Deterministic planner and verified executor for explicitly registered tasks.

Natural-language text is never interpreted as executable code. A task must name
an action registered by trusted application code and provide a result verifier.
"""
import json
import threading


class AutonomyPlanner:
    """Select ready goal steps and execute only allowlisted, verified tasks."""

    ACTION_NAME = "goal.start_step"
    TASK_PREFIX = "goal.task."

    def __init__(self, goal_manager, autonomy_engine, *, max_actions_per_cycle=1):
        self.goals = goal_manager
        self.engine = autonomy_engine
        self._lock = threading.RLock()
        self._tasks = {}
        policy_limit = autonomy_engine.policy.max_actions_per_cycle
        self.max_actions_per_cycle = max(
            1, min(int(max_actions_per_cycle), int(policy_limit), 100)
        )
        self.engine.register_action(
            self.ACTION_NAME,
            self._start_step,
            scope="internal",
            risk="low",
            description="Move one dependency-ready, user-defined manual step to in_progress",
        )

    def register_task(self, name, callback, verifier, *, description=""):
        """Register trusted internal work; verifier must confirm its result."""
        name = str(name).strip()
        if not name or len(name) > 80 or not callable(callback) or not callable(verifier):
            raise ValueError("Tarefa exige nome, callback e verificador válidos.")
        if name in self._tasks:
            raise ValueError("Tarefa já registrada: " + name)
        action_name = self.TASK_PREFIX + name

        def execute(payload):
            goal_id = str(payload.get("goal_id", "")).strip()
            step_id = str(payload.get("step_id", "")).strip()
            task_payload = payload.get("task_payload", {})
            if not goal_id or not step_id or not isinstance(task_payload, dict):
                raise ValueError("Contexto da tarefa inválido.")
            with self._lock:
                goal = self.goals.get_goal(goal_id)
                if goal is None:
                    raise ValueError("Objetivo não encontrado.")
                step = next((item for item in goal.get("steps", [])
                             if item.get("id") == step_id), None)
                task_spec = step.get("task") if step is not None else None
                if (step is None or step.get("status") != "pending"
                        or not isinstance(task_spec, dict)
                        or task_spec.get("name") != name):
                    raise ValueError("Etapa não está pendente ou não corresponde à tarefa.")
                ready_ids = {item["id"] for item in self.goals.next_actions(goal_id)}
                if step_id not in ready_ids:
                    raise ValueError("Etapa possui dependências não concluídas.")
                self.goals.set_step_status(goal_id, step_id, "in_progress")
            try:
                result = callback(task_payload)
                encoded_result = json.dumps(
                    result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                )
                if len(encoded_result.encode("utf-8")) > self.engine.policy.max_result_bytes:
                    raise ValueError("Resultado da tarefa excede o limite configurado.")
                if verifier(result, task_payload) is not True:
                    raise RuntimeError("Verificação da tarefa não confirmou o resultado.")
                self.goals.set_step_status(goal_id, step_id, "completed")
                return {"goal_id": goal_id, "step_id": step_id,
                        "status": "completed", "verified": True, "result": result}
            except Exception:
                current = self.goals.get_goal(goal_id)
                current_step = next((item for item in current.get("steps", [])
                                     if item.get("id") == step_id), None) if current else None
                if current_step and current_step.get("status") == "in_progress":
                    self.goals.set_step_status(goal_id, step_id, "failed")
                raise

        self.engine.register_action(
            action_name, execute, scope="internal", risk="low",
            description=str(description)[:500] or "Verified internal task: " + name,
        )
        self._tasks[name] = {"action": action_name, "description": str(description)[:500]}
        return {"name": name, "action": action_name, "scope": "internal",
                "risk": "low", "verification_required": True}

    def preview(self, limit=None):
        """Return read-only proposals for ready steps."""
        count = self.max_actions_per_cycle if limit is None else max(
            0, min(int(limit), self.max_actions_per_cycle)
        )
        if count <= 0:
            return []
        proposals = []
        with self._lock:
            for goal in self.goals.list_goals(status="active"):
                for step in self.goals.next_actions(goal["id"]):
                    task = step.get("task")
                    if isinstance(task, dict) and task.get("name") in self._tasks:
                        proposal = {
                            "action": self._tasks[task["name"]]["action"],
                            "payload": {"goal_id": goal["id"], "step_id": step["id"],
                                        "task_payload": task.get("payload", {})},
                        }
                    else:
                        proposal = {
                            "action": self.ACTION_NAME,
                            "payload": {"goal_id": goal["id"], "step_id": step["id"]},
                        }
                    proposal["goal_title"] = goal.get("title", "")
                    proposal["step_title"] = step.get("title", "")
                    proposals.append(proposal)
                    if len(proposals) >= count:
                        return proposals
        return proposals

    def _start_step(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Payload precisa ser um objeto.")
        goal_id = str(payload.get("goal_id", "")).strip()
        step_id = str(payload.get("step_id", "")).strip()
        if not goal_id or not step_id:
            raise ValueError("goal_id e step_id são obrigatórios.")
        with self._lock:
            goal = self.goals.get_goal(goal_id)
            if goal is None:
                raise ValueError("Objetivo não encontrado.")
            ready_ids = {step["id"] for step in self.goals.next_actions(goal_id)}
            if step_id not in ready_ids:
                raise ValueError("Etapa não está pendente ou possui dependências não concluídas.")
            step = self.goals.set_step_status(goal_id, step_id, "in_progress")
        return {"goal_id": goal_id, "step_id": step_id, "status": step["status"],
                "transition": "pending_to_in_progress"}

    def run_cycle(self, limit=None):
        """Execute a bounded batch; completed task steps require verifier success."""
        with self._lock:
            proposals = self.preview(limit=limit)
            results = self.engine.run_cycle(proposals)
            completed = sum(
                1 for item in results
                if item.get("status") == "completed"
                and isinstance(item.get("result"), dict)
                and item["result"].get("verified") is True
            )
            return {"proposed": len(proposals), "processed": len(results),
                    "verified_completed": completed, "results": results}

    def status(self):
        goals = self.goals.list_goals(status="active")
        ready = sum(len(self.goals.next_actions(goal["id"])) for goal in goals)
        return {
            "enabled": True,
            "max_actions_per_cycle": self.max_actions_per_cycle,
            "active_goals": len(goals),
            "ready_steps": ready,
            "registered_tasks": sorted(self._tasks),
            "next_actions": self.preview(),
            "execution_scope": "internal_allowlist_only",
            "requires_approval": False,
            "completion_requires_verifier": True,
            "manual_steps_are_not_auto_completed": True,
        }
