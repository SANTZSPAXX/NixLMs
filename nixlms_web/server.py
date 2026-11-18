"""Servidor HTTP local da interface NixLMs: loopback, sem shell remoto."""
from __future__ import annotations
import json, mimetypes, os, platform, re, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
STATIC=Path(__file__).resolve().parent/"static"
DATA=ROOT/"data"
MAX_BODY=5*1024*1024
ALLOWED={".txt",".md",".rst",".py",".json",".yaml",".yml",".toml"}
sys.path.insert(0,str(ROOT))
from nixlms import NixLMs
from nixlms_core.private_library import PrivateKnowledgeLibrary
from nixlms_core.framework_registry import inspect_frameworks
assistant=NixLMs()
library=PrivateKnowledgeLibrary(DATA/"private_library.sqlite3")
started=time.time()

class Handler(BaseHTTPRequestHandler):
    server_version="NixLMsLocalUI/1.0"
    def log_message(self,fmt,*args): print("[NixUI]",fmt%args)
    def local(self):
        host=self.headers.get("Host","")
        return host.startswith(("127.0.0.1:","localhost:","[::1]:"))
    def send_json(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(raw)
    def read_json(self):
        size=int(self.headers.get("Content-Length","0"))
        if size<0 or size>MAX_BODY: raise ValueError("Solicitação excede 5 MB.")
        return json.loads(self.rfile.read(size).decode("utf-8"))
    def do_GET(self):
        if not self.local(): return self.send_json({"error":"Somente acesso local."},403)
        path=urlparse(self.path).path
        if path=="/api/status":
            s=library.stats()
            return self.send_json({"knowledge":len(assistant.knowledge),"messages":len(assistant.history),
                "library":s,"python":platform.python_version(),"platform":platform.platform(),
                "cpu":platform.processor() or "Não identificado","uptime":int(time.time()-started)})
        if path=="/api/frameworks": return self.send_json(inspect_frameworks())
        if path=="/api/library":
            return self.send_json({"stats":library.stats(),"documents":library.list_documents(100)})
        if path=="/api/diagnostics":
            checks={"python":{"ok":sys.version_info>=(3,10),"detail":sys.version.split()[0]},
                "data":{"ok":DATA.exists() and os.access(DATA,os.W_OK),"detail":str(DATA)},
                "sqlite":{"ok":library.path.exists(),"detail":"Biblioteca privada local"},
                "frameworks":{"ok":isinstance(inspect_frameworks(),list),"detail":"Inventário sem importações pesadas"}}
            return self.send_json({"checks":checks,"ok":all(v["ok"] for v in checks.values())})
        routes={"/": "index.html","/index.html":"index.html","/app.js":"app.js","/style.css":"style.css"}
        if path not in routes: return self.send_json({"error":"Não encontrado."},404)
        target=STATIC/routes[path]
        try: raw=target.read_bytes()
        except OSError: return self.send_json({"error":"Asset ausente."},500)
        self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length",str(len(raw))); self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        if not self.local(): return self.send_json({"error":"Somente acesso local."},403)
        origin=self.headers.get("Origin","")
        if origin and not origin.startswith(("http://127.0.0.1:","http://localhost:")):
            return self.send_json({"error":"Origem não permitida."},403)
        try:
            data=self.read_json(); path=urlparse(self.path).path
            if path=="/api/chat":
                msg=str(data.get("message","")).strip()
                if not msg or len(msg)>8000: return self.send_json({"error":"Mensagem vazia ou longa demais."},400)
                return self.send_json({"reply":assistant.respond(msg)})
            if path=="/api/library/search":
                q=str(data.get("query","")).strip()
                if not q or len(q)>1000: return self.send_json({"error":"Consulta inválida."},400)
                return self.send_json({"results":library.search(q,10)})
            if path=="/api/library/import":
                name=Path(str(data.get("name","document.txt"))).name
                ext=Path(name).suffix.lower(); content=str(data.get("content",""))
                if ext not in ALLOWED: return self.send_json({"error":"Formato não permitido."},400)
                if not content.strip() or len(content.encode())>MAX_BODY: return self.send_json({"error":"Arquivo vazio ou acima de 5 MB."},400)
                inbox=DATA/"ui_imports"; inbox.mkdir(parents=True,exist_ok=True)
                safe=re.sub(r"[^A-Za-z0-9._-]","_",name)[:120]
                target=inbox/safe
                if target.exists(): target=inbox/(str(int(time.time()))+"_"+safe)
                target.write_text(content,encoding="utf-8")
                return self.send_json(library.import_path(target))
            return self.send_json({"error":"Endpoint não encontrado."},404)
        except (ValueError,UnicodeError,json.JSONDecodeError) as exc: return self.send_json({"error":str(exc)},400)
        except Exception as exc: return self.send_json({"error":"Falha interna: "+type(exc).__name__},500)

def main():
    host,port="127.0.0.1",8765
    try: server=ThreadingHTTPServer((host,port),Handler)
    except OSError as exc: raise SystemExit("Não foi possível iniciar a interface: "+str(exc))
    print("NixLMs UI: http://127.0.0.1:8765 (somente este computador)")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nEncerrando interface...")
    finally: server.server_close()
if __name__=="__main__": main()
