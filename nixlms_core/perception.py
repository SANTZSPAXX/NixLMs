"""Percepção multimodal opcional com modelos estritamente locais.

Nenhum modelo é baixado. O usuário precisa fornecer caminhos para modelos já
armazenados no computador; a inferência usa CPU por padrão.
"""
import importlib.util
import os
import threading
from pathlib import Path


class PerceptionManager:
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
    AUDIO_EXTENSIONS = {".wav"}

    def __init__(self, vision_model_path=None, speech_model_path=None,
                 max_image_bytes=10 * 1024 * 1024,
                 max_audio_bytes=20 * 1024 * 1024):
        self.vision_model_path = self._model_path(
            vision_model_path or os.getenv("NIXLMS_VISION_MODEL_PATH")
        )
        self.speech_model_path = self._model_path(
            speech_model_path or os.getenv("NIXLMS_SPEECH_MODEL_PATH")
        )
        self.max_image_bytes = int(max_image_bytes)
        self.max_audio_bytes = int(max_audio_bytes)
        if self.max_image_bytes <= 0 or self.max_audio_bytes <= 0:
            raise ValueError("Limites de arquivo precisam ser positivos.")
        self._pipelines = {}
        self._lock = threading.RLock()

    @staticmethod
    def _model_path(value):
        if value is None or not str(value).strip():
            return None
        return Path(value).expanduser()

    @staticmethod
    def _transformers_available():
        try:
            return importlib.util.find_spec("transformers") is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            return False

    @staticmethod
    def _torch_available():
        try:
            return importlib.util.find_spec("torch") is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            return False

    @staticmethod
    def _validate_file(path, extensions, max_bytes, label):
        target = Path(path).expanduser()
        if not target.is_file():
            raise ValueError(f"Arquivo de {label} não encontrado.")
        if target.suffix.lower() not in extensions:
            raise ValueError(f"Formato de {label} não permitido.")
        size = target.stat().st_size
        if size <= 0 or size > max_bytes:
            raise ValueError(f"Arquivo de {label} vazio ou acima do limite.")
        return target.resolve()

    def _get_pipeline(self, task, model_path):
        if model_path is None or not model_path.is_dir():
            raise RuntimeError(
                "Configure um diretório de modelo local; downloads automáticos estão desativados."
            )
        if not self._transformers_available():
            raise RuntimeError(
                "Transformers não está instalado. A percepção é opcional."
            )
        if not self._torch_available():
            raise RuntimeError(
                "PyTorch não está instalado. Instale a dependência opcional compatível com CPU."
            )
        key = (task, str(model_path.resolve()))
        with self._lock:
            if key not in self._pipelines:
                from transformers import pipeline
                self._pipelines[key] = pipeline(
                    task,
                    model=str(model_path.resolve()),
                    device=-1,
                    model_kwargs={"local_files_only": True},
                )
            return self._pipelines[key]

    def describe_image(self, path):
        target = self._validate_file(
            path, self.IMAGE_EXTENSIONS, self.max_image_bytes, "imagem"
        )
        processor = self._get_pipeline("image-to-text", self.vision_model_path)
        result = processor(str(target), max_new_tokens=96)
        if not isinstance(result, list) or not result:
            raise RuntimeError("O modelo de visão não retornou uma descrição.")
        text = str(result[0].get("generated_text", "")).strip()
        if not text:
            raise RuntimeError("O modelo de visão retornou texto vazio.")
        return {
            "modality": "image",
            "path": str(target),
            "description": text,
            "model": str(self.vision_model_path),
            "device": "cpu",
            "downloaded_model": False,
        }

    def transcribe_audio(self, path):
        target = self._validate_file(
            path, self.AUDIO_EXTENSIONS, self.max_audio_bytes, "áudio"
        )
        processor = self._get_pipeline(
            "automatic-speech-recognition", self.speech_model_path
        )
        result = processor(str(target))
        text = str(result.get("text", "")).strip() if isinstance(result, dict) else ""
        if not text:
            raise RuntimeError("O modelo de áudio não retornou uma transcrição.")
        return {
            "modality": "audio",
            "path": str(target),
            "transcription": text,
            "model": str(self.speech_model_path),
            "device": "cpu",
            "downloaded_model": False,
        }

    def status(self):
        return {
            "enabled": True,
            "transformers_installed": self._transformers_available(),
            "pytorch_installed": self._torch_available(),
            "vision": {
                "configured": self.vision_model_path is not None,
                "model_path_exists": bool(
                    self.vision_model_path and self.vision_model_path.is_dir()
                ),
                "task": "image-to-text",
            },
            "speech": {
                "configured": self.speech_model_path is not None,
                "model_path_exists": bool(
                    self.speech_model_path and self.speech_model_path.is_dir()
                ),
                "task": "automatic-speech-recognition",
            },
            "device": "cpu",
            "automatic_downloads": False,
            "image_extensions": sorted(self.IMAGE_EXTENSIONS),
            "audio_extensions": sorted(self.AUDIO_EXTENSIONS),
            "max_image_bytes": self.max_image_bytes,
            "max_audio_bytes": self.max_audio_bytes,
        }
