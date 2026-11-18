"""Servidor HTTP local da interface NixLMs: núcleo neural, loopback e sem shell remoto."""
from __future__ import annotations

import importlib.util
import json
import mimetypes
import os
import platform
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import metadata
from pathlib import Path
from urllib.parse import urlparse, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
DATA = Path(os.getenv("NIXLMS_DATA_DIR", str(ROOT / "data"))).expanduser()
MAX_BODY = 5 * 1024 * 1024
ALLOWED = {".txt", ".md", ".rst", ".py", ".json", ".yaml", ".yml", ".toml"}
sys.path.insert(0, str(ROOT))

from nixlms_core import NixLMsNeuralCore  # noqa: E402


def inspect_frameworks():
    """Inventário leve sem importar os frameworks."""
    candidates = [
        ("PyTorch", "torch", "Treinamento e inferência tensorial", "torch"),
        ("NumPy", "numpy", "Computação numérica", "numpy"),
        ("SciPy", "scipy", "Algoritmos científicos", "scipy"),
        ("scikit-learn", "sklearn", "Aprendizado de máquina clássico", "scikit-learn"),
        ("Transformers", "transformers", "Modelos Transformer", "transformers"),
        ("Sentence Transformers", "sentence_transformers", "Embeddings semânticos", "sentence-transformers"),
        ("FAISS CPU", "faiss", "Busca vetorial", "faiss-cpu"),
        ("ONNX Runtime", "onnxruntime", "Inferência otimizada", "onnxruntime"),
        ("Safetensors", "safetensors", "Armazenamento de pesos", "safetensors"),
        ("Tokenizers", "tokenizers", "Tokenização", "tokenizers"),
        ("TensorFlow", "tensorflow", "Treinamento e inferência", "tensorflow"),
        ("llama-cpp-python", "llama_cpp", "Inferência local GGUF", "llama-cpp-python"),
    ]
    result = []
    for name, module, purpose, distribution in candidates:
        try:
            installed = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            installed = False
        try:
            version = metadata.version(distribution) if installed else None
        except metadata.PackageNotFoundError:
            version = None
        result.append({
            "name": name, "purpose": purpose,
            "installed": installed, "version": version,
        })
    return result


# Uma única instância alimenta chat, biblioteca, memória e diagnóstico.
assistant = NixLMsNeuralCore(data_dir=DATA)
library = assistant.private_library
started = time.time()
assistant_lock = threading.RLock()


class Handler(BaseHTTPRequestHandler):
    server_version = "NixLMsLocalUI/2.0"

    def log_message(self, fmt, *args):
        print("[NixUI]", fmt % args)

    def local(self):
        try:
            import ipaddress
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                return False
            parsed = urlsplit("//" + self.headers.get("Host", ""))
            host_ok = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        except (ValueError, IndexError):
            return False
        return host_ok or os.getenv("NIXLMS_COLAB_PROXY") == "1"

    def send_json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length inválido.") from exc
        if size < 0 or size > MAX_BODY:
            raise ValueError("Solicitação excede 5 MB.")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("Corpo da solicitação incompleto.")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("O corpo JSON precisa ser um objeto.")
        return value

    def do_GET(self):
        if not self.local():
            return self.send_json({"error": "Somente acesso local."}, 403)
        path = urlparse(self.path).path
        if path == "/api/status":
            core_status = assistant.status()
            library_stats = library.stats()
            return self.send_json({
                "engine": "NixLMsNeuralCore",
                "knowledge": core_status.get("semantic_items", 0),
                "messages": core_status.get("episodic_experiences", core_status.get("episodic_items", 0)),
                "library": library_stats,
                "core": core_status,
                "runtime": {
                    "scheduler_running": assistant.scheduler.running,
                    "idle_learning": assistant.idle_learning.status(),
                },
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpu": platform.processor() or "Não identificado",
                "uptime": int(time.time() - started),
            })
        if path == "/api/frameworks":
            return self.send_json(inspect_frameworks())
        if path == "/api/library":
            return self.send_json({
                "stats": library.stats(),
                "documents": library.list_documents(100),
            })
        if path == "/api/diagnostics":
            diagnostic = assistant.run_startup_diagnostics()
            checks = {
                name: {
                    "ok": item.get("status") == "ok",
                    "status": item.get("status", "unknown"),
                    "detail": item.get("detail", ""),
                }
                for name, item in diagnostic.get("checks", {}).items()
            }
            checks.update({
                "python": {
                    "ok": sys.version_info >= (3, 10),
                    "status": "ok" if sys.version_info >= (3, 10) else "error",
                    "detail": sys.version.split()[0],
                },
                "data_directory": {
                    "ok": DATA.exists() and os.access(DATA, os.W_OK),
                    "status": "ok" if DATA.exists() and os.access(DATA, os.W_OK) else "error",
                    "detail": str(DATA),
                },
                "framework_inventory": {
                    "ok": isinstance(inspect_frameworks(), list),
                    "status": "info",
                    "detail": "Inventário de dependências opcionais; não indica que todos os frameworks estejam instalados",
                },
                "scheduler_running": {
                    "ok": assistant.scheduler.running,
                    "status": "ok" if assistant.scheduler.running else "error",
                    "detail": "Agendador ativo" if assistant.scheduler.running else "Agendador parado",
                },
            })
            try:
                dataset_audit = assistant.learning.dataset.audit_splits()
                dataset_counts = dataset_audit.get("counts", {})
                training_samples = dataset_counts.get("qa_train", 0) + dataset_counts.get("pair_train", 0)
                validation_samples = dataset_counts.get("qa_validation", 0)
                learning_ready = (
                    dataset_audit.get("valid", False)
                    and training_samples > 0
                    and validation_samples >= assistant.idle_learning.min_validation_samples
                )
                dataset_status = (
                    "ok" if learning_ready
                    else ("warning" if dataset_audit.get("valid", False) else "error")
                )
                dataset_detail = (
                    f"train={training_samples}; validation={validation_samples}; "
                    f"mínimo_validation={assistant.idle_learning.min_validation_samples}; "
                    f"integridade={'válida' if dataset_audit.get('valid') else 'inválida'}"
                )
            except Exception as exc:
                learning_ready = False
                dataset_status = "error"
                dataset_detail = type(exc).__name__ + ": " + str(exc)
            checks["idle_learning_dataset"] = {
                "ok": learning_ready,
                "status": dataset_status,
                "detail": dataset_detail,
            }
            errors = sum(item["status"] == "error" for item in checks.values())
            non_ok = any(
                item["status"] not in {"ok", "info"} for item in checks.values()
            )
            status = "failed" if errors else ("degraded" if non_ok else "ok")
            return self.send_json({
                "ok": status == "ok",
                "status": status,
                "checks": checks,
                "scheduler_running": assistant.scheduler.running,
                "idle_learning": assistant.idle_learning.status(),
            })
        routes = {
            "/": "index.html", "/index.html": "index.html",
            "/app.js": "app.js", "/style.css": "style.css",
        }
        if path not in routes:
            return self.send_json({"error": "Não encontrado."}, 404)
        target = STATIC / routes[path]
        try:
            raw = target.read_bytes()
        except OSError:
            return self.send_json({"error": "Asset ausente."}, 500)
        self.send_response(200)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(str(target))[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if not self.local():
            return self.send_json({"error": "Somente acesso local."}, 403)
        origin = self.headers.get("Origin", "")
        if origin:
            try:
                parsed_origin = urlsplit(origin)
                origin_ok = (
                    parsed_origin.scheme in {"http", "https"}
                    and parsed_origin.hostname in {"127.0.0.1", "localhost", "::1"}
                )
            except ValueError:
                origin_ok = False
            if not origin_ok and os.getenv("NIXLMS_COLAB_PROXY") != "1":
                return self.send_json({"error": "Origem não permitida."}, 403)
        try:
            data = self.read_json()
            path = urlparse(self.path).path
            if path == "/api/chat":
                msg = str(data.get("message", "")).strip()
                if not msg or len(msg) > 8000:
                    return self.send_json({"error": "Mensagem vazia ou longa demais."}, 400)
                with assistant_lock:
                    reply = assistant.respond(msg)
                    trace = dict(assistant.last_trace)
                return self.send_json({
                    "reply": reply,
                    "engine": "NixLMsNeuralCore",
                    "response_source": trace.get("response_source"),
                    "confidence": trace.get("confidence"),
                })
            if path == "/api/library/search":
                query = str(data.get("query", "")).strip()
                if not query or len(query) > 1000:
                    return self.send_json({"error": "Consulta inválida."}, 400)
                return self.send_json({"results": library.search(query, 10)})
            if path == "/api/library/import":
                name = Path(str(data.get("name", "document.txt"))).name
                extension = Path(name).suffix.lower()
                content = str(data.get("content", ""))
                if extension not in ALLOWED:
                    return self.send_json({"error": "Formato não permitido."}, 400)
                if not content.strip() or len(content.encode("utf-8")) > MAX_BODY:
                    return self.send_json({"error": "Arquivo vazio ou acima de 5 MB."}, 400)
                inbox = DATA / "ui_imports"
                inbox.mkdir(parents=True, exist_ok=True)
                safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
                target = inbox / safe_name
                if target.exists():
                    target = inbox / (str(int(time.time())) + "_" + safe_name)
                target.write_text(content, encoding="utf-8")
                return self.send_json(library.import_path(target))
            return self.send_json({"error": "Endpoint não encontrado."}, 404)
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": "Falha interna: " + type(exc).__name__}, 500)


def main():
    host, port = "127.0.0.1", int(os.getenv("NIXLMS_PORT", "8765"))
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        raise SystemExit("Não foi possível iniciar a interface: " + str(exc))
    runtime = assistant.start_runtime()
    print("NixLMs UI: http://127.0.0.1:8765 (somente este computador)")
    print("Motor: NixLMsNeuralCore")
    print("Autodiagnóstico:", runtime["diagnostics"]["status"])
    print("Aprendizagem ociosa:", runtime["idle_learning"])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando interface...")
    finally:
        assistant.scheduler.stop()
        server.server_close()


if __name__ == "__main__":
    main()
