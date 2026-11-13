from datetime import datetime, timezone
from pathlib import Path
from .utils import load_json, save_json, cosine, tokenize

class MemorySystem:
    def __init__(self, data_dir: Path, max_items=2000):
        self.data_dir=Path(data_dir); self.max_items=max_items
        self.knowledge_path=self.data_dir/"knowledge.json"; self.episodes_path=self.data_dir/"episodes.json"
        self.knowledge=load_json(self.knowledge_path,[]); self.episodes=load_json(self.episodes_path,[])
        if not isinstance(self.knowledge,list): self.knowledge=[]
        if not isinstance(self.episodes,list): self.episodes=[]
        self.working=[]

    def remember(self, question, answer, tags=None):
        item={"question":question.strip(),"answer":answer.strip(),"tags":tags or [],"created_at":datetime.now(timezone.utc).isoformat()}
        self.knowledge.append(item); self.knowledge=self.knowledge[-self.max_items:]
        save_json(self.knowledge_path,self.knowledge); return item

    def recall(self, query, encoder, network=None, limit=5):
        qtokens=set(tokenize(query)); qvec=encoder.encode(query); ranked=[]
        for item in self.knowledge:
            text=item.get("question",""); tokens=set(tokenize(text))
            lexical=len(qtokens & tokens)/max(1,len(qtokens | tokens))
            vector=encoder.encode(text); neural=cosine(qvec,vector)
            if network:
                out,_=network.forward(qvec); target=network.forward(vector)[0]
                neural=max(neural,cosine(out,target))
            ranked.append((.65*lexical+.35*max(0.0,neural),item))
        return sorted(ranked,key=lambda x:x[0],reverse=True)[:limit]

    def add_episode(self, role, content):
        self.episodes.append({"role":role,"content":content,"timestamp":datetime.now(timezone.utc).isoformat()})
        self.episodes=self.episodes[-self.max_items:]
        save_json(self.episodes_path,self.episodes)

    def stats(self):
        return {"semantic_items":len(self.knowledge),"episodic_items":len(self.episodes),"working_items":len(self.working)}
