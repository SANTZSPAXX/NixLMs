class FeedbackLearner:
    def __init__(self, network): self.network=network; self.feedback_count=0
    def reinforce(self, vector, hidden, reward=1.0):
        self.network.hebbian_update(vector,hidden,reward); self.feedback_count+=1
    def stats(self): return {"feedback_updates":self.feedback_count}
