"""Pequena rede recorrente LIF com plasticidade Hebbiana local."""
import math, random

class LIFNetwork:
    def __init__(self, input_size=64, hidden_size=48, output_size=32, steps=24, threshold=1.0, leak=.88, seed=42, learning_rate=.025):
        self.input_size=input_size; self.hidden_size=hidden_size; self.output_size=output_size
        self.steps=steps; self.threshold=threshold; self.leak=leak; self.learning_rate=learning_rate
        rng=random.Random(seed)
        self.w_in=[[rng.uniform(-.18,.18) for _ in range(input_size)] for _ in range(hidden_size)]
        self.w_out=[[rng.uniform(-.18,.18) for _ in range(hidden_size)] for _ in range(output_size)]
        self.last_hidden=[0.0]*hidden_size

    def forward(self, vector, modulation=1.0):
        if len(vector)!=self.input_size: raise ValueError(f"Vetor deve ter {self.input_size} dimensões")
        membrane=[0.0]*self.hidden_size; rates=[0.0]*self.hidden_size
        for _ in range(self.steps):
            for j in range(self.hidden_size):
                current=sum(w*x for w,x in zip(self.w_in[j],vector))*modulation
                membrane[j]=self.leak*membrane[j]+current/max(1,self.steps)**.5
                if membrane[j]>=self.threshold:
                    rates[j]+=1.0; membrane[j]=0.0
        hidden=[r/self.steps for r in rates]
        hidden=[h + .08*math.tanh(sum(w*x for w,x in zip(self.w_in[j],vector))) for j,h in enumerate(hidden)]
        output=[math.tanh(sum(w*h for w,h in zip(row,hidden))) for row in self.w_out]
        self.last_hidden=hidden
        return output, hidden

    def hebbian_update(self, input_vector, hidden, reward=1.0):
        rate=self.learning_rate*max(-1.0,min(1.0,reward))
        for j in range(self.hidden_size):
            activity=max(-1.0,min(1.0,hidden[j]))
            for i in range(self.input_size):
                self.w_in[j][i]=max(-1.5,min(1.5,self.w_in[j][i]+rate*activity*input_vector[i]*.08))

    def state_dict(self):
        return {"w_in":self.w_in,"w_out":self.w_out}
    def load_state_dict(self, state):
        if len(state.get("w_in",[]))==self.hidden_size and len(state.get("w_out",[]))==self.output_size:
            self.w_in=state["w_in"]; self.w_out=state["w_out"]
