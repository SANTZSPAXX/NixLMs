"""Simulação contrafactual determinística e sem efeitos colaterais.

O simulador trabalha sobre uma cópia dos fatos conhecidos. Ele não grava no
WorldModel, não executa ferramentas e não transforma hipóteses em conhecimento.
"""
import hashlib
import json
import math
from copy import deepcopy

from .utils import normalize


class WorldSimulator:
    MAX_CHANGES = 20

    def __init__(self, world_model):
        self.world_model = world_model

    @staticmethod
    def _conflict_groups(facts):
        grouped = {}
        for fact in facts:
            key = (
                normalize(fact.get("subject", "")),
                normalize(fact.get("predicate", "")),
            )
            grouped.setdefault(key, []).append(fact)
        conflicts = []
        for (subject, predicate), rows in grouped.items():
            objects = {normalize(row.get("object", "")) for row in rows}
            if len(objects) > 1:
                conflicts.append({
                    "subject": subject,
                    "predicate": predicate,
                    "objects": sorted(objects),
                    "fact_count": len(rows),
                })
        return sorted(conflicts, key=lambda row: (row["subject"], row["predicate"]))

    @staticmethod
    def _validate_change(change):
        if not isinstance(change, dict):
            raise ValueError("Cada alteração simulada precisa ser um objeto.")
        action = str(change.get("action", "assert")).strip().lower()
        if action not in {"assert", "replace"}:
            raise ValueError("Ação simulada precisa ser 'assert' ou 'replace'.")
        values = {
            key: str(change.get(key, "")).strip()
            for key in ("subject", "predicate", "object")
        }
        if not all(values.values()):
            raise ValueError("subject, predicate e object são obrigatórios.")
        confidence = float(change.get("confidence", 1.0))
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence deve estar entre 0 e 1.")
        source = str(change.get("source", "hypothesis")).strip() or "hypothesis"
        return {
            "action": action,
            **values,
            "confidence": confidence,
            "source": source[:1000],
        }

    def simulate(self, changes):
        """Aplica até 20 hipóteses a uma cópia e devolve diferenças e conflitos."""
        if not isinstance(changes, list) or not changes:
            raise ValueError("Informe uma lista não vazia de alterações.")
        if len(changes) > self.MAX_CHANGES:
            raise ValueError(f"Limite de {self.MAX_CHANGES} alterações por simulação.")
        validated = [self._validate_change(item) for item in changes]
        before = deepcopy(self.world_model.facts)
        after = deepcopy(before)
        before_conflicts = self._conflict_groups(before)

        for change in validated:
            subject_key = normalize(change["subject"])
            predicate_key = normalize(change["predicate"])
            object_key = normalize(change["object"])
            if change["action"] == "replace":
                after = [
                    fact for fact in after
                    if not (
                        normalize(fact.get("subject", "")) == subject_key
                        and normalize(fact.get("predicate", "")) == predicate_key
                    )
                ]
            existing = next((
                fact for fact in reversed(after)
                if normalize(fact.get("subject", "")) == subject_key
                and normalize(fact.get("predicate", "")) == predicate_key
                and normalize(fact.get("object", "")) == object_key
            ), None)
            proposed = {
                "subject": change["subject"],
                "predicate": change["predicate"],
                "object": change["object"],
                "confidence": change["confidence"],
                "source": change["source"],
                "hypothetical": True,
            }
            if existing is not None:
                existing.update(proposed)
            else:
                after.append(proposed)

        after_conflicts = self._conflict_groups(after)
        before_keys = {
            (row["subject"], row["predicate"], tuple(row["objects"]))
            for row in before_conflicts
        }
        new_conflicts = [
            row for row in after_conflicts
            if (row["subject"], row["predicate"], tuple(row["objects"])) not in before_keys
        ]
        payload = {
            "base_fact_count": len(before),
            "changes": validated,
            "result_fact_count": len(after),
            "conflicts": after_conflicts,
        }
        simulation_id = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "simulation_id": simulation_id,
            "status": "completed",
            "persisted": False,
            "external_actions": 0,
            "base_fact_count": len(before),
            "result_fact_count": len(after),
            "changes": validated,
            "existing_conflicts": before_conflicts,
            "result_conflicts": after_conflicts,
            "new_conflicts": new_conflicts,
            "facts_preview": after[-50:],
        }

    def simulate_fact(self, subject, predicate, obj, *, confidence=1.0, source="hypothesis"):
        return self.simulate([{
            "action": "assert",
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "confidence": confidence,
            "source": source,
        }])

    def status(self):
        return {
            "enabled": True,
            "mode": "deterministic_counterfactual",
            "max_changes_per_simulation": self.MAX_CHANGES,
            "persists_results": False,
            "executes_external_actions": False,
            "known_facts": len(self.world_model.facts),
        }
