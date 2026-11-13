"""Importação, treinamento contrastivo e avaliação sem vazamento de dados."""
import json
import random
from pathlib import Path
from .utils import save_json, load_json, normalize


class DatasetStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        rows = load_json(self.path, [])
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def add(self, question, answer, split="train"):
        question, answer = str(question).strip(), str(answer).strip()
        if not question or not answer:
            raise ValueError("question e answer são obrigatórios.")
        if split not in {"train", "test"}:
            raise ValueError("split deve ser train ou test.")
        rows = self.load()
        key = normalize(question)
        for row in rows:
            if row.get("type", "qa") == "qa" and normalize(row.get("question", "")) == key:
                row.update({"question": question, "answer": answer, "split": split})
                save_json(self.path, rows)
                return len(rows)
        rows.append({"type": "qa", "question": question, "answer": answer, "split": split})
        save_json(self.path, rows)
        return len(rows)

    def add_pair(self, text_a, text_b, label=1, split="train"):
        text_a, text_b = str(text_a).strip(), str(text_b).strip()
        if not text_a or not text_b:
            raise ValueError("text_a e text_b são obrigatórios.")
        if split not in {"train", "test"}:
            raise ValueError("split deve ser train ou test.")
        numeric_label = float(label)
        if numeric_label not in (0.0, 1.0):
            raise ValueError("label deve ser 0 ou 1.")
        label = int(numeric_label)
        if label not in (0, 1):
            raise ValueError("label deve ser 0 ou 1.")
        rows = self.load()
        pair_key = tuple(sorted((normalize(text_a), normalize(text_b))))
        for existing in rows:
            if existing.get("type") != "pair":
                continue
            existing_key = tuple(sorted((normalize(existing.get("text_a", "")),
                                         normalize(existing.get("text_b", "")))))
            if existing_key == pair_key:
                if int(existing.get("label", 1)) != label:
                    raise ValueError("Par contrastivo já cadastrado com rótulo conflitante.")
                if existing.get("split", "train") != split:
                    raise ValueError("O mesmo par não pode aparecer em train e test.")
                existing.update({"text_a": text_a, "text_b": text_b,
                                 "label": label, "split": split})
                save_json(self.path, rows)
                return len(rows)
        rows.append({"type": "pair", "text_a": text_a, "text_b": text_b,
                     "label": label, "split": split})
        save_json(self.path, rows)
        return len(rows)

    def import_jsonl(self, source):
        added = 0
        with Path(source).expanduser().open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("cada linha deve conter um objeto JSON")
                    split = row.get("split", "train")
                    if split not in {"train", "test"}:
                        raise ValueError("split inválido")
                    if row.get("type") == "pair" or ("text_a" in row and "text_b" in row):
                        self.add_pair(row.get("text_a", ""), row.get("text_b", ""),
                                      row.get("label", 1), split)
                    elif row.get("question") and row.get("answer"):
                        self.add(row["question"], row["answer"], split)
                    else:
                        raise ValueError("registro sem campos question/answer ou text_a/text_b")
                    added += 1
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise ValueError(f"JSONL linha {line_no}: {exc}") from exc
        return added


class LearningEngine:
    def __init__(self, agent, dataset_path):
        self.agent = agent
        self.dataset = DatasetStore(dataset_path)
        self.last_training = {}

    def train(self, epochs=1, seed=42):
        epochs = int(epochs)
        if epochs < 1 or epochs > 100:
            raise ValueError("epochs deve estar entre 1 e 100.")
        rows = self.dataset.load()
        qa_rows = [r for r in rows if r.get("type", "qa") == "qa" and r.get("split", "train") == "train"]
        pairs = [r for r in rows if r.get("type") == "pair" and r.get("split", "train") == "train"]
        if not qa_rows and not pairs:
            return {"trained": 0, "epochs": 0,
                    "message": "Dataset vazio. Adicione exemplos ou pares contrastivos."}

        # QA adiciona conhecimento uma vez por treinamento; remember() é upsert,
        # portanto repetir épocas não multiplica a mesma memória.
        for row in qa_rows:
            self.agent.learn(row["question"], row["answer"],
                             remember=True, reinforce=False, add_to_dataset=False)

        corpus = []
        for row in qa_rows:
            corpus.extend([row["question"], row["answer"]])
        for pair in pairs:
            corpus.extend([pair["text_a"], pair["text_b"]])
        self.agent.encoder.fit_vocabulary(corpus)

        rng = random.Random(seed)
        losses = []
        updates = 0
        for _ in range(epochs):
            batch = list(pairs)
            rng.shuffle(batch)
            for pair in batch:
                result = self.agent.encoder.fit_pair(
                    pair["text_a"], pair["text_b"], pair.get("label", 1)
                )
                losses.append(result["loss"])
                updates += int(result["updated"])

        self.agent._save_encoder()
        self.last_training = {
            "qa_memories_upserted": len(qa_rows),
            "contrastive_pairs": len(pairs),
            "contrastive_updates": updates,
            "epochs": epochs,
            "mean_contrastive_loss": sum(losses) / len(losses) if losses else None,
            "vocabulary_size": len(self.agent.encoder.vocab),
        }
        return dict(self.last_training)

    def evaluate(self):
        rows = self.dataset.load()
        qa_test = [r for r in rows if r.get("type", "qa") == "qa" and r.get("split") == "test"]
        pair_test = [r for r in rows if r.get("type") == "pair" and r.get("split") == "test"]
        retrieval = {"samples": 0, "top5_hit_rate": None, "mrr": None}
        if qa_test:
            hits, reciprocal = 0, 0.0
            for row in qa_test:
                ranked = self.agent.memory.recall(row["question"], self.agent.encoder, limit=5)
                rank = next((i + 1 for i, (_, item) in enumerate(ranked)
                             if item.get("answer") == row["answer"]), None)
                if rank:
                    hits += 1
                    reciprocal += 1.0 / rank
            retrieval = {"samples": len(qa_test), "top5_hit_rate": hits / len(qa_test),
                         "mrr": reciprocal / len(qa_test)}

        contrastive = {"samples": 0, "accuracy": None,
                       "mean_positive_similarity": None, "mean_negative_similarity": None}
        if pair_test:
            correct, positive, negative = 0, [], []
            for pair in pair_test:
                similarity = sum(a * b for a, b in zip(
                    self.agent.encoder.encode(pair["text_a"]),
                    self.agent.encoder.encode(pair["text_b"])
                ))
                predicted = 1 if similarity >= .25 else 0
                correct += int(predicted == int(pair.get("label", 1)))
                (positive if int(pair.get("label", 1)) == 1 else negative).append(similarity)
            contrastive = {
                "samples": len(pair_test), "accuracy": correct / len(pair_test),
                "mean_positive_similarity": sum(positive) / len(positive) if positive else None,
                "mean_negative_similarity": sum(negative) / len(negative) if negative else None,
                "decision_threshold": .25
            }
        return {"retrieval": retrieval, "contrastive": contrastive,
                "note": "Avaliações separadas; pares de teste não são usados no treinamento."}
