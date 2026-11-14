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
        self.recurrent_updates = 0

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

    def _forward_with_trace(self, vector, modulation=1.0, state=None):
        if len(vector) != self.input_size:
            raise ValueError(f"Vetor deve ter {self.input_size} dimensões")
        values = [float(value) for value in vector]
        modulation = float(modulation)
        if any(not math.isfinite(value) for value in values) or not math.isfinite(modulation):
            raise ValueError("Entrada LIF deve conter valores finitos.")
        membrane = list(state if state is not None else [0.0] * self.hidden_size)
        if len(membrane) != self.hidden_size:
            raise ValueError("Estado recorrente possui dimensão inválida")
        membrane = [float(value) for value in membrane]
        if any(not math.isfinite(value) for value in membrane):
            raise ValueError("Estado recorrente deve conter valores finitos.")
        prev = [0.0] * self.hidden_size
        counts = [0.0] * self.hidden_size
        history = []
        previous_history = []
        membrane_history = []
        scale = max(1, self.steps) ** -.5
        for _ in range(self.steps):
            previous = list(prev)
            spikes = [0.0] * self.hidden_size
            membrane_pre = [0.0] * self.hidden_size
            for j in range(self.hidden_size):
                feed = sum(w * x for w, x in zip(self.w_in[j], values))
                recurrent = sum(w * x for w, x in zip(self.w_rec[j], prev))
                membrane_pre[j] = (
                    self.leak * membrane[j]
                    + (feed + recurrent) * scale * modulation
                )
                if membrane_pre[j] >= self.threshold:
                    spikes[j] = 1.0
                    counts[j] += 1.0
                    membrane[j] = 0.0
                else:
                    membrane[j] = membrane_pre[j]
            previous_history.append(previous)
            membrane_history.append(membrane_pre)
            history.append(spikes)
            prev = spikes

        rates = [count / self.steps for count in counts]
        analog = [
            math.tanh(
                sum(w * x for w, x in zip(self.w_in[j], values))
                + sum(w * x for w, x in zip(self.w_rec[j], prev))
            )
            for j in range(self.hidden_size)
        ]
        hidden = [
            .75 * rate + .25 * value
            for rate, value in zip(rates, analog)
        ]
        output = [
            math.tanh(sum(w * h for w, h in zip(row, hidden)))
            for row in self.w_out
        ]
        return output, hidden, {
            "history": history,
            "previous_history": previous_history,
            "membrane_history": membrane_history,
            "counts": counts,
            "analog": analog,
            "hidden": hidden,
            "output": output,
            "scale": scale,
            "modulation": modulation,
        }

    def _store_trace(self, trace):
        self.last_hidden = list(trace["hidden"])
        self.last_spikes = list(trace["history"][-1]) if trace["history"] else [0.0] * self.hidden_size
        self.last_spike_counts = list(trace["counts"])
        self.last_spike_history = [list(row) for row in trace["history"]]

    def forward(self, vector, modulation=1.0, state=None, track_plasticity=False):
        output, hidden, trace = self._forward_with_trace(vector, modulation, state)
        self._store_trace(trace)
        if track_plasticity:
            self._accumulate_eligibility(vector, trace["history"])
        return output, hidden

    def _recurrent_gradients(self, vector, trace, grad_hidden, surrogate_width):
        grad_in = [[0.0] * self.input_size for _ in range(self.hidden_size)]
        grad_rec = [[0.0] * self.hidden_size for _ in range(self.hidden_size)]
        history = trace["history"]
        steps = len(history)
        d_spikes = [[0.0] * self.hidden_size for _ in range(steps)]
        for t in range(steps):
            for j in range(self.hidden_size):
                d_spikes[t][j] += .75 * float(grad_hidden[j]) / steps

        last_spikes = history[-1] if history else [0.0] * self.hidden_size
        for j in range(self.hidden_size):
            derivative = (
                .25 * float(grad_hidden[j])
                * (1.0 - trace["analog"][j] ** 2)
            )
            for i in range(self.input_size):
                grad_in[j][i] += derivative * float(vector[i])
            for k in range(self.hidden_size):
                grad_rec[j][k] += derivative * last_spikes[k]
                if steps:
                    d_spikes[-1][k] += derivative * self.w_rec[j][k]

        d_membrane_after = [0.0] * self.hidden_size
        for t in range(steps - 1, -1, -1):
            d_membrane_pre = [0.0] * self.hidden_size
            for j in range(self.hidden_size):
                membrane_pre = trace["membrane_history"][t][j]
                spike = history[t][j]
                distance = abs((membrane_pre - self.threshold) / surrogate_width)
                surrogate = 1.0 / ((1.0 + distance) ** 2 * surrogate_width)
                d_membrane_pre[j] = (
                    d_spikes[t][j] * surrogate
                    + d_membrane_after[j] * (1.0 - spike - membrane_pre * surrogate)
                )
                current_gradient = (
                    d_membrane_pre[j] * trace["scale"] * trace["modulation"]
                )
                for i in range(self.input_size):
                    grad_in[j][i] += current_gradient * float(vector[i])
                previous_spikes = trace["previous_history"][t]
                for k in range(self.hidden_size):
                    grad_rec[j][k] += current_gradient * previous_spikes[k]

            if t > 0:
                for k in range(self.hidden_size):
                    d_spikes[t - 1][k] += (
                        trace["scale"] * trace["modulation"]
                        * sum(
                            self.w_rec[j][k] * d_membrane_pre[j]
                            for j in range(self.hidden_size)
                        )
                    )
            d_membrane_after = [
                self.leak * value for value in d_membrane_pre
            ]
        return grad_in, grad_rec

    def _apply_recurrent_gradients(self, grad_in, grad_rec, learning_rate,
                                   clip_norm=1.0):
        squared_norm = (
            sum(value * value for row in grad_in for value in row)
            + sum(value * value for row in grad_rec for value in row)
        )
        gradient_norm = math.sqrt(squared_norm)
        if not math.isfinite(gradient_norm):
            raise ValueError("Gradiente recorrente não finito.")
        if gradient_norm <= 1e-12:
            return {"updated": False, "gradient_norm": gradient_norm}
        scale = min(1.0, clip_norm / gradient_norm)
        for j in range(self.hidden_size):
            for i in range(self.input_size):
                self.w_in[j][i] = max(-1.5, min(
                    1.5, self.w_in[j][i] - learning_rate * scale * grad_in[j][i]
                ))
            for k in range(self.hidden_size):
                if j == k:
                    self.w_rec[j][k] = 0.0
                    continue
                self.w_rec[j][k] = max(-.8, min(
                    .8, self.w_rec[j][k] - learning_rate * scale * grad_rec[j][k]
                ))
        self.recurrent_updates += 1
        return {"updated": True, "gradient_norm": gradient_norm}

    @staticmethod
    def _validate_recurrent_training(vector, input_size, learning_rate,
                                     surrogate_width, clip_norm):
        values = [float(value) for value in vector]
        rate = float(learning_rate)
        width = float(surrogate_width)
        clipping = float(clip_norm)
        if len(values) != input_size:
            raise ValueError(f"Vetor deve ter {input_size} dimensões")
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Entrada recorrente deve conter valores finitos.")
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("learning_rate deve ser finito e positivo.")
        if not math.isfinite(width) or width <= 0:
            raise ValueError("surrogate_width deve ser finito e positivo.")
        if not math.isfinite(clipping) or clipping <= 0:
            raise ValueError("clip_norm deve ser finito e positivo.")
        return values, rate, width, clipping

    def train_recurrent(self, vector, target, learning_rate=0.001,
                        modulation=1.0, surrogate_width=0.5, clip_norm=1.0):
        """Treina w_in/w_rec via BPTT aproximado, mantendo o readout congelado."""
        values, rate, width, clipping = self._validate_recurrent_training(
            vector, self.input_size, learning_rate, surrogate_width, clip_norm
        )
        targets = [float(value) for value in target]
        if len(targets) != self.output_size:
            raise ValueError("Dimensão do alvo recorrente incompatível.")
        if any(not math.isfinite(value) or abs(value) > 1.0 for value in targets):
            raise ValueError("Alvos recorrentes devem ser finitos e estar em [-1, 1].")
        output, hidden, trace = self._forward_with_trace(values, modulation)
        loss = sum(
            (float(prediction) - expected) ** 2
            for prediction, expected in zip(output, targets)
        ) / self.output_size
        grad_hidden = []
        for j in range(self.hidden_size):
            grad_hidden.append(sum(
                2.0 * (output[i] - targets[i]) * (1.0 - output[i] ** 2)
                * self.w_out[i][j] / self.output_size
                for i in range(self.output_size)
            ))
        grad_in, grad_rec = self._recurrent_gradients(
            values, trace, grad_hidden, width
        )
        update = self._apply_recurrent_gradients(
            grad_in, grad_rec, rate, clipping
        )
        self._store_trace(trace)
        return {
            "loss": loss,
            "updated": update["updated"],
            "gradient_norm": update["gradient_norm"],
            "spike_rate": (
                sum(trace["counts"]) / (self.hidden_size * self.steps)
            ),
        }

    def train_recurrent_pair(self, vector_a, vector_b, label=1,
                             learning_rate=0.001, margin=0.25,
                             modulation=1.0, surrogate_width=0.5,
                             clip_norm=1.0):
        """Aprende diretamente no espaço oculto LIF, sem atualizar o readout."""
        left, rate, width, clipping = self._validate_recurrent_training(
            vector_a, self.input_size, learning_rate, surrogate_width, clip_norm
        )
        right = [float(value) for value in vector_b]
        if len(right) != self.input_size or any(not math.isfinite(v) for v in right):
            raise ValueError("Segundo vetor recorrente inválido.")
        numeric_label = float(label)
        if numeric_label not in (0.0, 1.0):
            raise ValueError("label deve ser 0 ou 1.")
        margin = float(margin)
        if not math.isfinite(margin) or not 0.0 <= margin <= 2.0:
            raise ValueError("margin deve estar entre 0 e 2.")

        _, hidden_a, trace_a = self._forward_with_trace(left, modulation)
        _, hidden_b, trace_b = self._forward_with_trace(right, modulation)
        norm_a = max(math.sqrt(sum(value * value for value in hidden_a)), 1e-8)
        norm_b = max(math.sqrt(sum(value * value for value in hidden_b)), 1e-8)
        similarity = max(-1.0, min(
            1.0, sum(a * b for a, b in zip(hidden_a, hidden_b)) / (norm_a * norm_b)
        ))
        if numeric_label == 1.0:
            loss = 1.0 - similarity
            derivative_sign = -1.0
        elif similarity > margin:
            loss = similarity - margin
            derivative_sign = 1.0
        else:
            loss = 0.0
            derivative_sign = 0.0

        if derivative_sign == 0.0:
            return {
                "loss": loss, "similarity": similarity,
                "updated": False, "gradient_norm": 0.0,
            }

        grad_hidden_a = [
            derivative_sign * (
                hidden_b[i] / (norm_a * norm_b)
                - similarity * hidden_a[i] / (norm_a * norm_a)
            )
            for i in range(self.hidden_size)
        ]
        grad_hidden_b = [
            derivative_sign * (
                hidden_a[i] / (norm_a * norm_b)
                - similarity * hidden_b[i] / (norm_b * norm_b)
            )
            for i in range(self.hidden_size)
        ]
        grad_in_a, grad_rec_a = self._recurrent_gradients(
            left, trace_a, grad_hidden_a, width
        )
        grad_in_b, grad_rec_b = self._recurrent_gradients(
            right, trace_b, grad_hidden_b, width
        )
        grad_in = [
            [(grad_in_a[j][i] + grad_in_b[j][i]) * .5
             for i in range(self.input_size)]
            for j in range(self.hidden_size)
        ]
        grad_rec = [
            [(grad_rec_a[j][k] + grad_rec_b[j][k]) * .5
             for k in range(self.hidden_size)]
            for j in range(self.hidden_size)
        ]
        update = self._apply_recurrent_gradients(
            grad_in, grad_rec, rate, clipping
        )
        self._store_trace(trace_b)
        return {
            "loss": loss,
            "similarity": similarity,
            "updated": update["updated"],
            "gradient_norm": update["gradient_norm"],
        }

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
            "output_updates": self.output_updates,
            "recurrent_updates": self.recurrent_updates
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
            self.recurrent_updates = max(0, int(state.get("recurrent_updates", 0)))
            ei, er = state.get("eligibility_in"), state.get("eligibility_rec")
            if ei is not None and len(ei) == self.hidden_size and all(len(r) == self.input_size for r in ei):
                self.eligibility_in = [[float(v) for v in row] for row in ei]
            if er is not None and len(er) == self.hidden_size and all(len(r) == self.hidden_size for r in er):
                self.eligibility_rec = [[float(v) for v in row] for row in er]
            return True
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
