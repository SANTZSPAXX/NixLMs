"""Cliente Python mínimo para conectar ferramentas à API NixLMs."""
import json, urllib.error, urllib.request
class NixLMsClient:
    def __init__(self,api_key,base_url="http://127.0.0.1:8766",timeout=60):
        if not api_key: raise ValueError("api_key é obrigatória.")
        self.base_url=base_url.rstrip("/"); self.api_key=api_key; self.timeout=timeout
    def chat(self,message,model="nixlms"):
        payload=json.dumps({"model":model,"messages":[{"role":"user","content":message}]}).encode("utf-8")
        req=urllib.request.Request(self.base_url+"/v1/chat/completions",data=payload,method="POST",
            headers={"Authorization":"Bearer "+self.api_key,"Content-Type":"application/json","Accept":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as response: result=json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8",errors="replace")
            raise RuntimeError(f"NixLMs API HTTP {exc.code}: {detail}") from exc
        return result["choices"][0]["message"]["content"]
