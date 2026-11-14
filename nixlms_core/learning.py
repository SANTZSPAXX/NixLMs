"""Importação, treinamento contrastivo e avaliação sem vazamento de dados."""
import copy
import hashlib
import json
import math
import os
import random
import shutil
import tempfile
import uuid
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

    INCREMENTAL_MODEL_FILES = (
        "semantic_encoder.json",
        "neural_weights.json",
        "neural_decoder.json",
        "knowledge.json",
        "mental_map.json",
    )
    INCREMENTAL_CALIBRATION_FILES = (
        "lif_calibration.json",
        "decoder_calibration.json",
    )

    @staticmethod
    def _state_fingerprint(state):
        payload = json.dumps(
            state, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _live_model_state(self):
        return {
            "semantic_encoder.json": self.agent.encoder.state_dict(),
            "neural_weights.json": self.agent.network.state_dict(),
            "neural_decoder.json": self.agent.decoder.state_dict(),
            "knowledge.json": self.agent.memory.knowledge,
            "mental_map.json": {
                "nodes": self.agent.mental_map.nodes,
                "edges": self.agent.mental_map.edges,
            },
        }

    def _validation_metrics(self):
        """Compara o estado atual somente com exemplos QA do split validation."""
        self._require_clean_splits()
        rows = [
            row for row in self.dataset.load()
            if row.get("type", "qa") == "qa" and row.get("split") == "validation"
        ]
        decoder_losses = []
        decoder_accuracies = []
        decoder_known = 0
        decoder_oov = 0
        generation_scores = []
        lif_losses = []

        for row in rows:
            question = str(row.get("question", "")).strip()
            answer = str(row.get("answer", "")).strip()
            context, _, _, _ = self.agent._lif_forward(question)
            decoder_score = self.agent.decoder.score(context, answer)
            if decoder_score.get("loss") is not None:
                decoder_losses.append(float(decoder_score["loss"]))
                if decoder_score.get("token_accuracy") is not None:
                    decoder_accuracies.append(float(decoder_score["token_accuracy"]))
                decoder_known += int(decoder_score.get("known_tokens", 0))
                decoder_oov += int(decoder_score.get("oov_tokens", 0))

            generated = self.agent.decoder.generate(
                context, max_tokens=self.agent.config.decoder_max_tokens
            )
            generation_scores.append(
                self._token_f1(answer, generated.get("text", ""))
            )
            target = self.agent._compress_neural_target(
                self.agent.encoder.encode(answer)
            )
            prediction = context
            lif_losses.append(
                sum((float(left) - float(right)) ** 2
                    for left, right in zip(prediction, target))
                / max(1, len(target))
            )

        representation = self.evaluate_representations()["metrics"]
        lif_representation = self.evaluate_lif_representations()["metrics"]
        count = len(rows)
        metrics = {
            "decoder_loss": (
                sum(decoder_losses) / len(decoder_losses) if decoder_losses else None
            ),
            "decoder_token_accuracy": (
                sum(decoder_accuracies) / len(decoder_accuracies)
                if decoder_accuracies else None
            ),
            "decoder_oov_rate": (
                decoder_oov / (decoder_known + decoder_oov)
                if decoder_known + decoder_oov else None
            ),
            "generation_token_f1": (
                sum(generation_scores) / len(generation_scores)
                if generation_scores else None
            ),
            "lif_output_loss": (
                sum(lif_losses) / len(lif_losses) if lif_losses else None
            ),
            "representation_margin": representation.get("margin"),
            "representation_pairwise_accuracy": representation.get("pairwise_accuracy"),
            "lif_contrastive_margin": lif_representation.get("margin"),
            "lif_contrastive_pairwise_accuracy": lif_representation.get("pairwise_accuracy"),
        }
        return {
            "samples": count,
            "metrics": metrics,
            "protocol": {
                "validation_split_used": True,
                "test_split_used": False,
                "weights_updated": False,
                "llm_enabled": False,
            },
        }

    @staticmethod
    def _compare_validation_metrics(before, after, regression_tolerance, min_improvement):
        directions = {
            "decoder_loss": -1.0,
            "decoder_token_accuracy": 1.0,
            "decoder_oov_rate": -1.0,
            "generation_token_f1": 1.0,
            "lif_output_loss": -1.0,
            "representation_margin": 1.0,
            "representation_pairwise_accuracy": 1.0,
            "lif_contrastive_margin": 1.0,
            "lif_contrastive_pairwise_accuracy": 1.0,
        }
        comparisons = {}
        regressions = []
        improvements = []
        before_metrics = before.get("metrics", {})
        after_metrics = after.get("metrics", {})
        for name, direction in directions.items():
            left = before_metrics.get(name)
            right = after_metrics.get(name)
            if left is None and right is None:
                continue
            if right is None:
                regressions.append(name)
                comparisons[name] = {"before": left, "after": None, "status": "missing_after"}
                continue
            if left is None:
                improvements.append(name)
                comparisons[name] = {"before": None, "after": right, "status": "new_metric"}
                continue
            left, right = float(left), float(right)
            if not math.isfinite(left) or not math.isfinite(right):
                regressions.append(name)
                comparisons[name] = {"before": left, "after": right, "status": "non_finite"}
                continue
            gain = (right - left) * direction
            if gain < -regression_tolerance:
                regressions.append(name)
                status = "regression"
            elif gain > min_improvement:
                improvements.append(name)
                status = "improved"
            else:
                status = "stable"
            comparisons[name] = {
                "before": left, "after": right, "directional_gain": gain,
                "status": status,
            }
        accepted = bool(comparisons) and not regressions and bool(improvements)
        reason = (
            "accepted" if accepted else
            "validation_regression" if regressions else
            "no_measurable_improvement"
        )
        return {
            "accepted": accepted,
            "reason": reason,
            "comparisons": comparisons,
            "improvements": improvements,
            "regressions": regressions,
        }

    def _checkpoint_root(self):
        return self.agent.data_dir / "checkpoints" / "incremental"

    def _create_incremental_checkpoint(self, checkpoint_id, baseline_metrics,
                                       validation_fingerprint, state_fingerprint):
        checkpoint_dir = self._checkpoint_root() / checkpoint_id
        checkpoint_dir.mkdir(parents=True, exist_ok=False)
        state = self._live_model_state()
        for filename, payload in state.items():
            save_json(checkpoint_dir / filename, payload)
        files = {}
        for filename in self.INCREMENTAL_MODEL_FILES + self.INCREMENTAL_CALIBRATION_FILES:
            source = self.agent.data_dir / filename
            target = checkpoint_dir / filename
            if filename in state:
                files[filename] = {
                    "present": True,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            elif source.is_file():
                shutil.copy2(source, target)
                files[filename] = {
                    "present": True,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            else:
                files[filename] = {"present": False, "sha256": None}
        manifest = {
            "schema_version": 1,
            "checkpoint_id": checkpoint_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "candidate_pending",
            "files": files,
            "baseline_state_fingerprint": state_fingerprint,
            "validation_fingerprint": validation_fingerprint,
            "baseline_metrics": baseline_metrics,
            "candidate_metrics": None,
            "training": None,
        }
        save_json(checkpoint_dir / "manifest.json", manifest)
        return checkpoint_dir, manifest

    def _write_checkpoint_manifest(self, checkpoint_dir, manifest):
        save_json(checkpoint_dir / "manifest.json", manifest)

    def _checkpoint_directory(self, checkpoint_id):
        identifier = str(checkpoint_id or "")
        if not identifier or Path(identifier).name != identifier or identifier in {".", ".."}:
            raise ValueError("Identificador de checkpoint inválido.")
        return self._checkpoint_root() / identifier

    def restore_incremental_checkpoint(self, checkpoint_id):
        """Restaura pesos e calibrações verificando hashes antes de qualquer gravação."""
        checkpoint_dir = self._checkpoint_directory(checkpoint_id)
        manifest_path = checkpoint_dir / "manifest.json"
        manifest = load_json(manifest_path, None)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            raise ValueError("Manifesto de checkpoint ausente ou incompatível.")
        if manifest.get("checkpoint_id") != str(checkpoint_id):
            raise ValueError("O identificador não corresponde ao manifesto do checkpoint.")

        filenames = self.INCREMENTAL_MODEL_FILES + self.INCREMENTAL_CALIBRATION_FILES
        for filename in filenames:
            record = manifest.get("files", {}).get(filename)
            if not isinstance(record, dict):
                raise ValueError("Manifesto de checkpoint incompleto.")
            source = checkpoint_dir / filename
            if record.get("present"):
                if not source.is_file():
                    raise ValueError("Arquivo de checkpoint ausente: " + filename)
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                if digest != record.get("sha256"):
                    raise ValueError("Integridade do checkpoint inválida: " + filename)

        with tempfile.TemporaryDirectory(
            prefix=".nixlms-restore-", dir=str(self.agent.data_dir)
        ) as staging:
            staging_dir = Path(staging)
            for filename in filenames:
                record = manifest["files"][filename]
                if record["present"]:
                    shutil.copy2(checkpoint_dir / filename, staging_dir / filename)
            try:
                for filename in filenames:
                    destination = self.agent.data_dir / filename
                    staged = staging_dir / filename
                    if manifest["files"][filename]["present"]:
                        os.replace(staged, destination)
                    elif destination.exists():
                        destination.unlink()
                if not self.agent.encoder.load_state_dict(
                    load_json(self.agent.data_dir / "semantic_encoder.json", None)
                ):
                    raise ValueError("Checkpoint do encoder incompatível.")
                if not self.agent.network.load_state_dict(
                    load_json(self.agent.data_dir / "neural_weights.json", None)
                ):
                    raise ValueError("Checkpoint da rede LIF incompatível.")
                if not self.agent.decoder.load_state_dict(
                    load_json(self.agent.data_dir / "neural_decoder.json", None)
                ):
                    raise ValueError("Checkpoint do decoder incompatível.")
                self.agent.memory.knowledge = load_json(
                    self.agent.data_dir / "knowledge.json", []
                )
                self.agent.memory._embedding_cache.clear()
                mental_state = load_json(
                    self.agent.data_dir / "mental_map.json", {"nodes": {}, "edges": {}}
                )
                self.agent.mental_map.nodes = mental_state.get("nodes", {})
                self.agent.mental_map.edges = mental_state.get("edges", {})
                self.agent._load_lif_calibration()
                self.agent._load_decoder_calibration()
            except Exception:
                raise

        manifest["status"] = "rolled_back"
        manifest["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        self._write_checkpoint_manifest(checkpoint_dir, manifest)
        return {
            "restored": True,
            "checkpoint_id": str(checkpoint_id),
            "status": manifest["status"],
        }

    def train_incremental(self, epochs=1, seed=42, min_validation_samples=2,
                          regression_tolerance=0.02, min_improvement=0.001):
        """Treina candidato isolado e só promove pesos se validation não regredir."""
        epochs = int(epochs)
        min_validation_samples = int(min_validation_samples)
        regression_tolerance = float(regression_tolerance)
        min_improvement = float(min_improvement)
        if epochs < 1 or epochs > 100:
            raise ValueError("epochs deve estar entre 1 e 100.")
        if min_validation_samples < 2:
            raise ValueError("min_validation_samples deve ser pelo menos 2.")
        if (not math.isfinite(regression_tolerance) or regression_tolerance < 0
                or not math.isfinite(min_improvement) or min_improvement <= 0):
            raise ValueError("Tolerância deve ser não negativa e melhoria mínima positiva.")
        self._require_clean_splits()
        rows = self.dataset.load()
        validation_rows = [
            row for row in rows
            if row.get("type", "qa") == "qa" and row.get("split") == "validation"
        ]
        if len(validation_rows) < min_validation_samples:
            return {
                "accepted": False,
                "reason": "insufficient_validation_samples",
                "validation_samples": len(validation_rows),
                "required_samples": min_validation_samples,
            }
        if not any(
            row.get("split", "train") == "train"
            and row.get("type", "qa") in {"qa", "pair"}
            for row in rows
        ):
            return {"accepted": False, "reason": "training_split_empty"}
        if not getattr(self.agent, "decoder_persistence_enabled", True):
            return {"accepted": False, "reason": "decoder_checkpoint_unavailable"}

        baseline_metrics = self._validation_metrics()
        if baseline_metrics.get("samples", 0) < min_validation_samples:
            return {"accepted": False, "reason": "insufficient_validation_metrics"}

        validation_fingerprint = self.validation_fingerprint()
        dataset_fingerprint = self.dataset_fingerprint()
        live_state = self._live_model_state()
        state_fingerprint = self._state_fingerprint(live_state)
        checkpoint_id = uuid.uuid4().hex
        checkpoint_dir, manifest = self._create_incremental_checkpoint(
            checkpoint_id, baseline_metrics, validation_fingerprint, state_fingerprint
        )
        manifest["dataset_fingerprint"] = dataset_fingerprint
        self._write_checkpoint_manifest(checkpoint_dir, manifest)

        with tempfile.TemporaryDirectory(prefix="nixlms-incremental-") as temporary:
            candidate_dir = Path(temporary) / "candidate"
            shutil.copytree(
                self.agent.data_dir, candidate_dir, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("checkpoints"),
            )
            for filename, payload in live_state.items():
                save_json(candidate_dir / filename, payload)
            candidate = self.agent.__class__(
                candidate_dir, config=copy.deepcopy(self.agent.config), llm_model=None
            )
            # A threshold loaded from a calibration file must not be mistaken for
            # a user-supplied override merely because the active config is copied.
            candidate._base_lif_retrieval_threshold = self.agent._base_lif_retrieval_threshold
            candidate._explicit_lif_threshold = self.agent._explicit_lif_threshold
            candidate._base_decoder_min_confidence = self.agent._base_decoder_min_confidence
            candidate._explicit_decoder_min_confidence = self.agent._explicit_decoder_min_confidence
            candidate._load_lif_calibration()
            candidate._load_decoder_calibration()
            if (not getattr(candidate, "decoder_persistence_enabled", True)
                    or candidate.decoder_load_error):
                manifest["status"] = "rejected"
                manifest["reason"] = "candidate_decoder_state_unavailable"
                self._write_checkpoint_manifest(checkpoint_dir, manifest)
                return {
                    "accepted": False, "reason": manifest["reason"],
                    "checkpoint_id": checkpoint_id, "rollback_available": True,
                }

            training_report = candidate.learning.train(epochs=epochs, seed=seed)
            if training_report.get("trained") == 0:
                manifest["status"] = "rejected"
                manifest["reason"] = "no_training_updates"
                manifest["training"] = training_report
                self._write_checkpoint_manifest(checkpoint_dir, manifest)
                return {
                    "accepted": False, "reason": manifest["reason"],
                    "checkpoint_id": checkpoint_id, "rollback_available": True,
                }

            candidate_metrics = candidate.learning._validation_metrics()
            comparison = self._compare_validation_metrics(
                baseline_metrics, candidate_metrics,
                regression_tolerance, min_improvement,
            )
            manifest["candidate_metrics"] = candidate_metrics
            manifest["training"] = training_report
            manifest["comparison"] = comparison
            if not comparison["accepted"]:
                manifest["status"] = "rejected"
                manifest["reason"] = comparison["reason"]
                self._write_checkpoint_manifest(checkpoint_dir, manifest)
                return {
                    "accepted": False,
                    "reason": comparison["reason"],
                    "checkpoint_id": checkpoint_id,
                    "rollback_available": True,
                    "baseline": baseline_metrics,
                    "candidate": candidate_metrics,
                    "comparison": comparison,
                    "training": training_report,
                }

            if self.validation_fingerprint() != validation_fingerprint:
                manifest["status"] = "rejected"
                manifest["reason"] = "validation_dataset_changed"
                self._write_checkpoint_manifest(checkpoint_dir, manifest)
                return {
                    "accepted": False, "reason": manifest["reason"],
                    "checkpoint_id": checkpoint_id, "rollback_available": True,
                }
            if self.dataset_fingerprint() != dataset_fingerprint:
                manifest["status"] = "rejected"
                manifest["reason"] = "dataset_changed_during_candidate_training"
                self._write_checkpoint_manifest(checkpoint_dir, manifest)
                return {
                    "accepted": False, "reason": manifest["reason"],
                    "checkpoint_id": checkpoint_id, "rollback_available": True,
                }
            if self._state_fingerprint(self._live_model_state()) != state_fingerprint:
                manifest["status"] = "rejected"
                manifest["reason"] = "live_model_changed_during_candidate_training"
                self._write_checkpoint_manifest(checkpoint_dir, manifest)
                return {
                    "accepted": False, "reason": manifest["reason"],
                    "checkpoint_id": checkpoint_id, "rollback_available": True,
                }

            candidate_state = candidate.learning._live_model_state()
            try:
                candidate_state_fingerprint = self._state_fingerprint(candidate_state)
            except (TypeError, ValueError):
                manifest["status"] = "rejected"
                manifest["reason"] = "candidate_state_invalid"
                self._write_checkpoint_manifest(checkpoint_dir, manifest)
                return {
                    "accepted": False, "reason": manifest["reason"],
                    "checkpoint_id": checkpoint_id, "rollback_available": True,
                }
            manifest["candidate_state_fingerprint"] = candidate_state_fingerprint
            try:
                with tempfile.TemporaryDirectory(
                    prefix=".nixlms-candidate-", dir=str(self.agent.data_dir)
                ) as staging:
                    staging_dir = Path(staging)
                    for filename, payload in candidate_state.items():
                        save_json(staging_dir / filename, payload)
                    for filename in self.INCREMENTAL_MODEL_FILES:
                        os.replace(
                            staging_dir / filename, self.agent.data_dir / filename
                        )
                if not self.agent.encoder.load_state_dict(
                    candidate_state["semantic_encoder.json"]
                ):
                    raise ValueError("Encoder candidato incompatível.")
                if not self.agent.network.load_state_dict(
                    candidate_state["neural_weights.json"]
                ):
                    raise ValueError("Rede LIF candidata incompatível.")
                if not self.agent.decoder.load_state_dict(
                    candidate_state["neural_decoder.json"]
                ):
                    raise ValueError("Decoder candidato incompatível.")
                self.agent.memory.knowledge = copy.deepcopy(candidate_state["knowledge.json"])
                self.agent.memory._embedding_cache.clear()
                self.agent.mental_map.nodes = copy.deepcopy(
                    candidate_state["mental_map.json"].get("nodes", {})
                )
                self.agent.mental_map.edges = copy.deepcopy(
                    candidate_state["mental_map.json"].get("edges", {})
                )
                self.agent.invalidate_lif_calibration()
            except Exception:
                self.restore_incremental_checkpoint(checkpoint_id)
                raise

        manifest["status"] = "accepted"
        manifest["accepted_at"] = datetime.now(timezone.utc).isoformat()
        self._write_checkpoint_manifest(checkpoint_dir, manifest)
        return {
            "accepted": True,
            "reason": "accepted",
            "checkpoint_id": checkpoint_id,
            "rollback_available": True,
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "comparison": comparison,
            "training": training_report,
        }

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

        if hasattr(self.agent, "invalidate_lif_calibration"):
            self.agent.invalidate_lif_calibration()
        for row in qa_rows:
            self.agent.learn(row["question"], row["answer"],
                             remember=True, reinforce=False, add_to_dataset=False)

        corpus = []
        for row in qa_rows:
            corpus.extend([row["question"], row["answer"]])
        for pair in pairs:
            corpus.extend([pair["text_a"], pair["text_b"]])
        self.agent.encoder.fit_vocabulary(corpus)

        self.agent.decoder.fit_vocabulary([row["answer"] for row in qa_rows])
        rng = random.Random(seed)
        losses = []
        updates = 0
        lif_losses = []
        lif_recurrent_losses = []
        lif_pair_losses = []
        lif_pair_updates = 0
        decoder_losses = []
        for _ in range(epochs):
            batch = list(pairs)
            rng.shuffle(batch)
            for pair in batch:
                result = self.agent.encoder.fit_pair(
                    pair["text_a"], pair["text_b"], pair.get("label", 1)
                )
                losses.append(result["loss"])
                updates += int(result["updated"])
                lif_pair_result = self.agent.network.train_recurrent_pair(
                    self.agent.encoder.encode(pair["text_a"]),
                    self.agent.encoder.encode(pair["text_b"]),
                    pair.get("label", 1),
                    learning_rate=self.agent.config.lif_recurrent_learning_rate,
                    margin=self.agent.config.lif_contrastive_margin,
                    surrogate_width=self.agent.config.lif_surrogate_width,
                )
                lif_pair_losses.append(lif_pair_result["loss"])
                lif_pair_updates += int(lif_pair_result["updated"])
            # Treina a dinâmica recorrente com o alvo semântico antes de ajustar
            # o readout; o readout permanece congelado durante BPTT substituto.
            qa_batch = list(qa_rows)
            rng.shuffle(qa_batch)
            for row in qa_batch:
                vector = self.agent.encoder.encode(row["question"])
                target = self.agent._compress_neural_target(
                    self.agent.encoder.encode(row["answer"])
                )
                recurrent_result = self.agent.network.train_recurrent(
                    vector, target,
                    learning_rate=self.agent.config.lif_recurrent_learning_rate,
                    surrogate_width=self.agent.config.lif_surrogate_width,
                )
                lif_recurrent_losses.append(recurrent_result["loss"])
            # Treina a leitura depois da atualização recorrente,
            # mantendo os alvos semânticos alinhados aos embeddings atuais.
            for row in qa_batch:
                _, hidden, _, _ = self.agent._lif_forward(row["question"])
                target = self.agent._compress_neural_target(
                    self.agent.encoder.encode(row["answer"])
                )
                lif_losses.append(self.agent.network.train_output(
                    hidden, target,
                    learning_rate=self.agent.config.lif_output_learning_rate
                ))
            for row in qa_batch:
                lif_context, _, _, _ = self.agent._lif_forward(row["question"])
                decoder_result = self.agent.decoder.train_pair(
                    lif_context, row["answer"]
                )
                decoder_losses.append(decoder_result["loss"])

        self.agent._save_encoder()
        save_json(self.agent.data_dir / "neural_weights.json",
                  self.agent.network.state_dict())
        if getattr(self.agent, "decoder_persistence_enabled", True):
            self.agent._save_decoder()
        self.last_training = {
            "qa_memories_upserted": len(qa_rows),
            "contrastive_pairs": len(pairs),
            "contrastive_updates": updates,
            "epochs": epochs,
            "mean_contrastive_loss": sum(losses) / len(losses) if losses else None,
            "lif_output_updates": self.agent.network.output_updates,
            "lif_recurrent_updates": self.agent.network.recurrent_updates,
            "lif_recurrent_examples_trained": len(qa_rows),
            "mean_lif_recurrent_loss": (
                sum(lif_recurrent_losses) / len(lif_recurrent_losses)
                if lif_recurrent_losses else None
            ),
            "lif_pair_updates": lif_pair_updates,
            "mean_lif_pair_loss": (
                sum(lif_pair_losses) / len(lif_pair_losses)
                if lif_pair_losses else None
            ),
            "lif_qa_examples_trained": len(qa_rows),
            "mean_lif_readout_loss": sum(lif_losses) / len(lif_losses) if lif_losses else None,
            "decoder_trained_steps": self.agent.decoder.trained_steps,
            "decoder_vocabulary_size": len(self.agent.decoder.vocab),
            "mean_decoder_loss": sum(decoder_losses) / len(decoder_losses) if decoder_losses else None,
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

    def decoder_model_fingerprint(self):
        """Fingerprint do decoder, readout LIF e versão do encoder usada no contexto."""
        payload = {
            "decoder": self.agent.decoder.state_dict(),
            "lif_readout": self.agent.network.w_out,
            "lif_recurrent": {
                "w_in": self.agent.network.w_in,
                "w_rec": self.agent.network.w_rec,
                "recurrent_updates": self.agent.network.recurrent_updates,
            },
            "encoder_updates": self.agent.encoder.updates,
            "encoder_vocab_size": len(self.agent.encoder.vocab),
            "encoder_dimensions": self.agent.encoder.dimensions,
            "lif_config": {
                "input_size": self.agent.config.input_size,
                "hidden_size": self.agent.config.hidden_size,
                "output_size": self.agent.config.output_size,
                "steps": self.agent.config.steps,
                "threshold": self.agent.config.threshold,
                "leak": self.agent.config.leak,
                "seed": self.agent.config.seed,
            },
        }
        serialized = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def calibrate_decoder_confidence(self, min_validation_samples=4,
                                     min_correct=2, min_incorrect=2,
                                     min_token_f1=0.60):
        """Calibra a aceitação do decoder exclusivamente com QA do split validation."""
        if hasattr(self.agent, "_load_decoder_calibration"):
            self.agent._load_decoder_calibration()
        self._require_clean_splits()
        min_validation_samples = int(min_validation_samples)
        min_correct = int(min_correct)
        min_incorrect = int(min_incorrect)
        min_token_f1 = float(min_token_f1)
        if min_validation_samples < 1 or min_correct < 1 or min_incorrect < 1:
            raise ValueError("Os mínimos de calibração devem ser inteiros positivos.")
        if not math.isfinite(min_token_f1) or not 0.0 <= min_token_f1 <= 1.0:
            raise ValueError("min_token_f1 deve estar entre 0 e 1.")
        if self.agent.decoder.trained_steps <= 0 or self.agent.network.output_updates <= 0:
            return {"calibrated": False, "reason": "decoder_or_lif_readout_untrained"}

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

        cases = []
        for row in rows:
            question = str(row.get("question", "")).strip()
            expected = str(row.get("answer", "")).strip()
            context, _, _, _ = self.agent._lif_forward(question)
            generated = self.agent.decoder.generate(
                context, max_tokens=self.agent.config.decoder_max_tokens
            )
            candidate = str(generated.get("text", "")).strip()
            try:
                confidence = float(generated.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            if not math.isfinite(confidence):
                confidence = 0.0
            confidence = min(1.0, max(0.0, confidence))
            tokens = list(generated.get("tokens", []))
            token_f1 = self._token_f1(expected, candidate)
            valid_sequence = (
                bool(candidate)
                and int(generated.get("token_count", len(tokens))) >= 2
                and not self._is_question_echo(question, candidate)
                and len(set(tokens)) > 1
            )
            correct = bool(valid_sequence and token_f1 >= min_token_f1)
            cases.append({
                "question": question,
                "expected_answer": expected,
                "generated_answer": candidate,
                "confidence": confidence,
                "token_f1": token_f1,
                "valid_sequence": valid_sequence,
                "correct": correct,
            })

        correct_count = sum(case["correct"] for case in cases)
        incorrect_count = len(cases) - correct_count
        if len(cases) < min_validation_samples:
            return {
                "calibrated": False,
                "reason": "insufficient_decoder_generations",
                "validation_samples": len(rows),
                "scored_samples": len(cases),
            }
        if correct_count < min_correct or incorrect_count < min_incorrect:
            return {
                "calibrated": False,
                "reason": "insufficient_generation_class_balance",
                "scored_samples": len(cases),
                "positive_generations": correct_count,
                "negative_generations": incorrect_count,
                "required_positive": min_correct,
                "required_negative": min_incorrect,
            }

        scores = sorted({case["confidence"] for case in cases})
        thresholds = sorted({0.0, *scores, 1.000001})
        best = None
        for threshold in thresholds:
            accepted = [case for case in cases if case["confidence"] >= threshold]
            rejected = [case for case in cases if case["confidence"] < threshold]
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
                "positive_generations": correct_count,
                "negative_generations": incorrect_count,
                "scored_samples": len(cases),
                "mean_token_f1": sum(case["token_f1"] for case in cases) / len(cases),
            })
            if best is None or candidate[:3] > best[:3]:
                best = candidate

        threshold = float(best[2])
        calibration = {
            "schema_version": 1,
            "threshold": threshold,
            "decoder_trained_steps": int(self.agent.decoder.trained_steps),
            "decoder_vocab_size": len(self.agent.decoder.vocab),
            "lif_readout_updates": int(self.agent.network.output_updates),
            "lif_recurrent_updates": int(self.agent.network.recurrent_updates),
            "encoder_updates": int(self.agent.encoder.updates),
            "encoder_vocab_size": len(self.agent.encoder.vocab),
            "validation_fingerprint": self.validation_fingerprint(),
            "decoder_model_fingerprint": self.decoder_model_fingerprint(),
            "validation_samples": len(rows),
            "scored_samples": len(cases),
            "min_token_f1": min_token_f1,
            "metrics": best[3],
            "protocol": {
                "validation_split_used": True,
                "test_split_used": False,
                "weights_updated": False,
            },
            "selected_at": datetime.now(timezone.utc).isoformat(),
        }
        save_json(self.agent.decoder_calibration_path, calibration)
        self.agent.config.decoder_min_confidence = threshold
        return {"calibrated": True, **calibration}

    def evaluate_decoder(self, qa_test=None):
        """Avalia perplexidade e acurácia teacher-forced apenas no split test."""
        rows = qa_test if qa_test is not None else [
            row for row in self.dataset.load()
            if row.get("type", "qa") == "qa" and row.get("split") == "test"
        ]
        if self.agent.decoder.trained_steps <= 0:
            return {
                "samples": 0,
                "trained_steps": 0,
                "vocabulary_size": len(self.agent.decoder.vocab),
                "metrics": {"loss": None, "perplexity": None,
                            "token_accuracy": None, "oov_target_rate": None},
                "protocol": {"test_split_used": True, "weights_updated": False},
            }
        scores = []
        for row in rows:
            context, _, _, _ = self.agent._lif_forward(row["question"])
            result = self.agent.decoder.score(context, row["answer"])
            if result["loss"] is not None:
                scores.append(result)
        count = len(scores)
        known = sum(item["known_tokens"] for item in scores)
        oov = sum(item["oov_tokens"] for item in scores)
        return {
            "samples": count,
            "trained_steps": self.agent.decoder.trained_steps,
            "vocabulary_size": len(self.agent.decoder.vocab),
            "metrics": {
                "loss": sum(item["loss"] for item in scores) / count if count else None,
                "perplexity": (
                    sum(item["perplexity"] for item in scores) / count if count else None
                ),
                "token_accuracy": (
                    sum(item["token_accuracy"] for item in scores) / count if count else None
                ),
                "oov_target_rate": oov / (known + oov) if known + oov else None,
            },
            "protocol": {"test_split_used": True, "weights_updated": False},
        }

    def evaluate_representations(self):
        """Mede generalização semântica validation->train e cobertura de subwords."""
        rows = self.dataset.load()
        train_rows = [
            row for row in rows
            if row.get("type", "qa") == "qa" and row.get("split", "train") == "train"
        ]
        validation_rows = [
            row for row in rows
            if row.get("type", "qa") == "qa" and row.get("split") == "validation"
        ]
        cases = []
        coverages = []
        subword_coverages = []
        for row in validation_rows:
            expected = normalize(row.get("answer", ""))
            positives = [
                item for item in train_rows
                if normalize(item.get("answer", "")) == expected
            ]
            negatives = [
                item for item in train_rows
                if normalize(item.get("answer", "")) != expected
            ]
            coverage = self.agent.encoder.feature_coverage(row.get("question", ""))
            coverages.append(coverage["feature_coverage"])
            subword_coverages.append(coverage["subword_feature_coverage"])
            if not positives or not negatives:
                continue
            query_vector = self.agent.encoder.encode(row["question"])
            positive_score = max(
                cosine(query_vector, self.agent.encoder.encode(item["question"]))
                for item in positives
            )
            negative_score = max(
                cosine(query_vector, self.agent.encoder.encode(item["question"]))
                for item in negatives
            )
            cases.append({
                "question": row["question"],
                "positive_similarity": positive_score,
                "hard_negative_similarity": negative_score,
                "margin": positive_score - negative_score,
                "positive_ranked_above_negative": positive_score > negative_score,
            })

        count = len(cases)
        metrics = {
            "positive_similarity": (
                sum(case["positive_similarity"] for case in cases) / count
                if count else None
            ),
            "negative_similarity": (
                sum(case["hard_negative_similarity"] for case in cases) / count
                if count else None
            ),
            "margin": sum(case["margin"] for case in cases) / count if count else None,
            "pairwise_accuracy": (
                sum(case["positive_ranked_above_negative"] for case in cases) / count
                if count else None
            ),
            "feature_coverage": (
                sum(coverages) / len(coverages) if coverages else None
            ),
            "subword_feature_coverage": (
                sum(subword_coverages) / len(subword_coverages)
                if subword_coverages else None
            ),
        }
        return {
            "samples": count,
            "validation_questions": len(validation_rows),
            "metrics": metrics,
            "cases": cases,
            "protocol": {
                "train_split_used": True,
                "validation_split_used": True,
                "test_split_used": False,
                "weights_updated": False,
                "vocabulary_mutated": False,
            },
        }

    def lif_candidate_fingerprint(self):
        """Fingerprint das respostas candidatas disponíveis para o readout LIF."""
        rows = [
            (normalize(item.get("question", "")), normalize(item.get("answer", "")))
            for item in self.agent.memory.knowledge
        ]
        payload = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def dataset_fingerprint(self):
        """Fingerprint de todos os registros para detectar mudanças durante treino isolado."""
        payload = json.dumps(
            self.dataset.load(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def evaluate_lif_representations(self):
        """Avalia similaridade das representações ocultas LIF em pares validation."""
        rows = [
            row for row in self.dataset.load()
            if row.get("type") == "pair" and row.get("split") == "validation"
        ]
        positive = []
        negative = []
        cases = []
        for row in rows:
            _, hidden_a = self.agent.network.forward(
                self.agent.encoder.encode(row.get("text_a", ""))
            )
            _, hidden_b = self.agent.network.forward(
                self.agent.encoder.encode(row.get("text_b", ""))
            )
            similarity = cosine(hidden_a, hidden_b)
            label = int(row.get("label", 1))
            (positive if label == 1 else negative).append(similarity)
            cases.append({"label": label, "similarity": similarity})
        positive_mean = sum(positive) / len(positive) if positive else None
        negative_mean = sum(negative) / len(negative) if negative else None
        margin = (
            positive_mean - negative_mean
            if positive_mean is not None and negative_mean is not None else None
        )
        pairwise = (
            sum(pos > neg for pos in positive for neg in negative)
            / (len(positive) * len(negative))
            if positive and negative else None
        )
        return {
            "samples": len(rows),
            "positive_samples": len(positive),
            "negative_samples": len(negative),
            "metrics": {
                "positive_similarity": positive_mean,
                "negative_similarity": negative_mean,
                "margin": margin,
                "pairwise_accuracy": pairwise,
            },
            "cases": cases,
            "protocol": {
                "validation_split_used": True,
                "test_split_used": False,
                "weights_updated": False,
            },
        }

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
        if hasattr(self.agent, "_load_lif_calibration"):
            self.agent._load_lif_calibration()
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
            "recurrent_updates": int(self.agent.network.recurrent_updates),
            "encoder_updates": int(self.agent.encoder.updates),
            "encoder_vocab_size": len(self.agent.encoder.vocab),
            "validation_fingerprint": self.validation_fingerprint(),
            "candidate_memory_fingerprint": self.lif_candidate_fingerprint(),
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
        representations = self.evaluate_representations()
        decoder = self.evaluate_decoder(qa_test)
        cognition = self.evaluate_cognition(qa_test, include_llm=include_llm)

        return {
            "retrieval": retrieval,
            "contrastive": contrastive,
            "representations": representations,
            "decoder": decoder,
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
