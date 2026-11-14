"""Importação, treinamento contrastivo e avaliação sem vazamento de dados."""
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .utils import save_json, load_json, normalize, tokenize, cosine


class DatasetStore:
    VALID_SPLITS = {"train", "validation", "test"}

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        rows = load_json(self.path, [])
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    @staticmethod
    def _input_texts(row):
        if row.get("type", "qa") == "pair":
            return [row.get("text_a", ""), row.get("text_b", "")]
        return [row.get("question", "")]

    @staticmethod
    def _validate_split(split):
        if split not in DatasetStore.VALID_SPLITS:
            raise ValueError("split deve ser train, validation ou test.")

    @classmethod
    def _insert_qa(cls, rows, question, answer, split):
        question, answer = str(question).strip(), str(answer).strip()
        if not question or not answer:
            raise ValueError("question e answer são obrigatórios.")
        cls._validate_split(split)
        key = normalize(question)
        for row in rows:
            existing_split = row.get("split", "train")
            if existing_split != split and any(
                normalize(text) == key for text in cls._input_texts(row)
            ):
                raise ValueError("Texto de entrada repetido entre train e test.")
            if row.get("type", "qa") == "qa" and normalize(row.get("question", "")) == key:
                if existing_split != split:
                    raise ValueError("A mesma pergunta não pode aparecer em train e test.")
                row.update({"question": question, "answer": answer, "split": split})
                return len(rows)
        rows.append({"type": "qa", "question": question, "answer": answer, "split": split})
        return len(rows)

    @classmethod
    def _insert_pair(cls, rows, text_a, text_b, label, split):
        text_a, text_b = str(text_a).strip(), str(text_b).strip()
        if not text_a or not text_b:
            raise ValueError("text_a e text_b são obrigatórios.")
        cls._validate_split(split)
        numeric_label = float(label)
        if numeric_label not in (0.0, 1.0):
            raise ValueError("label deve ser 0 ou 1.")
        label = int(numeric_label)
        keys = {normalize(text_a), normalize(text_b)}
        for row in rows:
            existing_split = row.get("split", "train")
            if existing_split != split and keys.intersection(
                normalize(text) for text in cls._input_texts(row)
            ):
                raise ValueError("Texto de entrada repetido entre train e test.")
            if row.get("type") != "pair":
                continue
            existing_key = tuple(sorted((normalize(row.get("text_a", "")),
                                         normalize(row.get("text_b", "")))))
            pair_key = tuple(sorted((normalize(text_a), normalize(text_b))))
            if existing_key == pair_key:
                if int(row.get("label", 1)) != label:
                    raise ValueError("Par contrastivo já cadastrado com rótulo conflitante.")
                if existing_split != split:
                    raise ValueError("O mesmo par não pode aparecer em train e test.")
                row.update({"text_a": text_a, "text_b": text_b,
                            "label": label, "split": split})
                return len(rows)
        rows.append({"type": "pair", "text_a": text_a, "text_b": text_b,
                     "label": label, "split": split})
        return len(rows)

    def add(self, question, answer, split="train"):
        rows = self.load()
        result = self._insert_qa(rows, question, answer, split)
        save_json(self.path, rows)
        return result

    def add_pair(self, text_a, text_b, label=1, split="train"):
        rows = self.load()
        result = self._insert_pair(rows, text_a, text_b, label, split)
        save_json(self.path, rows)
        return result

    def audit_splits(self):
        rows = self.load()
        counts = {
            f"{kind}_{split}": 0
            for kind in ("qa", "pair")
            for split in ("train", "validation", "test")
        }
        seen = {}
        violations = []
        for index, row in enumerate(rows):
            kind = "pair" if row.get("type") == "pair" else "qa"
            split = row.get("split", "train")
            if split not in self.VALID_SPLITS:
                violations.append({"type": "invalid_split", "row": index, "split": split})
                continue
            counts[f"{kind}_{split}"] += 1
            for text in self._input_texts(row):
                key = normalize(text)
                if not key:
                    continue
                previous = seen.get(key)
                if previous and previous["split"] != split:
                    violations.append({
                        "type": "cross_split_text_overlap", "text": text,
                        "first_row": previous["row"], "second_row": index,
                        "first_split": previous["split"], "second_split": split,
                    })
                else:
                    seen.setdefault(key, {"row": index, "split": split})
        return {"valid": not violations, "counts": counts, "violations": violations}

    def import_jsonl(self, source):
        # Importação transacional: nenhuma gravação ocorre até todas as linhas
        # serem analisadas e validadas contra o dataset existente.
        rows = self.load()
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
                    if row.get("type") == "pair" or ("text_a" in row and "text_b" in row):
                        self._insert_pair(rows, row.get("text_a", ""), row.get("text_b", ""),
                                          row.get("label", 1), split)
                    elif row.get("question") and row.get("answer"):
                        self._insert_qa(rows, row["question"], row["answer"], split)
                    else:
                        raise ValueError("registro sem campos question/answer ou text_a/text_b")
                    added += 1
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise ValueError(f"JSONL linha {line_no}: {exc}") from exc
        audit = self.audit_rows(rows)
        if not audit["valid"]:
            raise ValueError("Dataset contém vazamento entre train e test.")
        save_json(self.path, rows)
        return added

    @classmethod
    def audit_rows(cls, rows):
        # Compartilha a mesma auditoria para importações ainda não persistidas.
        seen = {}
        violations = []
        counts = {
            f"{kind}_{split}": 0
            for kind in ("qa", "pair")
            for split in ("train", "validation", "test")
        }
        for index, row in enumerate(rows):
            kind = "pair" if row.get("type") == "pair" else "qa"
            split = row.get("split", "train")
            if split not in cls.VALID_SPLITS:
                violations.append({"type": "invalid_split", "row": index, "split": split})
                continue
            counts[f"{kind}_{split}"] += 1
            for text in cls._input_texts(row):
                key = normalize(text)
                if not key:
                    continue
                previous = seen.get(key)
                if previous and previous["split"] != split:
                    violations.append({
                        "type": "cross_split_text_overlap", "text": text,
                        "first_row": previous["row"], "second_row": index,
                        "first_split": previous["split"], "second_split": split,
                    })
                else:
                    seen.setdefault(key, {"row": index, "split": split})
        return {"valid": not violations, "counts": counts, "violations": violations}


class LearningEngine:
    def __init__(self, agent, dataset_path):
        self.agent = agent
        self.dataset = DatasetStore(dataset_path)
        self.last_training = {}

    def _require_clean_splits(self):
        audit = self.dataset.audit_splits()
        if not audit["valid"]:
            raise ValueError(
                "Dataset contém vazamento entre train e test; execute audit_splits() "
                "e corrija as sobreposições antes de treinar ou avaliar."
            )
        return audit

    def train(self, epochs=1, seed=42):
        epochs = int(epochs)
        if epochs < 1 or epochs > 100:
            raise ValueError("epochs deve estar entre 1 e 100.")
        self._require_clean_splits()
        rows = self.dataset.load()
        qa_rows = [r for r in rows if r.get("type", "qa") == "qa" and r.get("split", "train") == "train"]
        pairs = [r for r in rows if r.get("type") == "pair" and r.get("split", "train") == "train"]
        if not qa_rows and not pairs:
            return {"trained": 0, "epochs": 0,
                    "message": "Dataset vazio. Adicione exemplos ou pares contrastivos."}

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
        lif_losses = []
        for _ in range(epochs):
            batch = list(pairs)
            rng.shuffle(batch)
            for pair in batch:
                result = self.agent.encoder.fit_pair(
                    pair["text_a"], pair["text_b"], pair.get("label", 1)
                )
                losses.append(result["loss"])
                updates += int(result["updated"])
            # Treina a leitura depois da atualização contrastiva do encoder,
            # mantendo os alvos semânticos alinhados aos embeddings atuais.
            qa_batch = list(qa_rows)
            rng.shuffle(qa_batch)
            for row in qa_batch:
                input_vector = self.agent.encoder.encode(row["question"])
                _, hidden = self.agent.network.forward(input_vector)
                target = self.agent._compress_neural_target(
                    self.agent.encoder.encode(row["answer"])
                )
                lif_losses.append(self.agent.network.train_output(
                    hidden, target,
                    learning_rate=self.agent.config.lif_output_learning_rate
                ))

        if hasattr(self.agent, "invalidate_lif_calibration"):
            self.agent.invalidate_lif_calibration()
        self.agent._save_encoder()
        save_json(self.agent.data_dir / "neural_weights.json",
                  self.agent.network.state_dict())
        self.last_training = {
            "qa_memories_upserted": len(qa_rows),
            "contrastive_pairs": len(pairs),
            "contrastive_updates": updates,
            "epochs": epochs,
            "mean_contrastive_loss": sum(losses) / len(losses) if losses else None,
            "lif_output_updates": self.agent.network.output_updates,
            "lif_qa_examples_trained": len(qa_rows),
            "mean_lif_readout_loss": sum(lif_losses) / len(lif_losses) if lif_losses else None,
            "vocabulary_size": len(self.agent.encoder.vocab),
        }
        return dict(self.last_training)

    @staticmethod
    def _encode_query(encoder, text):
        method = getattr(encoder, "encode_query", None)
        return method(text) if callable(method) else encoder.encode(text)

    @staticmethod
    def _encode_passage(encoder, text):
        method = getattr(encoder, "encode_passage", None)
        return method(text) if callable(method) else encoder.encode(text)

    def validation_fingerprint(self):
        """Fingerprint determinístico das perguntas/respostas QA de validation."""
        rows = [
            (normalize(row.get("question", "")), normalize(row.get("answer", "")))
            for row in self.dataset.load()
            if row.get("type", "qa") == "qa" and row.get("split") == "validation"
        ]
        payload = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def calibrate_lif_threshold(self, min_validation_samples=4,
                                 min_correct_candidates=2,
                                 min_incorrect_candidates=2):
        """Calibra somente o limiar de aceitação LIF usando QA do split validation."""
        self._require_clean_splits()
        min_validation_samples = int(min_validation_samples)
        min_correct_candidates = int(min_correct_candidates)
        min_incorrect_candidates = int(min_incorrect_candidates)
        if min_validation_samples < 1 or min_correct_candidates < 1 or min_incorrect_candidates < 1:
            raise ValueError("Os mínimos de calibração devem ser inteiros positivos.")
        if self.agent.network.output_updates <= 0:
            return {"calibrated": False, "reason": "lif_readout_untrained"}

        rows = [
            row for row in self.dataset.load()
            if row.get("type", "qa") == "qa" and row.get("split") == "validation"
        ]
        if not rows:
            return {"calibrated": False, "reason": "validation_split_empty"}
        if len(rows) < min_validation_samples:
            return {
                "calibrated": False,
                "reason": "insufficient_validation_samples",
                "validation_samples": len(rows),
                "required_samples": min_validation_samples,
            }

        excluded_questions = {normalize(row.get("question", "")) for row in rows}
        cases = []
        for row in rows:
            question = str(row.get("question", "")).strip()
            expected = str(row.get("answer", "")).strip()
            self.agent.respond(
                question, use_language=False, record=False,
                excluded_questions=excluded_questions,
            )
            trace = dict(self.agent.last_trace)
            score = trace.get("lif_top_candidate_score")
            candidate_answer = str(trace.get("lif_top_candidate_answer", "")).strip()
            if score is None or not candidate_answer:
                continue
            score = float(score)
            if not math.isfinite(score):
                continue
            cases.append({
                "question": question,
                "expected_answer": expected,
                "candidate_answer": candidate_answer,
                "score": score,
                "correct": normalize(candidate_answer) == normalize(expected),
            })

        correct_count = sum(case["correct"] for case in cases)
        incorrect_count = len(cases) - correct_count
        if len(cases) < min_validation_samples:
            return {
                "calibrated": False,
                "reason": "insufficient_lif_candidates",
                "validation_samples": len(rows),
                "scored_samples": len(cases),
            }
        if correct_count < min_correct_candidates or incorrect_count < min_incorrect_candidates:
            return {
                "calibrated": False,
                "reason": "insufficient_candidate_class_balance",
                "scored_samples": len(cases),
                "positive_top1": correct_count,
                "negative_top1": incorrect_count,
                "required_positive": min_correct_candidates,
                "required_negative": min_incorrect_candidates,
            }

        scores = sorted({case["score"] for case in cases})
        thresholds = sorted(set([scores[0] - 1e-9, *scores, scores[-1] + 1e-9]))
        best = None
        for threshold in thresholds:
            accepted = [case for case in cases if case["score"] >= threshold]
            rejected = [case for case in cases if case["score"] < threshold]
            tp = sum(case["correct"] for case in accepted)
            fp = len(accepted) - tp
            fn = sum(case["correct"] for case in rejected)
            tn = len(rejected) - fn
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall_score = tp / (tp + fn) if tp + fn else 0.0
            f1 = (
                2.0 * precision * recall_score / (precision + recall_score)
                if precision + recall_score else 0.0
            )
            candidate = (f1, precision, threshold, {
                "precision": precision,
                "recall": recall_score,
                "f1": f1,
                "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
                "positive_top1": correct_count,
                "negative_top1": incorrect_count,
                "scored_samples": len(cases),
            })
            if best is None or candidate[:3] > best[:3]:
                best = candidate

        threshold = float(best[2])
        metrics = best[3]
        calibration = {
            "schema_version": 1,
            "threshold": threshold,
            "readout_updates": int(self.agent.network.output_updates),
            "encoder_updates": int(self.agent.encoder.updates),
            "encoder_vocab_size": len(self.agent.encoder.vocab),
            "validation_fingerprint": self.validation_fingerprint(),
            "validation_samples": len(rows),
            "scored_samples": len(cases),
            "metrics": metrics,
            "selected_at": datetime.now(timezone.utc).isoformat(),
        }
        save_json(self.agent.lif_calibration_path, calibration)
        self.agent.config.lif_retrieval_threshold = threshold
        return {"calibrated": True, **calibration}

    @staticmethod
    def _token_f1(expected, actual):
        expected_tokens = tokenize(expected)
        actual_tokens = tokenize(actual)
        if not expected_tokens or not actual_tokens:
            return 1.0 if expected_tokens == actual_tokens else 0.0
        expected_counts = Counter(expected_tokens)
        actual_counts = Counter(actual_tokens)
        overlap = sum((expected_counts & actual_counts).values())
        precision = overlap / len(actual_tokens)
        recall_score = overlap / len(expected_tokens)
        return (
            2.0 * precision * recall_score / (precision + recall_score)
            if precision + recall_score else 0.0
        )

    @staticmethod
    def _is_question_echo(question, answer):
        question_key, answer_key = normalize(question), normalize(answer)
        if not question_key or not answer_key:
            return False
        if question_key == answer_key:
            return True
        question_tokens = set(tokenize(question))
        answer_tokens = set(tokenize(answer))
        return (
            len(question_tokens) >= 3
            and len(question_tokens & answer_tokens) / len(question_tokens) >= 0.85
        )

    def evaluate_cognition(self, qa_test, include_llm=False):
        """Avalia respostas completas no split test sem persistir interações ou vazar consultas exatas."""
        exact_questions = {normalize(row.get("question", "")) for row in qa_test}

        cases = []
        source_counts = {}
        total_f1 = 0.0
        exact_matches = 0
        abstentions = 0
        echoes = 0
        lif_candidates = 0
        lif_used = 0
        lif_scores = []
        for row in qa_test:
            question = str(row.get("question", "")).strip()
            expected = str(row.get("answer", "")).strip()
            answer = self.agent.respond(
                question, use_language=bool(include_llm), record=False,
                excluded_questions=exact_questions,
            )
            trace = dict(self.agent.last_trace)
            source = str(trace.get("response_source", "unknown"))
            exact = normalize(answer) == normalize(expected)
            f1 = self._token_f1(expected, answer)
            abstained = source in {"fallback", "entity_abstention"}
            echoed = self._is_question_echo(question, answer)
            candidate_count = int(trace.get("lif_retrieval_candidates", 0) or 0)
            lif_score = trace.get("lif_retrieval_score")
            source_counts[source] = source_counts.get(source, 0) + 1
            total_f1 += f1
            exact_matches += int(exact)
            abstentions += int(abstained)
            echoes += int(echoed)
            lif_candidates += int(candidate_count > 0)
            lif_used += int(source in {"lif_associative_readout", "lif_conditioned_llm"})
            if lif_score is not None:
                lif_scores.append(float(lif_score))
            cases.append({
                "question": question,
                "expected_answer": expected,
                "answer": answer,
                "response_source": source,
                "exact_match": exact,
                "token_f1": f1,
                "abstained": abstained,
                "question_echo": echoed,
                "lif_candidate_count": candidate_count,
                "lif_retrieval_score": lif_score,
            })
        count = len(qa_test)
        metrics = {
            "exact_match": exact_matches / count if count else None,
            "token_f1": total_f1 / count if count else None,
            "abstention_rate": abstentions / count if count else None,
            "question_echo_rate": echoes / count if count else None,
            "lif_candidate_rate": lif_candidates / count if count else None,
            "lif_used_rate": lif_used / count if count else None,
            "mean_lif_retrieval_score": (
                sum(lif_scores) / len(lif_scores) if lif_scores else None
            ),
            "source_distribution": source_counts,
        }
        return {
            "samples": count,
            "metrics": metrics,
            "cases": cases,
            "protocol": {
                "llm_enabled": bool(include_llm),
                "response_recording": False,
                "exact_test_questions_excluded": True,
                "training_pipeline_uses_only_train_split": True,
                "historical_weight_provenance_verified": False,
                "quality_metric_note": (
                    "Token F1 e exact match são proxies de correspondência textual; "
                    "não comprovam factualidade nem compreensão geral."
                ),
            },
        }

    def evaluate(self, threshold=0.25, ks=(1, 3, 5), include_llm=False):
        """Benchmark de recuperação, classificação contrastiva e respostas completas."""
        threshold = float(threshold)
        if not -1.0 <= threshold <= 1.0:
            raise ValueError("threshold deve estar entre -1 e 1.")
        ks = tuple(sorted({int(k) for k in ks}))
        if not ks or ks[0] < 1:
            raise ValueError("ks deve conter inteiros positivos.")
        self._require_clean_splits()

        rows = self.dataset.load()
        qa_test = [r for r in rows if r.get("type", "qa") == "qa" and r.get("split") == "test"]
        pair_test = [r for r in rows if r.get("type") == "pair" and r.get("split") == "test"]
        candidates = list(self.agent.memory.knowledge)
        retrieval_encoder = (
            self.agent._active_retrieval_encoder()
            if hasattr(self.agent, "_active_retrieval_encoder")
            else getattr(self.agent, "retrieval_encoder", self.agent.encoder)
        )
        retrieval = {"samples": len(qa_test), "candidate_count": len(candidates), "metrics": {}}
        channels = ("lexical", "semantic", "hybrid")
        reciprocal = {name: 0.0 for name in channels}
        hits = {name: {k: 0 for k in ks} for name in channels}
        excluded_exact_queries = 0
        semantic_weight = getattr(
            retrieval_encoder, "semantic_weight",
            .35 + .50 * min(1.0, getattr(retrieval_encoder, "updates", 0) / 30.0)
        )
        for row in qa_test:
            query = row["question"]
            query_key = normalize(query)
            q_tokens = set(tokenize(query))
            q_vector = self._encode_query(retrieval_encoder, query)
            scored = {name: [] for name in channels}
            for item in candidates:
                candidate_text = str(item.get("question", ""))
                if normalize(candidate_text) == query_key:
                    excluded_exact_queries += 1
                    continue
                c_tokens = set(tokenize(candidate_text))
                union = q_tokens | c_tokens
                lexical = len(q_tokens & c_tokens) / len(union) if union else 0.0
                semantic = max(0.0, min(1.0, cosine(
                    q_vector, self._encode_passage(retrieval_encoder, candidate_text)
                )))
                values = {
                    "lexical": lexical,
                    "semantic": semantic,
                    "hybrid": semantic_weight * semantic + (1.0 - semantic_weight) * lexical,
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

        native_encoder = self.agent.encoder
        tp = fp = tn = fn = 0
        positive, negative = [], []
        for pair in pair_test:
            similarity = cosine(
                native_encoder.encode(pair["text_a"]),
                native_encoder.encode(pair["text_b"])
            )
            label = int(pair.get("label", 1))
            predicted = int(similarity >= threshold)
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
        cognition = self.evaluate_cognition(qa_test, include_llm=include_llm)

        return {
            "retrieval": retrieval,
            "contrastive": contrastive,
            "cognition": cognition,
            "protocol": {
                "test_qa_samples": len(qa_test),
                "test_pair_samples": len(pair_test),
                "candidate_source": "memory.knowledge excluding exact test questions",
                "excluded_exact_query_candidates": excluded_exact_queries,
                "channels": list(channels),
                "ks": list(ks),
                "threshold": threshold,
                "test_split_submitted_to_training": False,
                "historical_weight_provenance_verified": False,
                "split_audit": "passed",
            },
            "note": "Métricas de recuperação e classificação são separadas; "
                    "o benchmark não prova compreensão semântica geral.",
        }
