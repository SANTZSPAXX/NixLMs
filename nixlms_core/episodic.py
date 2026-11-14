"""Memória episódica persistente com recuperação contextual e feedback explícito."""
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .utils import cosine, load_json, normalize, save_json, tokenize


class EpisodicMemory:
    """Armazena interações como experiências; não transforma episódios em fatos."""

    def __init__(self, path: Path, max_items=2000):
        self.path = Path(path)
        self.max_items = max(1, int(max_items))
        raw = load_json(self.path, [])
        self.items = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        self._trim_and_save()

    @staticmethod
    def _text(value, field, limit=12000, required=False):
        text = str(value or "").strip()
        if required and not text:
            raise ValueError(f"{field} não pode ficar vazio.")
        if len(text) > limit:
            raise ValueError(f"{field} excede o limite de {limit} caracteres.")
        return text

    def _trim_and_save(self):
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items:]
            save_json(self.path, self.items)

    def record(self, user_input, assistant_output, *, context=None, outcome=None,
               source="unknown", importance=0.5, tags=None):
        user_input = self._text(user_input, "user_input", required=True)
        assistant_output = self._text(assistant_output, "assistant_output", required=True)
        if not isinstance(context, (dict, list, type(None))):
            raise ValueError("context deve ser um objeto JSON, lista ou None.")
        try:
            importance = float(importance)
        except (TypeError, ValueError) as exc:
            raise ValueError("importance deve ser numérico.") from exc
        if not 0.0 <= importance <= 1.0:
            raise ValueError("importance deve estar entre 0 e 1.")
        if tags is not None and (not isinstance(tags, list) or not all(isinstance(x, str) for x in tags)):
            raise ValueError("tags deve ser uma lista de textos.")
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": uuid.uuid4().hex,
            "timestamp": now,
            "user_input": user_input,
            "assistant_output": assistant_output,
            "context": context or {},
            "outcome": self._text(outcome, "outcome", 4000),
            "source": self._text(source, "source", 120),
            "importance": importance,
            "feedback": None,
            "tags": list(tags or []),
        }
        self.items.append(item)
        self._trim_and_save()
        return item

    def set_feedback(self, question, positive, *, episode_id=None):
        question_key = normalize(question)
        if not question_key and not episode_id:
            return None
        for item in reversed(self.items):
            matches_id = episode_id is not None and item.get("id") == episode_id
            matches_question = (
                episode_id is None
                and normalize(item.get("user_input", "")) == question_key
            )
            if matches_id or matches_question:
                item["feedback"] = "positive" if bool(positive) else "negative"
                item["feedback_at"] = datetime.now(timezone.utc).isoformat()
                save_json(self.path, self.items)
                return item
        return None

    def recall(self, query, encoder=None, limit=5, *, min_score=0.05):
        query = self._text(query, "query", 12000)
        limit = int(limit)
        if not query or limit <= 0:
            return []
        query_tokens = set(tokenize(query))
        query_vector = encoder.encode_query(query) if encoder is not None else None
        now = datetime.now(timezone.utc)
        ranked = []
        for item in self.items:
            searchable = " ".join([
                item.get("user_input", ""), item.get("assistant_output", ""),
                " ".join(item.get("tags", [])), item.get("outcome", ""),
            ])
            tokens = set(tokenize(searchable))
            lexical = len(query_tokens & tokens) / max(1, len(query_tokens | tokens))
            semantic = 0.0
            if encoder is not None and query_vector is not None:
                text = item.get("user_input", "") + " " + item.get("assistant_output", "")
                semantic = max(0.0, min(1.0, cosine(query_vector, encoder.encode_passage(text))))
            relevance = 0.65 * semantic + 0.35 * lexical if encoder is not None else lexical
            try:
                stamp = datetime.fromisoformat(item.get("timestamp", "").replace("Z", "+00:00"))
                age_days = max(0.0, (now - stamp).total_seconds() / 86400.0)
            except (TypeError, ValueError):
                age_days = 3650.0
            recency = 0.5 ** (age_days / 30.0)
            feedback = item.get("feedback")
            feedback_factor = 1.08 if feedback == "positive" else (0.85 if feedback == "negative" else 1.0)
            importance = max(0.0, min(1.0, float(item.get("importance", 0.5))))
            score = relevance * (0.85 + 0.15 * recency) * (0.9 + 0.2 * importance) * feedback_factor
            if score >= float(min_score):
                ranked.append((score, item))
        ranked.sort(key=lambda pair: (pair[0], pair[1].get("timestamp", "")), reverse=True)
        return ranked[:limit]

    def prune(self):
        before = len(self.items)
        self._trim_and_save()
        return {"before": before, "after": len(self.items), "removed": before - len(self.items)}

    def stats(self):
        return {
            "episodic_items": len(self.items),
            "positive_feedback": sum(x.get("feedback") == "positive" for x in self.items),
            "negative_feedback": sum(x.get("feedback") == "negative" for x in self.items),
            "episodic_feedback_coverage": (
                sum(x.get("feedback") in {"positive", "negative"} for x in self.items) / len(self.items)
                if self.items else 0.0
            ),
        }
