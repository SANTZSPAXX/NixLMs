"""Deterministic bridge from persistent goals to policy-governed autonomy.

This planner selects only user-authored, dependency-ready goal steps. It does
not invent goals, mark work complete, call an LLM, or perform external I/O.
"""
import threading


class AutonomyPlanner:
    """Select and start a bounded number of ready goal steps."""

    ACTION_NAME = "goal.start_step"

    def __init__(self, goal_manager, autonomy_engine, *, max_actions_per_cycle=1):
        self.goals = goal_manager
        self.engine = autonomy_engine
        self._lock = threading.RLock()
        policy_limit = autonomy_engine.policy.max_actions_per_cycle
        self.max_actions_per_cycle = max(
            1, min(int(max_actions_per_cycle), int(policy_limit), 100)
        )
        self.engine.register_action(
            self.ACTION_NAME,
            self._start_step,
            scope="internal",
            risk="low",
            description="Move one dependency-ready, user-defined goal step to in_progress",
        )

    def preview(self, limit=None):
        """Return deterministic proposals without changing persistent state."""
        count = self.max_actions_per_cycle if limit is None else max(
            0, min(int(limit), self.max_actions_per_cycle)
        )
        if count <= 0:
            return []
        proposals = []
        with self._lock:
            for goal in self.goals.list_goals(status="active"):
                for step in self.goals.next_actions(goal["id"]):
                    proposals.append({
                        "action": self.ACTION_NAME,
                        "payload": {
                            "goal_id": goal["id"],
                            "step_id": step["id"],
                        },
                        "goal_title": goal.get("title", ""),
                        "step_title": step.get("title", ""),
                    })
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
        return {
            "goal_id": goal_id,
            "step_id": step_id,
            "status": step["status"],
            "transition": "pending_to_in_progress",
        }

    def run_cycle(self, limit=None):
        """Execute only bounded internal transitions through AutonomyEngine."""
        with self._lock:
            proposals = self.preview(limit=limit)
            results = self.engine.run_cycle(proposals)
            return {
                "proposed": len(proposals),
                "processed": len(results),
                "results": results,
            }

    def status(self):
        goals = self.goals.list_goals(status="active")
        ready = sum(len(self.goals.next_actions(goal["id"])) for goal in goals)
        return {
            "enabled": True,
            "max_actions_per_cycle": self.max_actions_per_cycle,
            "active_goals": len(goals),
            "ready_steps": ready,
            "next_actions": self.preview(),
            "execution_scope": "internal",
            "requires_approval": False,
            "completion_is_automatic": False,
        }
