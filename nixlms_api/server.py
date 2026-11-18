"""Servidor HTTP OpenAI-compatible, autenticado e local por padrão."""
from __future__ import annotations
import json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .keys import APIKeyStore
ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 1024 * 1024

class RateLimiter:
    def __init__(self, limit=60, window=60):
        self.limit, self.window, self.events, self.lock = int(limit), int(window), {}, threading.Lock()
    def allow(self, identity):
        now = time.monotonic()
        with self.lock:
            bucket = [stamp for stamp in self.events.get(identity, []) if now-stamp < self.window]
            if len(bucket) >= self.limit:
                self.events[identity] = bucket; return False
            bucket.append(now); self.events[identity] = bucket; return True

def create_server(host=None, port=None, assistant=None, key_store=None):
    host = host or os.getenv("NIXLMS_API_HOST", "127.0.0.1")
    port = int(os.getenv("NIXLMS_API_PORT", "8766")) if port is None else int(port)
    if host not in {"127.0.0.1", "localhost", "::1"} and os.getenv("NIXLMS_API_ALLOW_REMOTE") != "1":
        raise RuntimeError("Acesso remoto bloqueado. Defina NIXLMS_API_ALLOW_REMOTE=1 somente atrás de HTTPS/firewall.")
    data_dir = Path(os.getenv("NIXLMS_DATA_DIR", str(ROOT / "data"))).expanduser()
    store = key_store or APIKeyStore(data_dir / "api_keys.sqlite3")
    limiter = RateLimiter(int(os.getenv("NIXLMS_API_RATE_LIMIT", "60")))
    assistant_lock = threading.RLock()
    class Handler(BaseHTTPRequestHandler):
        server_version = "NixLMsAPI/0.1"
        def log_message(self, fmt, *args):
            if os.getenv("NIXLMS_API_ACCESS_LOG") == "1": super().log_message(fmt, *args)
        def send_json(self, payload, status=200):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(raw)
        def authenticate(self, scope):
            scheme, _, token = self.headers.get("Authorization", "").partition(" ")
            identity = store.authenticate(token) if scheme.lower() == "bearer" else None
            if identity is None:
                self.send_json({"error":{"message":"API key ausente ou inválida.","type":"authentication_error"}},401); return None
            if scope not in identity["scopes"]:
                self.send_json({"error":{"message":"Escopo insuficiente.","type":"permission_error"}},403); return None
            if not limiter.allow(identity["prefix"]):
                self.send_json({"error":{"message":"Limite de requisições excedido.","type":"rate_limit_error"}},429); return None
            return identity
        def read_body(self):
            try: size = int(self.headers.get("Content-Length", "0"))
            except ValueError: raise ValueError("Content-Length inválido.")
            if size < 1 or size > MAX_BODY: raise ValueError("Corpo ausente ou acima de 1 MB.")
            data = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(data, dict): raise ValueError("O corpo deve ser um objeto JSON.")
            return data
        def do_GET(self):
            if self.path == "/health": return self.send_json({"ok":True,"service":"NixLMs API","version":"0.1.0"})
            if self.path == "/v1/models":
                if not self.authenticate("models:read"): return
                return self.send_json({"object":"list","data":[{"id":"nixlms","object":"model","owned_by":"SANTZSPAXX"}]})
            self.send_json({"error":{"message":"Endpoint não encontrado."}},404)
        def do_POST(self):
            if self.path not in {"/v1/chat/completions","/v1/chat"}:
                return self.send_json({"error":{"message":"Endpoint não encontrado."}},404)
            if not self.authenticate("chat:write"): return
            try:
                data = self.read_body()
                if self.path == "/v1/chat": prompt = str(data.get("message","")).strip()
                else:
                    messages = data.get("messages")
                    if not isinstance(messages,list): raise ValueError("messages deve ser uma lista.")
                    prompt = "\n".join(str(item.get("content","")) for item in messages
                        if isinstance(item,dict) and item.get("role") in {"system","user"})
                if not prompt or len(prompt)>16000: raise ValueError("Mensagem vazia ou acima de 16000 caracteres.")
                nonlocal assistant
                with assistant_lock:
                    if assistant is None:
                        from nixlms_core import NixLMsNeuralCore
                        assistant = NixLMsNeuralCore(data_dir=data_dir)
                        if hasattr(assistant, "start_runtime"):
                            assistant.start_runtime()
                    answer = assistant.respond(prompt, use_language=True, record=True)
                if self.path == "/v1/chat": return self.send_json({"reply":answer,"model":"nixlms"})
                return self.send_json({"id":"chatcmpl-"+uuid.uuid4().hex,"object":"chat.completion",
                    "created":int(time.time()),"model":"nixlms",
                    "choices":[{"index":0,"message":{"role":"assistant","content":answer},"finish_reason":"stop"}],
                    "usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0},
                    "nixlms":{"engine":"NixLMsNeuralCore","usage_estimate":False}})
            except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
                return self.send_json({"error":{"message":str(exc),"type":"invalid_request_error"}},400)
            except Exception as exc:
                return self.send_json({"error":{"message":"Falha interna: "+type(exc).__name__,"type":"server_error"}},500)
    class NixAPIServer(ThreadingHTTPServer):
        def server_close(self):
            super().server_close()
            current = assistant
            scheduler = getattr(current, "scheduler", None) if current is not None else None
            if scheduler is not None:
                scheduler.stop()
    return NixAPIServer((host,port),Handler)

def main():
    server=create_server()
    print(f"NixLMs API em http://{server.server_address[0]}:{server.server_address[1]}")
    print("Health: /health | Chat: /v1/chat/completions | Ctrl+C para encerrar")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == "__main__": main()
