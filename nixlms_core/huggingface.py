"""Integração pública e local com Hugging Face Hub.

A descoberta usa HTTPS anônimo e a biblioteca padrão. Downloads exigem ação
explícita, são limitados e usam huggingface_hub com token=False. Inferência é
sempre local/CPU e carrega apenas pesos Safetensors.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class HuggingFaceError(RuntimeError):
    """Erro controlado da integração Hugging Face."""


class HuggingFaceHub:
    API = "https://huggingface.co/api"
    USER_AGENT = "NixLMs-HuggingFace/1.0"
    HARD_MODEL_LIMIT = 1536 * 1024 * 1024
    HARD_DATASET_LIMIT = 512 * 1024 * 1024
    MODEL_EXTENSIONS = {
        ".safetensors", ".gguf", ".onnx", ".json", ".txt", ".model",
        ".tiktoken", ".vocab", ".merges", ".md",
    }
    DATASET_EXTENSIONS = {
        ".parquet", ".jsonl", ".json", ".csv", ".tsv", ".txt", ".md",
        ".yaml", ".yml",
    }
    SORTS = {"downloads", "likes", "lastModified", "createdAt", "trendingScore"}

    def __init__(self, data_dir, opener=None, timeout=12, downloader=None):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.root = self.data_dir / "huggingface"
        self.models_dir = self.root / "models"
        self.datasets_dir = self.root / "datasets"
        self.registry_path = self.root / "registry.json"
        self.active_path = self.root / "active_model.json"
        self.active_encoder_path = self.root / "active_encoder.json"
        self.active_perception_path = self.root / "active_perception.json"
        self.timeout = max(1, min(30, int(timeout)))
        self.opener = opener or urlopen
        self.downloader = downloader
        self._registry_lock = threading.RLock()
        # Even if the environment contains a cached login, never attach it
        # implicitly to public Hub requests.
        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

    @staticmethod
    def _repo_type(repo_type):
        value = str(repo_type or "").strip().lower().rstrip("s")
        if value not in {"model", "dataset", "space"}:
            raise HuggingFaceError("Tipo inválido. Use model, dataset ou space.")
        return value

    @staticmethod
    def _repo_id(repo_id):
        value = str(repo_id or "").strip()
        if len(value) > 200 or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}",
            value,
        ):
            raise HuggingFaceError("ID de repositório inválido; esperado autor/nome.")
        if any(part in {".", ".."} for part in value.split("/")):
            raise HuggingFaceError("ID de repositório inválido.")
        return value

    def _request_json(self, url):
        request = Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise HuggingFaceError("Resposta do Hub excedeu 5 MB.")
            value = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise HuggingFaceError(
                    "O recurso exige autenticação ou acesso aprovado; a NixLMs não usa token."
                ) from exc
            if exc.code == 404:
                raise HuggingFaceError("Repositório público não encontrado.") from exc
            if exc.code == 429:
                raise HuggingFaceError("Limite temporário de consultas do Hub atingido.") from exc
            raise HuggingFaceError(f"Hub respondeu HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise HuggingFaceError(f"Hub indisponível: {type(exc).__name__}.") from exc
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise HuggingFaceError("Resposta JSON inválida do Hub.") from exc
        return value

    def search(self, repo_type, query="", limit=20, sort="downloads"):
        repo_type = self._repo_type(repo_type)
        query = str(query or "").strip()
        if len(query) > 160:
            raise HuggingFaceError("A pesquisa deve ter no máximo 160 caracteres.")
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise HuggingFaceError("Limite de resultados inválido.") from exc
        if not 1 <= limit <= 30:
            raise HuggingFaceError("O limite de pesquisa deve ficar entre 1 e 30.")
        sort = str(sort or "downloads")
        if sort not in self.SORTS:
            raise HuggingFaceError("Ordenação não permitida.")
        params = {"limit": limit, "sort": sort, "direction": "-1"}
        if query:
            params["search"] = query
        payload = self._request_json(
            f"{self.API}/{repo_type}s?{urlencode(params)}"
        )
        if not isinstance(payload, list):
            raise HuggingFaceError("Formato inesperado na pesquisa do Hub.")
        return [self._summary(item, repo_type) for item in payload if isinstance(item, dict)]

    @staticmethod
    def _summary(item, repo_type):
        card = item.get("cardData") if isinstance(item.get("cardData"), dict) else {}
        return {
            "id": str(item.get("id") or item.get("modelId") or ""),
            "repo_type": repo_type,
            "private": bool(item.get("private", False)),
            "gated": item.get("gated", False),
            "downloads": item.get("downloads"),
            "likes": item.get("likes"),
            "pipeline_tag": item.get("pipeline_tag"),
            "library_name": item.get("library_name"),
            "license": card.get("license") or next(
                (tag.split(":", 1)[1] for tag in (item.get("tags") or [])
                 if isinstance(tag, str) and tag.startswith("license:")), None
            ),
            "tags": [str(tag) for tag in (item.get("tags") or [])[:30]],
            "sha": item.get("sha"),
            "last_modified": item.get("lastModified"),
            "url": "https://huggingface.co/" + str(item.get("id") or item.get("modelId") or ""),
        }

    def details(self, repo_type, repo_id):
        repo_type = self._repo_type(repo_type)
        repo_id = self._repo_id(repo_id)
        payload = self._request_json(
            f"{self.API}/{repo_type}s/{quote(repo_id, safe='/')}?blobs=true"
        )
        if not isinstance(payload, dict):
            raise HuggingFaceError("Formato inesperado nos detalhes do Hub.")
        result = self._summary(payload, repo_type)
        card = payload.get("cardData") if isinstance(payload.get("cardData"), dict) else {}
        siblings = []
        for item in payload.get("siblings", []) or []:
            if not isinstance(item, dict):
                continue
            lfs = item.get("lfs") if isinstance(item.get("lfs"), dict) else {}
            siblings.append({
                "path": str(item.get("rfilename") or ""),
                "size": item.get("size") if item.get("size") is not None else lfs.get("size"),
            })
        result.update({
            "description": str(card.get("description") or payload.get("description") or "")[:2000],
            "card_data": {
                str(key): value for key, value in card.items()
                if key in {"license", "language", "pipeline_tag", "tags", "datasets", "metrics"}
            },
            "siblings": siblings[:500],
            "private": bool(payload.get("private", False)),
            "gated": payload.get("gated", False),
            "sha": str(payload.get("sha") or ""),
        })
        return result

    @staticmethod
    def _safe_repo_file(path):
        value = str(path or "").replace("\\", "/")
        parts = value.split("/")
        return (
            bool(value) and not value.startswith("/") and
            all(part not in {"", ".", ".."} for part in parts)
        )

    def _allowed_files(self, repo_type, siblings):
        extensions = self.MODEL_EXTENSIONS if repo_type == "model" else self.DATASET_EXTENSIONS
        selected = []
        total = 0
        unknown_sizes = []
        for item in siblings:
            path = str(item.get("path") or "")
            if not self._safe_repo_file(path):
                raise HuggingFaceError("O repositório contém caminho de arquivo inseguro.")
            if Path(path).suffix.lower() not in extensions:
                continue
            # Never download executable model code or pickle-based weights.
            if Path(path).suffix.lower() in {".py", ".bin", ".pt", ".pth", ".pkl", ".pickle"}:
                continue
            size = item.get("size")
            try:
                size = int(size)
            except (TypeError, ValueError):
                unknown_sizes.append(path)
                continue
            if size < 0:
                raise HuggingFaceError("Metadado de tamanho inválido.")
            total += size
            selected.append(path)
        if unknown_sizes:
            raise HuggingFaceError(
                "Não foi possível estimar o tamanho de todos os arquivos permitidos; "
                "download cancelado por segurança."
            )
        if repo_type == "model":
            has_config = "config.json" in selected
            has_gguf = any(Path(path).suffix.lower() == ".gguf" for path in selected)
            has_weights = any(
                Path(path).suffix.lower() in {".safetensors", ".gguf", ".onnx"}
                for path in selected
            )
            if not has_weights or (not has_config and not has_gguf):
                raise HuggingFaceError(
                    "Modelo sem config.json + pesos permitidos, ou sem um arquivo GGUF."
                )
        elif not any(
            Path(path).suffix.lower() in self.DATASET_EXTENSIONS - {".md", ".yaml", ".yml"}
            for path in selected
        ):
            raise HuggingFaceError("Dataset sem arquivo de dados compatível.")
        return selected, total

    def download(self, repo_type, repo_id, max_bytes=None):
        repo_type = self._repo_type(repo_type)
        if repo_type == "space":
            raise HuggingFaceError(
                "Spaces são catalogados, mas não baixados nem executados pela NixLMs."
            )
        repo_id = self._repo_id(repo_id)
        hard_limit = self.HARD_MODEL_LIMIT if repo_type == "model" else self.HARD_DATASET_LIMIT
        default_limit = hard_limit
        if max_bytes is None:
            max_bytes = default_limit
        try:
            max_bytes = int(max_bytes)
        except (TypeError, ValueError) as exc:
            raise HuggingFaceError("Limite de download inválido.") from exc
        if max_bytes < 1 or max_bytes > hard_limit:
            raise HuggingFaceError(
                f"Limite máximo permitido: {hard_limit // (1024 * 1024)} MB."
            )
        info = self.details(repo_type, repo_id)
        if info.get("private") or info.get("gated") not in (False, None):
            raise HuggingFaceError("Somente repositórios públicos e não gated são permitidos.")
        revision = info.get("sha", "")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise HuggingFaceError("O Hub não forneceu SHA imutável; download cancelado.")
        files, estimated_bytes = self._allowed_files(repo_type, info["siblings"])
        if estimated_bytes > max_bytes:
            raise HuggingFaceError(
                f"Download estimado em {estimated_bytes} bytes; limite configurado em {max_bytes}."
            )
        if self.downloader is None:
            try:
                from huggingface_hub import snapshot_download
            except ImportError as exc:
                raise HuggingFaceError(
                    "Suporte de download ausente. Instale requirements-hf-hub.txt."
                ) from exc
            downloader = snapshot_download
        else:
            downloader = self.downloader

        base = self.models_dir if repo_type == "model" else self.datasets_dir
        target = (base / repo_id).resolve()
        if base.resolve() not in target.parents:
            raise HuggingFaceError("Destino de download inválido.")
        if target.exists():
            raise HuggingFaceError(
                "O destino já existe. A NixLMs não sobrescreve downloads locais."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".hf-download-", dir=str(target.parent)))
        try:
            downloader(
                repo_id,
                repo_type=repo_type,
                revision=revision,
                token=False,
                local_dir=str(temporary),
                allow_patterns=files,
            )
            actual_bytes = sum(
                path.stat().st_size for path in temporary.rglob("*")
                if path.is_file() and not path.is_symlink()
            )
            if actual_bytes > max_bytes:
                raise HuggingFaceError("Download excedeu o limite após a transferência.")
            if repo_type == "model" and not (temporary / "config.json").is_file() and not any(temporary.rglob("*.gguf")):
                raise HuggingFaceError("Download incompleto: config.json ausente.")
            if not any(
                path.is_file() and path.suffix.lower() in (
                    {".safetensors", ".gguf", ".onnx"} if repo_type == "model"
                    else self.DATASET_EXTENSIONS - {".md", ".yaml", ".yml"}
                )
                for path in temporary.rglob("*")
            ):
                raise HuggingFaceError("Download não contém artefato de dados/pesos.")
            os.replace(str(temporary), str(target))
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        entry = {
            "repo_id": repo_id, "repo_type": repo_type,
            "path": str(target), "revision": revision,
            "license": info.get("license"), "pipeline_tag": info.get("pipeline_tag"),
            "library_name": info.get("library_name"),
            "estimated_bytes": estimated_bytes, "downloaded_bytes": actual_bytes,
            "files": files, "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._registry_lock:
            registry = self._load_registry()
            registry = [
                item for item in registry
                if not (item.get("repo_type") == repo_type and item.get("repo_id") == repo_id)
            ]
            registry.append(entry)
            self._save_registry(registry)
        return entry

    def _load_registry(self):
        try:
            value = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _save_registry(self, value):
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temporary), str(self.registry_path))

    def local_repositories(self):
        return self._load_registry()

    def active_model(self):
        try:
            value = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        path = Path(str(value.get("path", ""))).resolve()
        if self.models_dir.resolve() not in path.parents:
            return None
        has_safetensors = any(path.rglob("*.safetensors"))
        has_gguf = any(path.rglob("*.gguf"))
        if not has_gguf and (not (path / "config.json").is_file() or not has_safetensors):
            return None
        return value

    def activate_model(self, repo_id):
        repo_id = self._repo_id(repo_id)
        entry = next((
            item for item in self._load_registry()
            if item.get("repo_type") == "model" and item.get("repo_id") == repo_id
        ), None)
        if not entry:
            raise HuggingFaceError("Modelo não encontrado no registro de downloads locais.")
        if entry.get("pipeline_tag") != "text-generation":
            raise HuggingFaceError("Ativação de geração exige um modelo com tarefa text-generation.")
        path = Path(entry.get("path", "")).resolve()
        if self.models_dir.resolve() not in path.parents:
            raise HuggingFaceError("Caminho local do modelo não permitido.")
        has_safetensors = any(path.rglob("*.safetensors"))
        has_gguf = any(path.rglob("*.gguf"))
        if not has_gguf and (not (path / "config.json").is_file() or not has_safetensors):
            raise HuggingFaceError(
                "Geração exige Safetensors com config.json ou um arquivo GGUF."
            )
        value = {
            "repo_id": repo_id, "path": str(path), "revision": entry.get("revision"),
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.active_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temporary), str(self.active_path))
        return value

    def active_encoder(self):
        try:
            value = json.loads(self.active_encoder_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        path = Path(str(value.get("path", ""))).resolve()
        if self.models_dir.resolve() not in path.parents:
            return None
        if not (path / "config.json").is_file() or not any(path.rglob("*.safetensors")):
            return None
        return value

    def activate_encoder(self, repo_id):
        repo_id = self._repo_id(repo_id)
        entry = next((
            item for item in self._load_registry()
            if item.get("repo_type") == "model" and item.get("repo_id") == repo_id
        ), None)
        if not entry:
            raise HuggingFaceError("Encoder não encontrado no registro de downloads locais.")
        if (
            entry.get("pipeline_tag") not in {"sentence-similarity", "feature-extraction"}
            or entry.get("library_name") != "sentence-transformers"
        ):
            raise HuggingFaceError(
                "Ativação de embeddings exige sentence-similarity ou feature-extraction."
            )
        path = Path(entry.get("path", "")).resolve()
        if self.models_dir.resolve() not in path.parents:
            raise HuggingFaceError("Caminho local do encoder não permitido.")
        if not (path / "config.json").is_file() or not any(path.rglob("*.safetensors")):
            raise HuggingFaceError("Encoder exige config.json e pesos Safetensors.")
        value = {
            "repo_id": repo_id, "path": str(path), "revision": entry.get("revision"),
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.active_encoder_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temporary), str(self.active_encoder_path))
        return value

    def active_perception(self):
        try:
            value = json.loads(self.active_perception_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        if not isinstance(value, dict):
            return {}
        valid = {}
        for role in ("vision", "speech"):
            item = value.get(role)
            if not isinstance(item, dict):
                continue
            path = Path(str(item.get("path", ""))).resolve()
            if (
                self.models_dir.resolve() in path.parents
                and (path / "config.json").is_file()
                and any(path.rglob("*.safetensors"))
            ):
                valid[role] = item
        return valid

    def activate_perception(self, repo_id, role):
        repo_id = self._repo_id(repo_id)
        role = str(role or "").lower()
        expected_task = {
            "vision": "image-to-text",
            "speech": "automatic-speech-recognition",
        }
        if role not in expected_task:
            raise HuggingFaceError("Use role=vision ou role=speech.")
        entry = next((
            item for item in self._load_registry()
            if item.get("repo_type") == "model" and item.get("repo_id") == repo_id
        ), None)
        if not entry:
            raise HuggingFaceError("Modelo multimodal não encontrado no registro local.")
        if entry.get("pipeline_tag") != expected_task[role]:
            raise HuggingFaceError(
                f"A tarefa do modelo precisa ser {expected_task[role]}."
            )
        path = Path(entry.get("path", "")).resolve()
        if (
            self.models_dir.resolve() not in path.parents
            or not (path / "config.json").is_file()
            or not any(path.rglob("*.safetensors"))
        ):
            raise HuggingFaceError("Percepção exige modelo local com config e Safetensors.")
        value = {
            "repo_id": repo_id, "path": str(path), "revision": entry.get("revision"),
            "task": expected_task[role],
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
        active = self.active_perception()
        active[role] = value
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.active_perception_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temporary), str(self.active_perception_path))
        return value

    def deactivate_perception(self, role):
        role = str(role or "").lower()
        if role not in {"vision", "speech"}:
            raise HuggingFaceError("Use role=vision ou role=speech.")
        active = self.active_perception()
        removed = role in active
        active.pop(role, None)
        if active:
            temporary = self.active_perception_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(str(temporary), str(self.active_perception_path))
        else:
            try:
                self.active_perception_path.unlink()
            except FileNotFoundError:
                pass
        return removed

    def deactivate_encoder(self):
        try:
            self.active_encoder_path.unlink()
            return True
        except FileNotFoundError:
            return False

    def deactivate_model(self):
        try:
            self.active_path.unlink()
            return True
        except FileNotFoundError:
            return False

    def status(self):
        try:
            hub_installed = importlib.util.find_spec("huggingface_hub") is not None
        except (ImportError, ValueError):
            hub_installed = False
        try:
            transformers_installed = importlib.util.find_spec("transformers") is not None
            torch_installed = importlib.util.find_spec("torch") is not None
            datasets_installed = importlib.util.find_spec("datasets") is not None
            evaluate_installed = importlib.util.find_spec("evaluate") is not None
            peft_installed = importlib.util.find_spec("peft") is not None
            diffusers_installed = importlib.util.find_spec("diffusers") is not None
            llama_cpp_installed = importlib.util.find_spec("llama_cpp") is not None
        except (ImportError, ValueError):
            transformers_installed = torch_installed = False
            datasets_installed = evaluate_installed = False
            peft_installed = diffusers_installed = False
            llama_cpp_installed = False
        repositories = self._load_registry()
        return {
            "anonymous_public_access": True,
            "token_required": False,
            "implicit_token_disabled": os.getenv("HF_HUB_DISABLE_IMPLICIT_TOKEN") == "1",
            "paid_remote_inference": False,
            "hub_package_installed": hub_installed,
            "download_support": hub_installed,
            "inference_support": (transformers_installed and torch_installed) or llama_cpp_installed,
            "gguf_support": llama_cpp_installed,
            "datasets_support": datasets_installed,
            "evaluation_support": evaluate_installed,
            "fine_tuning_support": peft_installed,
            "diffusers_support": diffusers_installed,
            "repositories": repositories,
            "active_model": self.active_model(),
            "active_encoder": self.active_encoder(),
            "active_perception": self.active_perception(),
            "limits": {
                "model_bytes": self.HARD_MODEL_LIMIT,
                "dataset_bytes": self.HARD_DATASET_LIMIT,
            },
        }


class HuggingFaceLocalGenerator:
    """Geração causal opcional: CPU, Safetensors/GGUF locais, sem código remoto."""

    def __init__(self, model_path, repo_id="", max_input_tokens=1024,
                 max_new_tokens=160, threads=2, model_loader=None):
        self.model_path = str(Path(model_path).expanduser().resolve())
        self.repo_id = str(repo_id or "")
        self.max_input_tokens = max(64, min(2048, int(max_input_tokens)))
        self.max_new_tokens = max(1, min(256, int(max_new_tokens)))
        self.threads = max(1, min(4, int(threads)))
        self.model_loader = model_loader
        self._model = None
        self._tokenizer = None
        self.last_error = None

    def _load(self):
        if self._model is not None:
            return self._model, self._tokenizer
        path = Path(self.model_path)
        if not path.is_dir():
            raise HuggingFaceError("Diretório de modelo local incompleto.")
        gguf_files = sorted(path.rglob("*.gguf"))
        safetensors_files = list(path.rglob("*.safetensors"))
        if not gguf_files and (not (path / "config.json").is_file() or not safetensors_files):
            raise HuggingFaceError("Inferência exige Safetensors com config.json ou GGUF.")
        if self.model_loader:
            model, tokenizer = self.model_loader(
                model_path=self.model_path, device="cpu",
                local_files_only=True, trust_remote_code=False,
                use_safetensors=bool(safetensors_files), threads=self.threads,
            )
            self._backend = "mocked_local"
        elif gguf_files:
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise HuggingFaceError(
                    "Modelo GGUF requer llama-cpp-python CPU; instale requirements-ml-llama-cpp.txt."
                ) from exc
            model = Llama(
                model_path=str(gguf_files[0]), n_ctx=self.max_input_tokens + self.max_new_tokens,
                n_threads=self.threads, verbose=False,
            )
            tokenizer = None
            self._backend = "llama.cpp_cpu"
        else:
            self._backend = "transformers_cpu"
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                raise HuggingFaceError(
                    "Inferência local ausente. Instale PyTorch CPU e requirements-hf-local.txt."
                ) from exc
            torch.set_num_threads(self.threads)
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, local_files_only=True, trust_remote_code=False
            )
            model = AutoModelForCausalLM.from_pretrained(
                self.model_path, local_files_only=True, trust_remote_code=False,
                use_safetensors=True, low_cpu_mem_usage=True,
                torch_dtype=torch.float32,
            )
            model.to("cpu")
            model.eval()
        self._model, self._tokenizer = model, tokenizer
        return model, tokenizer

    def generate(self, system_prompt, prompt):
        try:
            model, tokenizer = self._load()
            text = (
                "Instruções do sistema:\n" + str(system_prompt)[:5000]
                + "\n\nMensagem/contexto:\n" + str(prompt)[:12000]
                + "\n\nResposta em português brasileiro:"
            )
            if self._backend == "llama.cpp_cpu":
                result = model.create_completion(
                    prompt=text, max_tokens=self.max_new_tokens,
                    temperature=0.1, echo=False,
                )
                answer = str(result.get("choices", [{}])[0].get("text", "")).strip()
            else:
                import torch
                inputs = tokenizer(
                    text, return_tensors="pt", truncation=True,
                    max_length=self.max_input_tokens,
                )
                inputs = {key: value.to("cpu") for key, value in inputs.items()}
                generation_options = {
                    "max_new_tokens": self.max_new_tokens,
                    "do_sample": False,
                    "use_cache": True,
                }
                pad_token_id = (
                    tokenizer.eos_token_id
                    if tokenizer.eos_token_id is not None else tokenizer.pad_token_id
                )
                if pad_token_id is not None:
                    generation_options["pad_token_id"] = pad_token_id
                with torch.inference_mode():
                    output = model.generate(**inputs, **generation_options)
                generated = output[0][inputs["input_ids"].shape[1]:]
                answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
            if not answer:
                self.last_error = "O modelo local não gerou conteúdo."
                return None
            self.last_error = None
            return answer
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def status(self):
        return {
            "provider": "huggingface_local", "repo_id": self.repo_id,
            "model_path": self.model_path, "device": "cpu",
            "local_files_only": True, "loaded": self._model is not None,
            "backend": getattr(self, "_backend", None),
            "last_error": self.last_error,
        }
