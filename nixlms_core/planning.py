"""Gestão persistente de objetivos e etapas; não executa ações externas."""
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .utils import load_json, save_json


class GoalManager:
    VALID_STEP_STATUSES = {"pending", "in_progress", "completed", "cancelled"}

    def __init__(self, path, max_goals=500):
        self.path = Path(path)
        self.max_goals = max(1, int(max_goals))
        data = load_json(self.path, {"goals": []})
        raw = data.get("goals", []) if isinstance(data, dict) else []
        self.goals = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _save(self):
        save_json(self.path, {"goals": self.goals})

    def _find_goal(self, goal_id):
        for goal in self.goals:
            if goal.get("id") == goal_id:
                return goal
        raise ValueError("Objetivo não encontrado.")

    @staticmethod
    def _refresh_goal_status(goal):
        steps = goal.get("steps", [])
        if steps and all(step.get("status") == "completed" for step in steps):
            goal["status"] = "completed"
        elif steps and all(step.get("status") == "cancelled" for step in steps):
            goal["status"] = "cancelled"
        else:
            goal["status"] = "active"

    def create_goal(self, title, description=""):
        title, description = str(title).strip(), str(description).strip()
        if not title:
            raise ValueError("O título do objetivo é obrigatório.")
        if len(self.goals) >= self.max_goals:
            raise ValueError("Limite de objetivos atingido.")
        now = self._now()
        goal = {"id": "goal-" + uuid.uuid4().hex[:12], "title": title,
                "description": description, "status": "active", "steps": [],
                "created_at": now, "updated_at": now}
        self.goals.append(goal)
        self._save()
        return deepcopy(goal)

    def add_step(self, goal_id, title, depends_on=None):
        goal = self._find_goal(goal_id)
        title = str(title).strip()
        if not title:
            raise ValueError("O título da etapa é obrigatório.")
        dependencies = list(dict.fromkeys(str(item) for item in (depends_on or [])))
        known = {step.get("id") for step in goal.get("steps", [])}
        if any(item not in known for item in dependencies):
            raise ValueError("Toda dependência deve identificar uma etapa existente do objetivo.")
        step = {"id": "step-" + uuid.uuid4().hex[:12], "title": title,
                "status": "pending", "depends_on": dependencies,
                "created_at": self._now(), "updated_at": self._now()}
        goal.setdefault("steps", []).append(step)
        goal["updated_at"] = self._now()
        self._refresh_goal_status(goal)
        self._save()
        return deepcopy(step)

    def set_step_status(self, goal_id, step_id, status):
        if status not in self.VALID_STEP_STATUSES:
            raise ValueError("Status inválido para etapa.")
        goal = self._find_goal(goal_id)
        step = next((item for item in goal.get("steps", [])
                     if item.get("id") == step_id), None)
        if step is None:
            raise ValueError("Etapa não encontrada.")
        if status in {"in_progress", "completed"}:
            dependencies = set(step.get("depends_on", []))
            completed = {item.get("id") for item in goal.get("steps", [])
                         if item.get("status") == "completed"}
            if not dependencies.issubset(completed):
                raise ValueError("A etapa possui dependências ainda não concluídas.")
        step["status"] = status
        step["updated_at"] = self._now()
        goal["updated_at"] = self._now()
        self._refresh_goal_status(goal)
        self._save()
        return deepcopy(step)

    def get_goal(self, goal_id):
        for goal in self.goals:
            if goal.get("id") == goal_id:
                return deepcopy(goal)
        return None

    def list_goals(self, status=None):
        rows = [goal for goal in self.goals
                if status is None or goal.get("status") == status]
        return [deepcopy(goal) for goal in rows]

    def next_actions(self, goal_id):
        goal = self._find_goal(goal_id)
        completed = {step.get("id") for step in goal.get("steps", [])
                     if step.get("status") == "completed"}
        ready = [step for step in goal.get("steps", [])
                 if step.get("status") == "pending"
                 and set(step.get("depends_on", [])).issubset(completed)]
        return [deepcopy(step) for step in ready]

    def active_context(self, limit=5):
        result = []
        for goal in self.goals:
            if goal.get("status") != "active":
                continue
            result.append({"id": goal.get("id"), "title": goal.get("title"),
                           "next_steps": [step.get("title") for step in
                                          self.next_actions(goal.get("id"))[:3]]})
            if len(result) >= max(0, int(limit)):
                break
        return result

    def stats(self):
        steps = [step for goal in self.goals for step in goal.get("steps", [])]
        return {"goals": len(self.goals),
                "active_goals": sum(goal.get("status") == "active" for goal in self.goals),
                "steps": len(steps),
                "ready_steps": sum(len(self.next_actions(goal.get("id")))
                                   for goal in self.goals)}
