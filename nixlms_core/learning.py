import json,random
from pathlib import Path
from .utils import save_json,load_json

class DatasetStore:
    def __init__(self,path): self.path=Path(path)
    def load(self):
        rows=load_json(self.path,[])
        return rows if isinstance(rows,list) else []
    def add(self,question,answer,split="train"):
        rows=self.load(); rows.append({"question":question.strip(),"answer":answer.strip(),"split":split})
        save_json(self.path,rows); return len(rows)
    def import_jsonl(self,source):
        added=0
        with Path(source).open("r",encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                row=json.loads(line)
                if row.get("question") and row.get("answer"):
                    self.add(row["question"],row["answer"],row.get("split","train")); added+=1
        return added

class LearningEngine:
    def __init__(self,agent,dataset_path): self.agent=agent; self.dataset=DatasetStore(dataset_path); self.last_training={}
    def train(self,epochs=1,seed=42):
        rows=[r for r in self.dataset.load() if r.get("split","train")=="train"]
        if not rows: return {"trained":0,"epochs":0,"message":"Dataset vazio. Adicione exemplos antes de treinar."}
        rng=random.Random(seed); trained=0
        for _ in range(max(1,int(epochs))):
            batch=list(rows); rng.shuffle(batch)
            for row in batch:
                self.agent.learn(row["question"],row["answer"],reward=.5); trained+=1
        self.last_training={"trained":trained,"epochs":max(1,int(epochs)),"dataset_size":len(rows)}
        return dict(self.last_training)
    def evaluate(self):
        rows=[r for r in self.dataset.load() if r.get("split")=="test"]
        if not rows: rows=[r for r in self.dataset.load() if r.get("split","train")=="train"]
        if not rows: return {"samples":0,"accuracy":0.0,"mrr":0.0,"message":"Sem exemplos para avaliação."}
        hits=0; reciprocal=0.0
        for row in rows:
            ranked=self.agent.memory.recall(row["question"],self.agent.encoder,self.agent.network,limit=5)
            rank=next((i+1 for i,(_,item) in enumerate(ranked) if item.get("answer")==row["answer"]),None)
            if rank: hits+=1; reciprocal+=1.0/rank
        n=len(rows)
        return {"samples":n,"accuracy":hits/n,"mrr":reciprocal/n,"metric":"top-5 retrieval hit rate and MRR"}
