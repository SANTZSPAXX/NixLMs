"""LLM opcional via Ollama local; conexões remotas são recusadas."""
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class LanguageEngine:
    def __init__(self, model=None, host=None, timeout=90):
        self.model = model or os.getenv("NIXLMS_LLM_MODEL", "qwen2.5:0.5b")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = max(1, int(timeout))
        self.enabled = os.getenv("NIXLMS_LLM_ENABLED", "1").lower() not in {"0", "false", "no"}
        parsed = urlparse(self.host)
        self.local_host = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}

    def status(self):
        return {"enabled": self.enabled, "provider": "ollama_local", "model": self.model,
                "host": self.host, "local_endpoint": self.local_host}

    def available(self):
        if not self.enabled or not self.local_host:
            return False
        try:
            with urlopen(self.host + "/api/tags", timeout=2) as response:
                data = json.loads(response.read().decode("utf-8"))
            return any(m.get("name") == self.model for m in data.get("models", []))
        except (URLError, HTTPError, TimeoutError, ValueError, OSError):
            return False

    def generate(self, message, memories=None, concepts=None, history=None,
                 world_facts=None, goals=None):
        if not self.enabled or not self.local_host:
            return None
        context = {
            "memorias_relevantes": memories or [],
            "conceitos_associados": concepts or [],
            "memoria_de_trabalho": history or [],
            "fatos_do_modelo_de_mundo_com_proveniencia": world_facts or [],
            "objetivos_ativos_e_proximas_etapas": goals or [],
        }
        prompt = (
            "Responda em português brasileiro, com clareza. Use o contexto como pistas, "
            "não como fatos garantidos. Fatos do modelo de mundo incluem fonte e confiança; "
            "não invente proveniência e sinalize conflitos. Objetivos são registros, não "
            "permissão para executar ações. Admita quando não souber. Não afirme consciência, "
            "sentimentos reais ou acesso a sensores.\n\nCONTEXTO:\n"
            + json.dumps(context, ensure_ascii=False)
            + "\n\nMENSAGEM:\n" + str(message)
        )
        payload = json.dumps({"model": self.model, "stream": False, "messages": [
            {"role": "system", "content": "Você é o mecanismo linguístico local da NixLMs, uma IA experimental."},
            {"role": "user", "content": prompt}],
            "options": {"temperature": .35, "num_ctx": 2048, "num_predict": 256}},
            ensure_ascii=False).encode("utf-8")
        req = Request(self.host + "/api/chat", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            answer = result.get("message", {}).get("content", "").strip()
            return answer or None
        except (URLError, HTTPError, TimeoutError, ValueError, OSError):
            return None
