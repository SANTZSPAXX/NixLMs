"""Geração multimodal local opcional para a NixLMs.

Modelos são baixados somente por ação explícita. Dependências podem ser
preparadas em segundo plano na inicialização do servidor, sem atualizar
pacotes existentes. Toda inferência é local e usa arquivos já baixados.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

class MediaGenerationError(RuntimeError):
    """Erro controlado do subsistema de geração multimodal."""


class MediaGenerationManager:
    IMAGE_LIMIT = 4 * 1024**3
    VIDEO_LIMIT = 10 * 1024**3
    MODEL_EXTENSIONS = {
        ".safetensors", ".json", ".txt", ".model", ".tiktoken",
        ".vocab", ".merges", ".md", ".yaml", ".yml",
    }
    BLOCKED_PROMPT = re.compile(
        r"\b(child|children|minor|underage|under-age|preteen|pre-teen|"
        r"schoolgirl|schoolboy|loli|shota|infant|toddler)\b",
        re.IGNORECASE,
    )

    def __init__(self, data_dir, hub=None):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.root = self.data_dir / "media"
        self.models_dir = self.root / "models"
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.registry_path = self.root / "registry.json"
        self.settings_path = self.root / "settings.json"
        self.bootstrap_path = self.root / "bootstrap.json"
        self.hub = hub
        self._lock = threading.RLock()
        self._pipelines = {}
        for path in (self.models_dir, self.input_dir, self.output_dir):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _repo_id(value):
        value = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}", value):
            raise MediaGenerationError("ID inválido; use autor/nome.")
        return value

    def _read_json(self, path, fallback):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value
        except (OSError, UnicodeError, json.JSONDecodeError):
            return fallback

    def _write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)

    def settings(self):
        value = self._read_json(self.settings_path, {})
        return {"nsfw_enabled": bool(value.get("nsfw_enabled", False))}

    def set_nsfw(self, enabled):
        if not isinstance(enabled, bool):
            raise MediaGenerationError("O estado NSFW deve ser booleano.")
        self._write_json(self.settings_path, {"nsfw_enabled": enabled})
        return self.settings()

    def _validate_prompt(self, prompt, nsfw=False):
        prompt = str(prompt or "").strip()
        if not prompt or len(prompt) > 4000:
            raise MediaGenerationError("Prompt vazio ou acima de 4.000 caracteres.")
        if nsfw and self.BLOCKED_PROMPT.search(prompt):
            raise MediaGenerationError("Prompt bloqueado: conteúdo sexual ou sugestivo envolvendo menores não é permitido.")
        if nsfw and not self.settings()["nsfw_enabled"]:
            raise MediaGenerationError("Modo NSFW desativado. Ative-o explicitamente nas configurações locais.")
        if nsfw and re.search(r"\b(real person|real people|celebrity|public figure|deepfake)\b", prompt, re.I):
            raise MediaGenerationError("O modo adulto aceita somente personagens fictícios; pessoas reais não são permitidas.")
        return prompt

    def _registry(self):
        value = self._read_json(self.registry_path, [])
        return value if isinstance(value, list) else []

    def status(self):
        registry = self._registry()
        packages = {}
        for module in ("torch", "diffusers", "transformers", "accelerate", "safetensors", "PIL", "imageio"):
            try:
                packages[module] = importlib.util.find_spec(module) is not None
            except (ImportError, ValueError, ModuleNotFoundError):
                packages[module] = False
        return {
            "ok": all(packages.values()) and bool(registry),
            "packages": packages,
            "models": registry,
            "nsfw_enabled": self.settings()["nsfw_enabled"],
            "auto_install": os.getenv("NIXLMS_AUTO_INSTALL_MEDIA", "1") != "0",
            "model_downloads_require_confirmation": True,
            "inference": "local-only",
            "bootstrap": self._read_json(self.bootstrap_path, {"status": "not_started"}),
        }

    def bootstrap_async(self, enabled=True):
        """Instala apenas dependências ausentes em background; não atualiza as existentes."""
        if not enabled:
            return {"started": False, "reason": "disabled"}
        if self._bootstrap_thread_alive():
            return {"started": False, "reason": "already_running"}
        state = self._read_json(self.bootstrap_path, {})
        last = state.get("attempted_at")
        if last:
            try:
                from datetime import timedelta
                attempted = datetime.fromisoformat(last)
                if (datetime.now(timezone.utc) - attempted).total_seconds() < 86400:
                    return {"started": False, "reason": "attempted_within_24h", "state": state}
            except (TypeError, ValueError):
                pass
        self._bootstrap_thread = threading.Thread(
            target=self._bootstrap_worker, name="nixlms-media-bootstrap", daemon=True
        )
        self._bootstrap_thread.start()
        return {"started": True}

    def _bootstrap_thread_alive(self):
        thread = getattr(self, "_bootstrap_thread", None)
        return bool(thread and thread.is_alive())

    def _bootstrap_worker(self):
        state = {
            "attempted_at": datetime.now(timezone.utc).isoformat(),
            "status": "installing",
        }
        self._write_json(self.bootstrap_path, state)
        try:
            def missing(module):
                try:
                    return importlib.util.find_spec(module) is None
                except (ImportError, ValueError, ModuleNotFoundError):
                    return True

            # Preserve an existing CUDA/CPU Torch installation. If absent, install
            # the official CPU wheel instead of guessing a CUDA runtime.
            if missing("torch"):
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                     "torch", "--index-url", "https://download.pytorch.org/whl/cpu"],
                    check=True, timeout=1800, capture_output=True, text=True,
                )
            packages = [
                ("diffusers", "diffusers>=0.30,<1"),
                ("transformers", "transformers>=4.45,<6"),
                ("accelerate", "accelerate>=1,<2"),
                ("safetensors", "safetensors>=0.4"),
                ("PIL", "Pillow>=10"),
                ("imageio", "imageio>=2.34"),
                ("imageio_ffmpeg", "imageio-ffmpeg>=0.5"),
                ("huggingface_hub", "huggingface-hub>=0.25"),
            ]
            missing_specs = [spec for module, spec in packages if missing(module)]
            if missing_specs:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *missing_specs],
                    check=True, timeout=1800, capture_output=True, text=True,
                )
            state.update({"status": "ready", "completed_at": datetime.now(timezone.utc).isoformat()})
        except Exception as exc:
            state.update({
                "status": "failed",
                "error": type(exc).__name__ + ": " + str(exc)[:500],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
        self._write_json(self.bootstrap_path, state)

    def download_model(self, repo_id, mode, confirm=False):
        if confirm is not True:
            raise MediaGenerationError("Download exige confirmação explícita (confirm=true).")
        repo_id = self._repo_id(repo_id)
        mode = str(mode or "").lower()
        if mode not in {"text-to-image", "image-to-image", "image-to-video"}:
            raise MediaGenerationError("Modo inválido.")
        if self.hub is None:
            raise MediaGenerationError("Integração Hugging Face indisponível.")
        info = self.hub.details("model", repo_id)
        if info.get("private") or info.get("gated") not in (False, None):
            raise MediaGenerationError("Somente modelos públicos e não gated são aceitos.")
        sha = str(info.get("sha") or "")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
            raise MediaGenerationError("SHA imutável ausente; download cancelado.")
        files, total = [], 0
        for item in info.get("siblings", []):
            name = str(item.get("path") or "").replace("\\", "/")
            if not name or name.startswith("/") or any(p in {"", ".", ".."} for p in name.split("/")):
                raise MediaGenerationError("O repositório contém caminho inseguro.")
            if Path(name).suffix.lower() not in self.MODEL_EXTENSIONS:
                continue
            if Path(name).suffix.lower() in {".py", ".bin", ".pt", ".pth", ".pkl", ".pickle"}:
                continue
            size = item.get("size")
            if size is None:
                raise MediaGenerationError("Tamanho desconhecido em arquivo permitido; download cancelado.")
            size = int(size)
            if size < 0:
                raise MediaGenerationError("Tamanho inválido.")
            files.append(name)
            total += size
        limit = self.VIDEO_LIMIT if mode == "image-to-video" else self.IMAGE_LIMIT
        if not files or total > limit:
            raise MediaGenerationError(f"Download estimado em {total} bytes; limite para este modo: {limit} bytes.")
        target = (self.models_dir / repo_id).resolve()
        if self.models_dir.resolve() not in target.parents:
            raise MediaGenerationError("Destino inválido.")
        if target.exists():
            raise MediaGenerationError("Modelo já existe localmente; não será sobrescrito.")
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise MediaGenerationError("huggingface_hub ausente; aguarde o bootstrap ou instale requirements-hf-media.txt.") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".media-download-", dir=str(target.parent)))
        try:
            snapshot_download(
                repo_id, repo_type="model", revision=sha, token=False,
                local_dir=str(temporary), allow_patterns=files,
            )
            actual = sum(p.stat().st_size for p in temporary.rglob("*") if p.is_file() and not p.is_symlink())
            if actual > limit:
                raise MediaGenerationError("Download excedeu o limite após a transferência.")
            if not (temporary / "model_index.json").is_file():
                raise MediaGenerationError("Modelo Diffusers inválido: model_index.json ausente.")
            if not any(temporary.rglob("*.safetensors")):
                raise MediaGenerationError("Modelo sem pesos Safetensors permitidos; download cancelado.")
            os.replace(temporary, target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        entry = {
            "repo_id": repo_id, "mode": mode, "path": str(target),
            "revision": sha, "license": info.get("license"),
            "estimated_bytes": total, "downloaded_bytes": actual,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        registry = [x for x in self._registry() if x.get("repo_id") != repo_id]
        registry.append(entry)
        self._write_json(self.registry_path, registry)
        return entry

    def _model_entry(self, repo_id, mode):
        repo_id = self._repo_id(repo_id)
        entry = next((x for x in self._registry() if x.get("repo_id") == repo_id), None)
        compatible = entry and (
            entry.get("mode") == mode
            or (mode == "image-to-image" and entry.get("mode") == "text-to-image")
        )
        if not compatible:
            raise MediaGenerationError("Baixe primeiro um modelo compatível com este modo.")
        path = Path(entry.get("path", "")).resolve()
        if self.models_dir.resolve() not in path.parents or not (path / "model_index.json").is_file():
            raise MediaGenerationError("Caminho local do modelo inválido ou incompleto.")
        return entry, path

    def _pipeline(self, repo_id, mode):
        key = (repo_id, mode)
        with self._lock:
            if key in self._pipelines:
                return self._pipelines[key]
            _, path = self._model_entry(repo_id, mode)
            try:
                import torch
                from diffusers import AutoPipelineForImage2Image, AutoPipelineForText2Image, DiffusionPipeline
            except ImportError as exc:
                raise MediaGenerationError("Dependências de mídia ainda não estão prontas.") from exc
            kwargs = {"torch_dtype": torch.float32, "local_files_only": True}
            if mode == "text-to-image":
                pipe = AutoPipelineForText2Image.from_pretrained(str(path), **kwargs)
            elif mode == "image-to-image":
                pipe = AutoPipelineForImage2Image.from_pretrained(str(path), **kwargs)
            else:
                # I2V pipelines vary by architecture; DiffusionPipeline resolves
                # the class from the downloaded model's local model_index.json.
                pipe = DiffusionPipeline.from_pretrained(str(path), **kwargs)
            pipe.to("cuda" if torch.cuda.is_available() else "cpu")
            self._pipelines[key] = pipe
            return pipe

    def _safe_input(self, relative_path):
        value = str(relative_path or "").strip()
        if not value:
            raise MediaGenerationError("Informe o caminho de uma imagem em data/media/input.")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.input_dir / candidate
        candidate = candidate.resolve()
        if self.input_dir.resolve() not in candidate.parents or not candidate.is_file():
            raise MediaGenerationError("A imagem deve ser um arquivo existente dentro de data/media/input.")
        if candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise MediaGenerationError("Formato de imagem não permitido.")
        if candidate.stat().st_size > 20 * 1024 * 1024:
            raise MediaGenerationError("Imagem acima do limite de 20 MB.")
        return candidate

    def generate(self, mode, repo_id, prompt, image_path=None, nsfw=False,
                 negative_prompt="", steps=20, guidance=7.0, strength=0.65,
                 width=512, height=512, frames=16):
        mode = str(mode or "").lower()
        if mode not in {"text-to-image", "image-to-image", "image-to-video"}:
            raise MediaGenerationError("Modo inválido.")
        if not isinstance(nsfw, bool):
            raise MediaGenerationError("O sinalizador NSFW deve ser booleano.")
        prompt = self._validate_prompt(prompt, nsfw=nsfw)
        if nsfw and not self.settings()["nsfw_enabled"]:
            raise MediaGenerationError("Modo NSFW desativado.")
        steps, width, height, frames = int(steps), int(width), int(height), int(frames)
        guidance = float(guidance)
        strength = float(strength)
        if (not 1 <= steps <= 40 or width not in {256, 384, 512, 640, 768}
                or height not in {256, 384, 512, 640, 768} or not 1 <= frames <= 24
                or not 0.0 <= guidance <= 20.0 or not 0.1 <= strength <= 0.95):
            raise MediaGenerationError("Parâmetros fora dos limites seguros.")
        pipe = self._pipeline(repo_id, mode)
        kwargs = {"prompt": prompt, "num_inference_steps": steps}
        if negative_prompt:
            kwargs["negative_prompt"] = str(negative_prompt)[:1000]
        if mode == "text-to-image":
            kwargs.update({"width": width, "height": height, "guidance_scale": float(guidance)})
        else:
            source = self._safe_input(image_path)
            try:
                from PIL import Image
                image = Image.open(source).convert("RGB")
            except Exception as exc:
                raise MediaGenerationError("Não foi possível abrir a imagem de entrada.") from exc
            if mode == "image-to-image":
                kwargs.update({"image": image, "strength": max(0.1, min(0.95, float(strength))),
                               "guidance_scale": float(guidance)})
            else:
                kwargs.update({"image": image, "num_frames": frames})
        try:
            result = pipe(**kwargs)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            if mode == "image-to-video":
                try:
                    from diffusers.utils import export_to_video
                    output = self.output_dir / f"nix_{stamp}.mp4"
                    export_to_video(result.frames[0], str(output), fps=8)
                except Exception as exc:
                    raise MediaGenerationError("O pipeline não retornou frames de vídeo compatíveis.") from exc
            else:
                output = self.output_dir / f"nix_{stamp}.png"
                result.images[0].save(output, format="PNG")
        except MediaGenerationError:
            raise
        except Exception as exc:
            raise MediaGenerationError("Falha na geração local: " + type(exc).__name__) from exc
        return {"mode": mode, "output": str(output), "bytes": output.stat().st_size,
                "created_at": datetime.now(timezone.utc).isoformat(), "nsfw_mode": bool(nsfw)}
