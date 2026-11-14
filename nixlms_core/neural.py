"""Rede recorrente LIF experimental com traços de elegibilidade e STDP aproximada."""
import math
import random


class LIFNetwork:
    def __init__(self, input_size=64, hidden_size=48, output_size=32, steps=24,
                 threshold=.08, leak=.88, seed=42, learning_rate=.025,
                 recurrent_scale=.12):
        self.input_size = int(input_size)
        self.hidden_size = int(hidden_size)
        self.output_size = int(output_size)
        self.steps = max(1, int(steps))
        self.threshold = float(threshold)
        self.leak = float(leak)
        self.learning_rate = float(learning_rate)
        rng = random.Random(seed)
        self.w_in = [[rng.uniform(-.12, .12) for _ in range(self.input_size)]
                     for _ in range(self.hidden_size)]
        self.w_rec = [[0.0 if i == j else rng.uniform(-recurrent_scale, recurrent_scale)
                       for j in range(self.hidden_size)]
                      for i in range(self.hidden_size)]
        self.w_out = [[rng.uniform(-.12, .12) for _ in range(self.hidden_size)]
                      for _ in range(self.output_size)]
        self.last_hidden = [0.0] * self.hidden_size
        self.last_spikes = [0.0] * self.hidden_size
        self.last_spike_counts = [0.0] * self.hidden_size
        self.last_spike_history = []
        self.eligibility_in = [[0.0] * self.input_size for _ in range(self.hidden_size)]
        self.eligibility_rec = [[0.0] * self.hidden_size for _ in range(self.hidden_size)]
        self.output_updates = 0

    def train_output(self, hidden, target, learning_rate=0.025):
        """Treina a leitura supervisionada LIF -> representação semântica da resposta."""
        if len(hidden) != self.hidden_size or len(target) != self.output_size:
            raise ValueError("Dimensões incompatíveis para treinar a leitura de saída.")
        values = [float(value) for value in list(hidden) + list(target)]
        rate = float(learning_rate)
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("learning_rate deve ser finito e positivo.")
        if any(not math.isfinite(value) for value in values):
            raise ValueError("A leitura LIF recebeu valores não finitos.")
        if any(abs(value) > 1.0 for value in target):
            raise ValueError("O alvo da leitura LIF deve estar no intervalo [-1, 1].")
        prediction = [
            math.tanh(sum(w * h for w, h in zip(row, hidden)))
            for row in self.w_out
        ]
        loss = sum((pred - float(expected)) ** 2
                   for pred, expected in zip(prediction, target)) / self.output_size
        for index, row in enumerate(self.w_out):
            pred = prediction[index]
            gradient = (2.0 * (pred - float(target[index])) *
                        (1.0 - pred * pred) / self.output_size)
            for j, activation in enumerate(hidden):
                row[j] = max(-1.5, min(1.5, row[j] - rate * gradient * float(activation)))
        self.output_updates += 1
        return loss

    def forward(self, vector, modulation=1.0, state=None, track_plasticity=False):
        if len(vector) != self.input_size:
            raise ValueError(f"Vetor deve ter {self.input_size} dimensões")
        membrane = list(state if state is not None else [0.0] * self.hidden_size)
        if len(membrane) != self.hidden_size:
            raise ValueError("Estado recorrente possui dimensão inválida")
        prev = [0.0] * self.hidden_size
        counts = [0.0] * self.hidden_size
        history = []
        scale = max(1, self.steps) ** -.5
        for _ in range(self.steps):
            spikes = [0.0] * self.hidden_size
            for j in range(self.hidden_size):
                feed = sum(w * x for w, x in zip(self.w_in[j], vector))
                recurrent = sum(w * x for w, x in zip(self.w_rec[j], prev))
                membrane[j] = self.leak * membrane[j] + (feed + recurrent) * scale * modulation
                if membrane[j] >= self.threshold:
                    spikes[j] = 1.0
                    counts[j] += 1.0
                    membrane[j] = 0.0
            history.append(spikes)
            prev = spikes

        rates = [count / self.steps for count in counts]
        analog = [
            math.tanh(sum(w * x for w, x in zip(self.w_in[j], vector)) +
                      sum(w * x for w, x in zip(self.w_rec[j], prev)))
            for j in range(self.hidden_size)
        ]
        hidden = [.75 * rate + .25 * value for rate, value in zip(rates, analog)]
        output = [
            math.tanh(sum(w * h for w, h in zip(row, hidden)))
            for row in self.w_out
        ]
        self.last_hidden = hidden
        self.last_spikes = prev
        self.last_spike_counts = counts
        self.last_spike_history = history
        if track_plasticity:
            self._accumulate_eligibility(vector, history)
        return output, hidden

    def _accumulate_eligibility(self, vector, history):
        pre_input = [0.0] * self.input_size
        pre_hidden = [0.0] * self.hidden_size
        post_hidden = [0.0] * self.hidden_size
        for spikes in history:
            for j, post_spike in enumerate(spikes):
                if post_spike:
                    for i, pre_value in enumerate(vector):
                        delta = post_spike * pre_input[i] - .5 * pre_value * post_hidden[j]
                        self.eligibility_in[j][i] = (
                            .995 * self.eligibility_in[j][i] + delta * .0002
                        )
                for i, pre_spike in enumerate(spikes):
                    if i == j:
                        continue
                    delta = post_spike * pre_hidden[i] - .5 * pre_spike * post_hidden[j]
                    self.eligibility_rec[j][i] = (
                        .995 * self.eligibility_rec[j][i] + delta * .0002
                    )
            pre_input = [.90 * trace + value for trace, value in zip(pre_input, vector)]
            pre_hidden = [.90 * trace + spike for trace, spike in zip(pre_hidden, spikes)]
            post_hidden = [.90 * trace + spike for trace, spike in zip(post_hidden, spikes)]

    def hebbian_update(self, input_vector, hidden, reward=1.0):
        if len(input_vector) != self.input_size or len(hidden) != self.hidden_size:
            raise ValueError("Dimensões incompatíveis para atualização hebbiana")
        rate = self.learning_rate * max(-1.0, min(1.0, float(reward)))
        for j in range(self.hidden_size):
            for i in range(self.input_size):
                self.w_in[j][i] = max(-1.5, min(
                    1.5, self.w_in[j][i] + rate * self.eligibility_in[j][i]
                ))
            for i in range(self.hidden_size):
                if i != j:
                    self.w_rec[j][i] = max(-.8, min(
                        .8, self.w_rec[j][i] + rate * self.eligibility_rec[j][i]
                    ))
        decay = .5 if reward > 0 else .8
        self.eligibility_in = [[v * decay for v in row] for row in self.eligibility_in]
        self.eligibility_rec = [[v * decay for v in row] for row in self.eligibility_rec]

    def reset_eligibility(self):
        self.eligibility_in = [[0.0] * self.input_size for _ in range(self.hidden_size)]
        self.eligibility_rec = [[0.0] * self.hidden_size for _ in range(self.hidden_size)]

    def state_dict(self):
        return {
            "w_in": self.w_in, "w_rec": self.w_rec, "w_out": self.w_out,
            "eligibility_in": self.eligibility_in,
            "eligibility_rec": self.eligibility_rec,
            "output_updates": self.output_updates
        }

    def load_state_dict(self, state):
        try:
            wi, wr, wo = state["w_in"], state["w_rec"], state["w_out"]
            valid = (
                len(wi) == self.hidden_size and all(len(r) == self.input_size for r in wi)
                and len(wr) == self.hidden_size and all(len(r) == self.hidden_size for r in wr)
                and len(wo) == self.output_size and all(len(r) == self.hidden_size for r in wo)
            )
            if not valid:
                return False
            matrices = [wi, wr, wo]
            if any(not math.isfinite(float(v)) for matrix in matrices for row in matrix for v in row):
                return False
            self.w_in = [[float(v) for v in row] for row in wi]
            self.w_rec = [[float(v) for v in row] for row in wr]
            self.w_out = [[float(v) for v in row] for row in wo]
            self.output_updates = max(0, int(state.get("output_updates", 0)))
            ei, er = state.get("eligibility_in"), state.get("eligibility_rec")
            if ei is not None and len(ei) == self.hidden_size and all(len(r) == self.input_size for r in ei):
                self.eligibility_in = [[float(v) for v in row] for row in ei]
            if er is not None and len(er) == self.hidden_size and all(len(r) == self.hidden_size for r in er):
                self.eligibility_rec = [[float(v) for v in row] for row in er]
            return True
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
