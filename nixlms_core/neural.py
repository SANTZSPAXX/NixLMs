"""Rede recorrente LIF com sinapses recorrentes e plasticidade STDP modulada por recompensa."""
import math, random

class LIFNetwork:
    def __init__(self, input_size=64, hidden_size=48, output_size=32, steps=24, threshold=1.0, leak=.88, seed=42, learning_rate=.025, recurrent_scale=.12):
        self.input_size=input_size; self.hidden_size=hidden_size; self.output_size=output_size
        self.steps=steps; self.threshold=threshold; self.leak=leak; self.learning_rate=learning_rate
        rng=random.Random(seed)
        self.w_in=[[rng.uniform(-.12,.12) for _ in range(input_size)] for _ in range(hidden_size)]
        self.w_rec=[[0.0 if i==j else rng.uniform(-recurrent_scale,recurrent_scale) for i in range(hidden_size)] for j in range(hidden_size)]
        self.w_out=[[rng.uniform(-.12,.12) for _ in range(hidden_size)] for _ in range(output_size)]
        self.last_hidden=[0.0]*hidden_size; self.last_spikes=[0.0]*hidden_size
        self.eligibility_in=[[0.0]*input_size for _ in range(hidden_size)]
        self.eligibility_rec=[[0.0]*hidden_size for _ in range(hidden_size)]

    def forward(self, vector, modulation=1.0, state=None):
        if len(vector)!=self.input_size: raise ValueError(f"Vetor deve ter {self.input_size} dimensões")
        membrane=list(state or [0.0]*self.hidden_size)
        if len(membrane)!=self.hidden_size: membrane=[0.0]*self.hidden_size
        prev=[0.0]*self.hidden_size; counts=[0.0]*self.hidden_size; history=[]
        scale=max(1,self.steps)**-.5
        for _ in range(self.steps):
            spikes=[0.0]*self.hidden_size
            for j in range(self.hidden_size):
                feed=sum(w*x for w,x in zip(self.w_in[j],vector))
                recurrent=sum(w*x for w,x in zip(self.w_rec[j],prev))
                membrane[j]=self.leak*membrane[j]+(feed+recurrent)*scale*modulation
                if membrane[j]>=self.threshold:
                    spikes[j]=1.0; counts[j]+=1.0; membrane[j]=0.0
            history.append(spikes); prev=spikes
        rates=[c/self.steps for c in counts]
        analog=[math.tanh(sum(w*x for w,x in zip(self.w_in[j],vector))+sum(w*x for w,x in zip(self.w_rec[j],prev))) for j in range(self.hidden_size)]
        hidden=[.75*r+.25*a for r,a in zip(rates,analog)]
        output=[math.tanh(sum(w*h for w,h in zip(row,hidden))) for row in self.w_out]
        self.last_hidden=hidden; self.last_spikes=prev
        self._accumulate_eligibility(vector,history)
        return output,hidden

    def _accumulate_eligibility(self, vector, history):
        pre=[0.0]*self.hidden_size; post=[0.0]*self.hidden_size
        for spikes in history:
            for i,s in enumerate(spikes): pre[i]=.90*pre[i]+s
            for j,s in enumerate(spikes): post[j]=.90*post[j]+s
            for j in range(self.hidden_size):
                for i,x in enumerate(vector):
                    self.eligibility_in[j][i]=.98*self.eligibility_in[j][i]+post[j]*x*.0005
                for i in range(self.hidden_size):
                    if i!=j: self.eligibility_rec[j][i]=.98*self.eligibility_rec[j][i]+post[j]*pre[i]*.0002

    def hebbian_update(self, input_vector, hidden, reward=1.0):
        rate=self.learning_rate*max(-1.0,min(1.0,float(reward)))
        for j in range(self.hidden_size):
            for i in range(self.input_size):
                self.w_in[j][i]=max(-1.5,min(1.5,self.w_in[j][i]+rate*self.eligibility_in[j][i]))
            for i in range(self.hidden_size):
                if i!=j: self.w_rec[j][i]=max(-.8,min(.8,self.w_rec[j][i]+rate*self.eligibility_rec[j][i]))
        decay=.5 if reward else .8
        self.eligibility_in=[[v*decay for v in row] for row in self.eligibility_in]
        self.eligibility_rec=[[v*decay for v in row] for row in self.eligibility_rec]

    def state_dict(self): return {"w_in":self.w_in,"w_rec":self.w_rec,"w_out":self.w_out}
    def load_state_dict(self,state):
        try:
            wi,wr,wo=state["w_in"],state["w_rec"],state["w_out"]
            if len(wi)==self.hidden_size and all(len(r)==self.input_size for r in wi) and len(wr)==self.hidden_size and all(len(r)==self.hidden_size for r in wr) and len(wo)==self.output_size and all(len(r)==self.hidden_size for r in wo):
                self.w_in=wi; self.w_rec=wr; self.w_out=wo; return True
        except (KeyError,TypeError): pass
        return False
