from collections import deque
from datetime import datetime,timezone
from .utils import tokenize

class WorkingMemory:
    def __init__(self,capacity=12): self.capacity=max(2,int(capacity)); self.items=deque(maxlen=self.capacity)
    def add(self,role,content,priority=.5):
        self.items.append({"role":role,"content":str(content),"priority":float(priority),"time":datetime.now(timezone.utc).isoformat()})
    def context(self,limit=8):
        return list(reversed(sorted(self.items,key=lambda x:x["priority"],reverse=True)[:limit]))
    def clear(self): self.items.clear()
    def __len__(self): return len(self.items)

class AttentionSystem:
    def __init__(self,working_capacity=12):
        self.working=WorkingMemory(working_capacity); self.last_focus=[]
    def allocate(self,query,candidates,eeg_state=None,mental_map=None,limit=5):
        eeg_state=eeg_state or {}; q=set(tokenize(query))
        associations=set(mental_map.context(query) if mental_map else [])
        ranked=[]
        for item in candidates:
            terms=set(tokenize(item.get("question",item.get("content",""))))
            overlap=len(q & terms)/max(1,len(q))
            assoc=len(terms & associations)/max(1,len(terms)) if terms else 0.0
            recency=float(item.get("priority",0.0))
            score=.58*overlap+.22*assoc+.12*eeg_state.get("focus",0.0)+.08*recency
            ranked.append((score,item))
        ranked.sort(key=lambda x:x[0],reverse=True); self.last_focus=[{"score":s,"item":i} for s,i in ranked[:limit]]
        return ranked[:limit]
    def attend_message(self,role,text,priority=.5): self.working.add(role,text,priority)
