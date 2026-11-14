"""Memória episódica persistente com recuperação contextual e feedback explícito."""
from array import array
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import uuid

from .utils import cosine, load_json, normalize, save_json, tokenize


class EpisodicMemory:
    """Armazena interações como experiências; não transforma episódios em fatos."""

    def __init__(self, path: Path, max_items=2000, *,
                 embedding_cache_size=None, passage_batch_size=8):
        self.path = Path(path)
        self.max_items = max(1, int(max_items))
        if embedding_cache_size is None:
            embedding_cache_size = self.max_items
        self.embedding_cache_size = max(0, int(embedding_cache_size))
        self.passage_batch_size = max(1, min(32, int(passage_batch_size)))

        self._embedding_cache = OrderedDict()
        self._cache_encoder_ref = None
        self._cache_encoder_fingerprint = None
        self._embedding_cache_hits = 0
        self._embedding_cache_misses = 0
        self._embedding_cache_evictions = 0
        self._encoded_passages = 0
        self._passage_encoder_calls = 0

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

    @staticmethod
    def _passage_text(item):
        return (
            str(item.get("user_input", "") or "")
            + " "
            + str(item.get("assistant_output", "") or "")
        )

    @staticmethod
    def _episode_cache_identity(item, passage):
        content_fingerprint = hashlib.sha256(
            passage.encode("utf-8")
        ).hexdigest()
        episode_id = str(item.get("id") or "").strip()
        identity = (
            "id:" + episode_id
            if episode_id
            else "legacy:" + content_fingerprint
        )
        return identity, content_fingerprint

    @staticmethod
    def _encoder_fingerprint(encoder):
        model = getattr(encoder, "_model", None)
        vocab = getattr(encoder, "vocab", None)
        vocab_size = len(vocab) if isinstance(vocab, dict) else None
        attributes = (
            type(encoder).__module__,
            type(encoder).__qualname__,
            id(encoder),
            getattr(encoder, "dimensions", None),
            getattr(encoder, "updates", None),
            getattr(encoder, "semantic_weight", None),
            getattr(encoder, "model_path", None),
            getattr(encoder, "device", None),
            getattr(encoder, "local_files_only", None),
            getattr(encoder, "max_seq_length", None),
            vocab_size,
            id(model) if model is not None else None,
        )
        return hashlib.sha256(repr(attributes).encode("utf-8")).hexdigest()

    def _prune_embedding_cache(self, valid_entries=None):
        if not self._embedding_cache:
            return
        if valid_entries is None:
            valid_entries = set()
            for item in self.items:
                passage = self._passage_text(item)
                valid_entries.add(self._episode_cache_identity(item, passage))

        for key in list(self._embedding_cache):
            _, identity, content_fingerprint = key
            if (identity, content_fingerprint) not in valid_entries:
                del self._embedding_cache[key]
                self._embedding_cache_evictions += 1

    def _prepare_embedding_cache(self, encoder):
        fingerprint = self._encoder_fingerprint(encoder)
        if (
            encoder is not self._cache_encoder_ref
            or fingerprint != self._cache_encoder_fingerprint
        ):
            self._embedding_cache_evictions += len(self._embedding_cache)
            self._embedding_cache.clear()
            self._cache_encoder_ref = encoder
            self._cache_encoder_fingerprint = fingerprint
        return fingerprint

    def _cache_get(self, key):
        if key not in self._embedding_cache:
            self._embedding_cache_misses += 1
            return None
        self._embedding_cache.move_to_end(key)
        self._embedding_cache_hits += 1
        return self._embedding_cache[key]

    def _cache_put(self, key, vector):
        if self.embedding_cache_size <= 0:
            return
        self._embedding_cache[key] = array("f", (float(value) for value in vector))
        self._embedding_cache.move_to_end(key)
        while len(self._embedding_cache) > self.embedding_cache_size:
            self._embedding_cache.popitem(last=False)
            self._embedding_cache_evictions += 1

    def _encode_missing_passages(self, encoder, texts):
        encode_passages = getattr(encoder, "encode_passages", None)
        if callable(encode_passages):
            vectors = list(encode_passages(
                texts, batch_size=self.passage_batch_size
            ))
            self._passage_encoder_calls += 1
        else:
            encode_passage = getattr(encoder, "encode_passage", None)
            if callable(encode_passage):
                vectors = [encode_passage(text) for text in texts]
            else:
                vectors = [encoder.encode(text) for text in texts]
            self._passage_encoder_calls += len(texts)

        if len(vectors) != len(texts):
            raise ValueError(
                "O encoder retornou uma quantidade de embeddings diferente da quantidade de passagens."
            )
        self._encoded_passages += len(texts)
        return vectors

    def _trim_and_save(self):
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items:]
            save_json(self.path, self.items)
            self._prune_embedding_cache()

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
        save_json(self.path, self.items)
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

    def recall(self, query, encoder=None, limit=5, *, min_score=0.05,
               exclude_user_inputs=None):
        query = self._text(query, "query", 12000)
        limit = int(limit)
        if not query or limit <= 0:
            return []
        query_tokens = set(tokenize(query))
        query_vector = None
        encoder_fingerprint = None
        if encoder is not None:
            encode_query = getattr(encoder, "encode_query", None)
            query_vector = encode_query(query) if callable(encode_query) else encoder.encode(query)
            encoder_fingerprint = self._prepare_embedding_cache(encoder)

        now = datetime.now(timezone.utc)
        excluded = {normalize(text) for text in (exclude_user_inputs or [])}
        ranked = []
        pending = []
        prepared = []
        valid_entries = set()

        for item in self.items:
            passage_text = None
            cache_key = None
            if encoder is not None and query_vector is not None:
                passage_text = self._passage_text(item)
                identity, content_fingerprint = self._episode_cache_identity(
                    item, passage_text
                )
                valid_entries.add((identity, content_fingerprint))
                cache_key = (
                    encoder_fingerprint, identity, content_fingerprint
                )

            if normalize(item.get("user_input", "")) in excluded:
                continue
            searchable = " ".join([
                item.get("user_input", ""), item.get("assistant_output", ""),
                " ".join(item.get("tags", [])), item.get("outcome", ""),
            ])
            tokens = set(tokenize(searchable))
            lexical = len(query_tokens & tokens) / max(1, len(query_tokens | tokens))
            prepared.append((item, lexical, passage_text, cache_key))

        if encoder is not None and query_vector is not None:
            self._prune_embedding_cache(valid_entries)

        def add_ranked(item, lexical, passage_vector):
            semantic = 0.0
            if encoder is not None and query_vector is not None:
                semantic = max(0.0, min(1.0, cosine(query_vector, passage_vector)))
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

        def flush_pending():
            if not pending:
                return
            vectors = self._encode_missing_passages(
                encoder, [entry[2] for entry in pending]
            )
            for (item, lexical, passage_text, key), vector in zip(pending, vectors):
                self._cache_put(key, vector)
                add_ranked(item, lexical, vector)
            pending.clear()

        for item, lexical, passage_text, cache_key in prepared:
            if encoder is None or query_vector is None:
                add_ranked(item, lexical, [])
                continue

            passage_vector = self._cache_get(cache_key)
            if passage_vector is not None:
                add_ranked(item, lexical, passage_vector)
                continue

            pending.append((item, lexical, passage_text, cache_key))
            if len(pending) >= self.passage_batch_size:
                flush_pending()

        flush_pending()
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
            "episodic_embedding_cache_entries": len(self._embedding_cache),
            "episodic_embedding_cache_limit": self.embedding_cache_size,
            "episodic_embedding_cache_hits": self._embedding_cache_hits,
            "episodic_embedding_cache_misses": self._embedding_cache_misses,
            "episodic_embedding_cache_evictions": self._embedding_cache_evictions,
            "episodic_encoded_passages": self._encoded_passages,
            "episodic_passage_encoder_calls": self._passage_encoder_calls,
        }
