"""Instalação e gerenciamento explícito do Ollama para a NixLMs.

Nenhuma operação de instalação, inicialização ou download é executada ao importar
este módulo. O chamador deve obter consentimento explícito antes de invocá-las.
"""
import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


class OllamaManager:
    DEFAULT_MODEL = "qwen2.5:0.5b"
    INSTALL_URL = "https://ollama.com/install.sh"

    def __init__(self, language_engine, readiness_timeout=45):
        self.language = language_engine
        self.readiness_timeout = max(1, int(readiness_timeout))
        self.process = None
        self.last_error = None
        self.last_action = None

    @staticmethod
    def _platform():
        return platform.system().lower()

    def executable(self):
        found = shutil.which("ollama")
        if found:
            return found
        system = self._platform()
        candidates = []
        if system == "windows":
            local = os.getenv("LOCALAPPDATA", "")
            program_files = os.getenv("ProgramFiles", r"C:\Program Files")
            if local:
                candidates.append(Path(local) / "Programs" / "Ollama" / "ollama.exe")
            candidates.append(Path(program_files) / "Ollama" / "ollama.exe")
        elif system == "linux":
            candidates.extend((Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")))
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return None

    def status(self):
        return {
            "installed": self.executable() is not None,
            "executable": self.executable(),
            "service_reachable": bool(self.language.reachable),
            "endpoint": self.language.host,
            "model": self.language.model,
            "model_installed": self.language.model in self.language.installed_models,
            "installed_models": list(self.language.installed_models),
            "last_action": self.last_action,
            "last_error": self.last_error or self.language.last_error,
        }

    def install(self):
        """Instala Ollama; deve ser chamado somente após consentimento do usuário."""
        system = self._platform()
        try:
            if system == "windows":
                winget = shutil.which("winget")
                if not winget:
                    raise RuntimeError(
                        "winget não foi encontrado. Instale o App Installer da Microsoft "
                        "ou instale o Ollama manualmente em https://ollama.com/download."
                    )
                result = subprocess.run(
                    [winget, "install", "--id", "Ollama.Ollama", "--exact", "--silent",
                     "--accept-package-agreements", "--accept-source-agreements"],
                    check=False, capture_output=True, text=True, timeout=900,
                )
                if result.returncode != 0 and self.executable() is None:
                    detail = (result.stderr or result.stdout or "").strip()
                    raise RuntimeError(
                        f"winget falhou (código {result.returncode}): {detail[-1200:]}"
                    )
            elif system == "linux":
                if shutil.which("zstd") is None and shutil.which("apt-get"):
                    update = subprocess.run(
                        ["apt-get", "update", "-qq"], check=False,
                        capture_output=True, text=True, timeout=900,
                    )
                    if update.returncode != 0:
                        raise RuntimeError(
                            "Não foi possível atualizar os índices do apt para instalar "
                            f"zstd: {(update.stderr or update.stdout)[-1000:]}"
                        )
                    install_zstd = subprocess.run(
                        ["apt-get", "install", "-y", "-qq", "zstd"], check=False,
                        capture_output=True, text=True, timeout=900,
                    )
                    if install_zstd.returncode != 0:
                        raise RuntimeError(
                            "Não foi possível instalar zstd: "
                            f"{(install_zstd.stderr or install_zstd.stdout)[-1000:]}"
                        )
                with urlopen(self.INSTALL_URL, timeout=30) as response:
                    script = response.read()
                if not script or len(script) > 2_000_000:
                    raise RuntimeError("O instalador oficial retornou um script vazio ou inesperadamente grande.")
                result = subprocess.run(
                    ["bash"], input=script, check=False, capture_output=True,
                    timeout=1200,
                )
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout).decode("utf-8", "replace")
                    raise RuntimeError(
                        f"Instalador oficial do Ollama falhou (código {result.returncode}): {detail[-1600:]}"
                    )
            else:
                raise RuntimeError(
                    f"Instalação automática não suportada em {system or 'sistema desconhecido'}. "
                    "Baixe o instalador em https://ollama.com/download."
                )

            binary = self.executable()
            if not binary:
                raise RuntimeError(
                    "O instalador terminou, mas o executável 'ollama' não foi localizado. "
                    "Reinicie o terminal ou verifique a instalação e o PATH."
                )
            self.last_action = "installed"
            self.last_error = None
            return {"ok": True, "executable": binary}
        except (OSError, subprocess.SubprocessError, RuntimeError, Exception) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.last_action = "install_failed"
            return {"ok": False, "error": self.last_error}

    def start_service(self):
        """Inicia 'ollama serve' se a API local ainda não responder."""
        if not self.language.local_host:
            self.last_error = "Inicialização recusada: o endpoint precisa ser loopback local."
            self.last_action = "start_refused"
            return {"ok": False, "error": self.last_error}
        self.language.refresh_models()
        if self.language.reachable:
            self.last_action = "already_running"
            self.last_error = None
            return {"ok": True, "already_running": True}

        binary = self.executable()
        if not binary:
            self.last_error = "Executável Ollama não instalado."
            self.last_action = "start_failed"
            return {"ok": False, "error": self.last_error}
        try:
            log_dir = Path.home() / ".nixlms"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "ollama.log"
            log_handle = open(log_path, "ab")
            kwargs = {}
            if self._platform() == "windows":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(
                [binary, "serve"], stdout=log_handle, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, **kwargs,
            )
            log_handle.close()
            deadline = time.monotonic() + self.readiness_timeout
            while time.monotonic() < deadline:
                self.language.refresh_models()
                if self.language.reachable:
                    self.last_action = "started"
                    self.last_error = None
                    return {"ok": True, "already_running": False, "log": str(log_path)}
                if self.process.poll() is not None:
                    break
                time.sleep(1)
            detail = self.language.last_error or "tempo limite aguardando /api/tags."
            raise RuntimeError(
                f"Ollama não ficou pronto em {self.readiness_timeout}s: {detail} "
                f"Consulte {log_path}."
            )
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.last_action = "start_failed"
            return {"ok": False, "error": self.last_error}

    def pull_model(self, model=None):
        """Baixa um modelo após consentimento; valida presença via /api/tags."""
        model = str(model or self.DEFAULT_MODEL).strip()
        if not model or any(char.isspace() for char in model):
            self.last_error = "Nome de modelo inválido."
            self.last_action = "pull_failed"
            return {"ok": False, "error": self.last_error}
        self.language.refresh_models()
        if not self.language.reachable:
            self.last_error = (
                "O serviço Ollama não está acessível. Inicie o serviço antes de baixar o modelo. "
                + str(self.language.last_error or "")
            )
            self.last_action = "pull_failed"
            return {"ok": False, "error": self.last_error}
        if model in self.language.installed_models:
            self.language.model = model
            self.last_action = "model_already_installed"
            self.last_error = None
            return {"ok": True, "already_installed": True, "model": model}
        binary = self.executable()
        if not binary:
            self.last_error = "Executável Ollama não encontrado para executar o download."
            self.last_action = "pull_failed"
            return {"ok": False, "error": self.last_error}
        try:
            result = subprocess.run(
                [binary, "pull", model], check=False, capture_output=True,
                text=True, timeout=3600,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                raise RuntimeError(
                    f"ollama pull {model} falhou (código {result.returncode}): {detail[-1600:]}"
                )
            installed = self.language.refresh_models()
            if model not in installed:
                raise RuntimeError(
                    f"Download terminou, mas {model} não apareceu em /api/tags. "
                    f"Modelos detectados: {', '.join(installed) or 'nenhum'}."
                )
            self.language.model = model
            self.last_action = "model_downloaded"
            self.last_error = None
            return {"ok": True, "model": model, "installed_models": installed}
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.last_action = "pull_failed"
            return {"ok": False, "error": self.last_error}
