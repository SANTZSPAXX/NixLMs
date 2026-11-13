from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
from .utils import load_json, save_json, tokenize

class MentalMap:
    """Grafo associativo local baseado em coocorrência lexical."""
    def __init__(self,path:Path,max_edges=12000):
        self.path=Path(path); self.max_edges=max_edges
        data=load_json(self.path,{"nodes":{},"edges":{}})
        self.nodes=data.get("nodes",{}) if isinstance(data,dict) else {}
        self.edges=data.get("edges",{}) if isinstance(data,dict) else {}
    def _key(self,a,b): return "|".join(sorted((a,b)))
    def observe(self,text,weight=1.0):
        terms=list(dict.fromkeys(tokenize(text)))[:24]; now=datetime.now(timezone.utc).isoformat()
        for term in terms:
            node=self.nodes.setdefault(term,{"count":0,"updated_at":now})
            node["count"]=int(node.get("count",0))+1; node["updated_at"]=now
        for i,a in enumerate(terms):
            for b in terms[i+1:]:
                if a==b: continue
                key=self._key(a,b); edge=self.edges.setdefault(key,{"source":a,"target":b,"weight":0.0})
                edge["weight"]=min(100.0,float(edge.get("weight",0))+float(weight))
        if len(self.edges)>self.max_edges:
            self.edges=dict(sorted(self.edges.items(),key=lambda kv:kv[1].get("weight",0),reverse=True)[:self.max_edges])
        self.save(); return terms
    def associate(self,query,limit=8):
        terms=set(tokenize(query)); scores=Counter()
        for edge in self.edges.values():
            a,b=edge["source"],edge["target"]
            if a in terms and b not in terms: scores[b]+=float(edge.get("weight",0))
            if b in terms and a not in terms: scores[a]+=float(edge.get("weight",0))
        return [{"concept":k,"strength":v} for k,v in scores.most_common(limit)]
    def context(self,query,limit=8):
        direct=tokenize(query)
        return list(dict.fromkeys(direct+[x["concept"] for x in self.associate(query,limit)]))[:limit*2]
    def save(self): save_json(self.path,{"nodes":self.nodes,"edges":self.edges})
    def stats(self): return {"concept_nodes":len(self.nodes),"associations":len(self.edges)}
