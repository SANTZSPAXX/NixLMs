"""Motor EEG-inspired: oscilações sintéticas, não aquisição biomédica real."""
import math, random

BANDS = {"delta": (0.5,4.0), "theta": (4.0,8.0), "alpha": (8.0,13.0), "beta": (13.0,30.0), "gamma": (30.0,45.0)}

class EEGInspiredEngine:
    def __init__(self, seed=42, sample_rate=128):
        self.rng = random.Random(seed); self.sample_rate = sample_rate

    def synthesize(self, seconds=2.0, profile=None):
        profile = profile or {"delta":.15,"theta":.25,"alpha":.35,"beta":.2,"gamma":.05}
        n = max(1, int(seconds*self.sample_rate)); signal=[]
        freqs = {k:(lo+hi)/2 for k,(lo,hi) in BANDS.items()}
        phases = {k:self.rng.random()*2*math.pi for k in BANDS}
        for i in range(n):
            t=i/self.sample_rate
            v=sum(float(profile.get(k,0))*math.sin(2*math.pi*freqs[k]*t+phases[k]) for k in BANDS)
            signal.append(v + self.rng.gauss(0,.015))
        return signal

    def band_energy(self, signal):
        result={}; n=len(signal) or 1
        for name,(lo,hi) in BANDS.items():
            f=(lo+hi)/2; re=im=0.0
            for i,x in enumerate(signal):
                a=2*math.pi*f*i/self.sample_rate
                re += x*math.cos(a); im -= x*math.sin(a)
            result[name]=2*(re*re+im*im)/(n*n)
        total=sum(result.values()) or 1.0
        return {k:v/total for k,v in result.items()}

    def cognitive_state(self, energies):
        focus=min(1.0, energies.get("beta",0)*1.7 + energies.get("gamma",0)*1.2)
        calm=min(1.0, energies.get("alpha",0)*1.8)
        association=min(1.0, energies.get("theta",0)*1.8)
        return {"focus":focus,"calm":calm,"association":association}
