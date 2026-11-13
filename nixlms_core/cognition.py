class CognitiveEngine:
    def __init__(self, confidence_threshold=.12): self.confidence_threshold=confidence_threshold
    def attend(self, text, eeg_state):
        salience=min(1.0,len(set(text.split()))/18.0)
        return {"salience":salience,"focus":eeg_state.get("focus",0.0),"priority":.6*salience+.4*eeg_state.get("focus",0.0)}
    def decide(self, ranked, attention):
        if not ranked: return None,0.0
        score,item=ranked[0]
        confidence=min(1.0,score*(.8+.2*attention["priority"]))
        return (item if confidence>=self.confidence_threshold else None),confidence
