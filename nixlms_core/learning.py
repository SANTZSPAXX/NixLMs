"""Importação, treinamento contrastivo e avaliação sem vazamento de dados."""
import json
import random
from pathlib import Path
from .utils import save_json, load_json, normalize, tokenize, cosine


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
                if row.get("split", "train") != split:
                    raise ValueError("A mesma pergunta não pode aparecer em train e test.")
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

    def evaluate(self, threshold=0.25, ks=(1, 3, 5)):
        """Benchmark reproduzível de recuperação e classificação contrastiva.

        A avaliação usa somente registros marcados como test. Os canais lexical,
        semântico e híbrido são reportados separadamente para tornar comparações
        futuras do encoder verificáveis.
        """
        threshold = float(threshold)
        if not -1.0 <= threshold <= 1.0:
            raise ValueError("threshold deve estar entre -1 e 1.")
        ks = tuple(sorted({int(k) for k in ks}))
        if not ks or ks[0] < 1:
            raise ValueError("ks deve conter inteiros positivos.")

        rows = self.dataset.load()
        qa_test = [r for r in rows if r.get("type", "qa") == "qa" and r.get("split") == "test"]
        pair_test = [r for r in rows if r.get("type") == "pair" and r.get("split") == "test"]

        # Avalia os mesmos candidatos com três estratégias, sem alterar memória.
        candidates = list(self.agent.memory.knowledge)
        retrieval = {"samples": len(qa_test), "candidate_count": len(candidates), "metrics": {}}
        channels = ("lexical", "semantic", "hybrid")
        reciprocal = {name: 0.0 for name in channels}
        hits = {name: {k: 0 for k in ks} for name in channels}
        for row in qa_test:
            query = row["question"]
            q_tokens = set(tokenize(query))
            q_vector = self.agent.encoder.encode(query)
            scored = {name: [] for name in channels}
            for item in candidates:
                candidate_text = str(item.get("question", ""))
                c_tokens = set(tokenize(candidate_text))
                union = q_tokens | c_tokens
                lexical = len(q_tokens & c_tokens) / len(union) if union else 0.0
                semantic = max(-1.0, min(1.0, cosine(
                    q_vector, self.agent.encoder.encode(candidate_text)
                )))
                weight = 0.35 + 0.50 * min(
                    1.0, getattr(self.agent.encoder, "updates", 0) / 30.0
                )
                values = {
                    "lexical": lexical,
                    "semantic": semantic,
                    "hybrid": weight * semantic + (1.0 - weight) * lexical,
                }
                for name, score in values.items():
                    scored[name].append((score, item))
            for name in channels:
                ranked = sorted(scored[name], key=lambda pair: pair[0], reverse=True)
                rank = next((i + 1 for i, (_, item) in enumerate(ranked)
                             if item.get("answer") == row["answer"]), None)
                if rank is not None:
                    reciprocal[name] += 1.0 / rank
                    for k in ks:
                        hits[name][k] += int(rank <= k)

        if qa_test:
            retrieval["metrics"] = {
                name: {
                    "mrr": reciprocal[name] / len(qa_test),
                    "recall_at_k": {str(k): hits[name][k] / len(qa_test) for k in ks},
                } for name in channels
            }
        else:
            retrieval["metrics"] = {
                name: {"mrr": None, "recall_at_k": {str(k): None for k in ks}}
                for name in channels
            }

        similarities = []
        tp = fp = tn = fn = 0
        positive, negative = [], []
        for pair in pair_test:
            similarity = cosine(
                self.agent.encoder.encode(pair["text_a"]),
                self.agent.encoder.encode(pair["text_b"])
            )
            label = int(pair.get("label", 1))
            predicted = int(similarity >= threshold)
            similarities.append(similarity)
            (positive if label == 1 else negative).append(similarity)
            if predicted and label:
                tp += 1
            elif predicted and not label:
                fp += 1
            elif not predicted and not label:
                tn += 1
            else:
                fn += 1

        total = len(pair_test)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall_score = tp / (tp + fn) if tp + fn else 0.0
        specificity = tn / (tn + fp) if tn + fp else 0.0
        f1 = (2 * precision * recall_score / (precision + recall_score)
              if precision + recall_score else 0.0)
        contrastive = {
            "samples": total,
            "accuracy": (tp + tn) / total if total else None,
            "precision": precision if total else None,
            "recall": recall_score if total else None,
            "f1": f1 if total else None,
            "specificity": specificity if total else None,
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "mean_positive_similarity": sum(positive) / len(positive) if positive else None,
            "mean_negative_similarity": sum(negative) / len(negative) if negative else None,
            "decision_threshold": threshold,
        }
        return {
            "retrieval": retrieval,
            "contrastive": contrastive,
            "protocol": {
                "test_qa_samples": len(qa_test),
                "test_pair_samples": len(pair_test),
                "candidate_source": "memory.knowledge",
                "channels": list(channels),
                "ks": list(ks),
                "threshold": threshold,
                "test_data_used_for_training": False,
            },
            "note": "Métricas de recuperação e classificação são separadas; "
                    "o benchmark não prova compreensão semântica geral.",
        }
