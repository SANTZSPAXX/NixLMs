from datetime import datetime, timezone
from pathlib import Path
from .utils import load_json, save_json, cosine, tokenize, normalize


class MemorySystem:
    def __init__(self, data_dir: Path, max_items=2000):
        self.data_dir = Path(data_dir)
        self.max_items = max(1, int(max_items))
        self.knowledge_path = self.data_dir / "knowledge.json"
        self.episodes_path = self.data_dir / "episodes.json"
        self.knowledge = load_json(self.knowledge_path, [])
        self.episodes = load_json(self.episodes_path, [])
        if not isinstance(self.knowledge, list):
            self.knowledge = []
        else:
            self.knowledge = [item for item in self.knowledge if isinstance(item, dict)]
        if not isinstance(self.episodes, list):
            self.episodes = []
        else:
            self.episodes = [item for item in self.episodes if isinstance(item, dict)]
        self.working = []
        self._embedding_cache = {}

    def remember(self, question, answer, tags=None):
        question, answer = str(question).strip(), str(answer).strip()
        if not question or not answer:
            raise ValueError("Pergunta e resposta não podem ficar vazias.")
        key = normalize(question)
        now = datetime.now(timezone.utc).isoformat()
        # Atualiza a entrada existente em vez de criar duplicatas em cada época.
        for item in reversed(self.knowledge):
            if normalize(item.get("question", "")) == key:
                item.update({"question": question, "answer": answer,
                             "tags": list(tags or item.get("tags", [])),
                             "updated_at": now})
                save_json(self.knowledge_path, self.knowledge)
                return item
        item = {"question": question, "answer": answer, "tags": list(tags or []),
                "created_at": now}
        self.knowledge.append(item)
        self.knowledge = self.knowledge[-self.max_items:]
        save_json(self.knowledge_path, self.knowledge)
        return item

    def recall(self, query, encoder, network=None, limit=5):
        """Busca híbrida; não executa nem modifica a rede neural durante leitura."""
        if limit <= 0:
            return []
        qtokens = set(tokenize(query))
        qvec = encoder.encode(query)
        ranked = []
        for item in self.knowledge:
            text = item.get("question", "")
            tokens = set(tokenize(text))
            lexical = len(qtokens & tokens) / max(1, len(qtokens | tokens))
            version = getattr(encoder, "updates", 0)
            cache_key = normalize(text)
            cached = self._embedding_cache.get(cache_key)
            if cached is None or cached[0] != version:
                vector = encoder.encode(text)
                self._embedding_cache[cache_key] = (version, vector)
            else:
                vector = cached[1]
            if len(self._embedding_cache) > self.max_items * 2:
                self._embedding_cache.clear()
            semantic = max(0.0, cosine(qvec, vector))
            # No início, embeddings pouco treinados recebem peso menor. A semântica
            # assume gradualmente a recuperação conforme pares contrastivos são aprendidos.
            semantic_weight = .35 + .50 * min(1.0, getattr(encoder, "updates", 0) / 30.0)
            score = semantic_weight * semantic + (1.0 - semantic_weight) * lexical
            ranked.append((score, item))
        return sorted(ranked, key=lambda pair: pair[0], reverse=True)[:limit]

    def add_episode(self, role, content):
        self.episodes.append({"role": str(role), "content": str(content),
                              "timestamp": datetime.now(timezone.utc).isoformat()})
        self.episodes = self.episodes[-self.max_items:]
        save_json(self.episodes_path, self.episodes)

    def stats(self):
        return {"semantic_items": len(self.knowledge),
                "episodic_items": len(self.episodes),
                "working_items": len(self.working)}
