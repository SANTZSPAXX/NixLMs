"""Modelo de mundo local com fatos tipados, proveniência e confiança.

O módulo armazena afirmações; não presume que uma afirmação seja verdadeira.
Conflitos são expostos para revisão e nunca resolvidos automaticamente.
"""
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .utils import load_json, normalize, save_json, tokenize


class WorldModel:
    def __init__(self, path, max_facts=5000):
        self.path = Path(path)
        self.max_facts = max(1, int(max_facts))
        data = load_json(self.path, {"facts": []})
        raw = data.get("facts", []) if isinstance(data, dict) else []
        self.facts = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []

    @staticmethod
    def _key(subject, predicate, obj):
        return tuple(normalize(value) for value in (subject, predicate, obj))

    def assert_fact(self, subject, predicate, obj, confidence=1.0, source="user"):
        subject, predicate, obj = (str(value).strip() for value in (subject, predicate, obj))
        source = str(source).strip()
        if not subject or not predicate or not obj:
            raise ValueError("subject, predicate e object são obrigatórios.")
        if not source:
            raise ValueError("source não pode ficar vazio.")
        confidence = float(confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence deve estar entre 0 e 1.")
        key = self._key(subject, predicate, obj)
        now = datetime.now(timezone.utc).isoformat()
        for fact in reversed(self.facts):
            if self._key(fact.get("subject", ""), fact.get("predicate", ""),
                         fact.get("object", "")) == key:
                fact.update({"subject": subject, "predicate": predicate, "object": obj,
                             "confidence": confidence, "source": source,
                             "updated_at": now})
                self._save()
                return deepcopy(fact)
        fact = {"subject": subject, "predicate": predicate, "object": obj,
                "confidence": confidence, "source": source, "created_at": now}
        self.facts.append(fact)
        self.facts = self.facts[-self.max_facts:]
        self._save()
        return deepcopy(fact)

    def query(self, subject=None, predicate=None, obj=None, limit=100):
        limit = max(0, int(limit))
        if not limit:
            return []
        filters = [(field, normalize(value)) for field, value in (
            ("subject", subject), ("predicate", predicate), ("object", obj)
        ) if value is not None]
        matches = []
        for fact in self.facts:
            if all(normalize(fact.get(field, "")) == expected
                   for field, expected in filters):
                matches.append(deepcopy(fact))
        return matches[-limit:]

    def search(self, text, limit=10):
        terms = set(tokenize(text))
        limit = max(0, int(limit))
        if not terms or not limit:
            return []
        ranked = []
        for fact in self.facts:
            content = " ".join(str(fact.get(field, "")) for field in
                               ("subject", "predicate", "object"))
            overlap = len(terms & set(tokenize(content))) / len(terms)
            if overlap:
                score = overlap + 0.01 * float(fact.get("confidence", 0.0))
                ranked.append((score, fact))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [deepcopy(fact) for _, fact in ranked[:limit]]

    def possible_conflicts(self, subject, predicate):
        rows = self.query(subject=subject, predicate=predicate, limit=self.max_facts)
        objects = {normalize(fact.get("object", "")) for fact in rows}
        return [[deepcopy(fact) for fact in rows]] if len(objects) > 1 else []

    def _save(self):
        save_json(self.path, {"facts": self.facts})

    def stats(self):
        entities = {normalize(f.get(field, "")) for f in self.facts
                    for field in ("subject", "object") if f.get(field)}
        predicates = {}
        for fact in self.facts:
            key = (normalize(fact.get("subject", "")),
                   normalize(fact.get("predicate", "")))
            predicates.setdefault(key, set()).add(normalize(fact.get("object", "")))
        conflicts = sum(len(objects) > 1 for objects in predicates.values())
        return {"facts": len(self.facts), "entities": len(entities),
                "possible_conflict_groups": conflicts}
