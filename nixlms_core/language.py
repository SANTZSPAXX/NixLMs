"""LLM opcional e estritamente local via Ollama HTTP em localhost."""
import json,os
from urllib.request import Request,urlopen
from urllib.error import URLError,HTTPError

class LanguageEngine:
    def __init__(self,model=None,host=None,timeout=90):
        self.model=model or os.getenv("NIXLMS_LLM_MODEL","qwen2.5:0.5b")
        self.host=(host or os.getenv("OLLAMA_HOST","http://127.0.0.1:11434")).rstrip("/")
        self.timeout=timeout
        self.enabled=os.getenv("NIXLMS_LLM_ENABLED","1").lower() not in {"0","false","no"}
    def status(self): return {"enabled":self.enabled,"provider":"ollama_local","model":self.model,"host":self.host}
    def available(self):
        if not self.enabled: return False
        try:
            with urlopen(self.host+"/api/tags",timeout=2) as response: data=json.loads(response.read().decode("utf-8"))
            return any(m.get("name","").split(":")[0]==self.model.split(":")[0] for m in data.get("models",[]))
        except (URLError,HTTPError,TimeoutError,ValueError,OSError): return False
    def generate(self,message,memories=None,concepts=None,history=None):
        if not self.enabled: return None
        context={"memorias_relevantes":memories or [],"conceitos_associados":concepts or [],"memoria_de_trabalho":history or []}
        prompt=("Responda em português brasileiro, com clareza. Use o contexto como pistas, não como fatos garantidos. "
                "Admita quando não souber. Não afirme consciência, sentimentos reais ou acesso a sensores.\n\n"
                +"CONTEXTO:\n"+json.dumps(context,ensure_ascii=False)+"\n\nMENSAGEM:\n"+message)
        payload=json.dumps({"model":self.model,"stream":False,"messages":[
            {"role":"system","content":"Você é o mecanismo linguístico local da NixLMs, uma IA experimental."},
            {"role":"user","content":prompt}],"options":{"temperature":.35,"num_ctx":2048,"num_predict":256}},ensure_ascii=False).encode("utf-8")
        req=Request(self.host+"/api/chat",data=payload,headers={"Content-Type":"application/json"},method="POST")
        try:
            with urlopen(req,timeout=self.timeout) as response: result=json.loads(response.read().decode("utf-8"))
            answer=result.get("message",{}).get("content","").strip()
            return answer or None
        except (URLError,HTTPError,TimeoutError,ValueError,OSError): return None
