"""Small supervised autoregressive decoder conditioned on the LIF readout.

This is a compact CPU-oriented Elman RNN, not a pretrained language model.
"""
import hashlib
import math
import random
import re


class NeuralTextDecoder:
    SPECIAL_TOKENS = ("<pad>", "<bos>", "<eos>", "<unk>")
    TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
    CLOSING_PUNCTUATION = {".", ",", "!", "?", ";", ":", "%", ")", "]", "}"}
    OPENING_PUNCTUATION = {"(", "[", "{"}

    def __init__(self, context_size=32, hidden_size=16, embedding_size=16,
                 max_vocab=512, learning_rate=0.03, seed=42,
                 max_sequence_length=32):
        self.context_size = int(context_size)
        self.hidden_size = int(hidden_size)
        self.embedding_size = int(embedding_size)
        self.max_vocab = max(4, int(max_vocab))
        self.learning_rate = float(learning_rate)
        self.seed = int(seed)
        self.max_sequence_length = max(2, int(max_sequence_length))
        if min(self.context_size, self.hidden_size, self.embedding_size) < 1:
            raise ValueError("Dimensões do decoder devem ser positivas.")
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("learning_rate deve ser finito e positivo.")

        self.vocab = {token: index for index, token in enumerate(self.SPECIAL_TOKENS)}
        self.embeddings = []
        self.w_context = []
        self.w_input = []
        self.w_recurrent = []
        self.w_output = []
        self.b_context = [0.0] * self.hidden_size
        self.b_hidden = [0.0] * self.hidden_size
        self.b_output = [0.0] * len(self.SPECIAL_TOKENS)
        self.trained_steps = 0
        self.trained_tokens = 0
        self._rng = random.Random(self.seed)
        self._initialize_parameters()

    @classmethod
    def tokenize(cls, text):
        return [token.lower() for token in cls.TOKEN_PATTERN.findall(str(text))]

    @classmethod
    def detokenize(cls, tokens):
        result = ""
        for token in tokens:
            if token in cls.CLOSING_PUNCTUATION:
                result = result.rstrip() + token
            elif token in cls.OPENING_PUNCTUATION:
                result += (" " if result else "") + token
            else:
                result += (" " if result else "") + token
        result = result.strip()
        return result[:1].upper() + result[1:] if result else ""

    def _random_vector(self, label, size, scale=None):
        digest = hashlib.blake2b(
            (str(self.seed) + ":" + str(label)).encode("utf-8"), digest_size=16
        ).digest()
        rng = random.Random(int.from_bytes(digest, "little"))
        bound = float(scale if scale is not None else 1.0 / math.sqrt(max(1, size)))
        return [rng.uniform(-bound, bound) for _ in range(size)]

    def _random_matrix(self, rows, columns, label):
        return [
            self._random_vector(f"{label}:{row}", columns)
            for row in range(rows)
        ]

    def _initialize_parameters(self):
        self.embeddings = [
            self._random_vector(f"embedding:{token}", self.embedding_size)
            for token in self.SPECIAL_TOKENS
        ]
        self.w_context = self._random_matrix(
            self.hidden_size, self.context_size, "context"
        )
        self.w_input = self._random_matrix(
            self.hidden_size, self.embedding_size, "input"
        )
        self.w_recurrent = self._random_matrix(
            self.hidden_size, self.hidden_size, "recurrent"
        )
        self.w_output = self._random_matrix(
            len(self.vocab), self.hidden_size, "output"
        )

    def _validate_context(self, context):
        values = [float(value) for value in context]
        if len(values) != self.context_size:
            raise ValueError("Dimensão do contexto LIF incompatível com o decoder.")
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Contexto LIF contém valores não finitos.")
        return values

    def fit_vocabulary(self, texts):
        added = 0
        for text in texts:
            for token in self.tokenize(text)[:self.max_sequence_length]:
                if token in self.vocab or len(self.vocab) >= self.max_vocab:
                    continue
                index = len(self.vocab)
                self.vocab[token] = index
                self.embeddings.append(
                    self._random_vector(f"embedding:{token}", self.embedding_size)
                )
                self.w_output.append(
                    self._random_vector(f"output:{token}", self.hidden_size)
                )
                self.b_output.append(0.0)
                added += 1
        return added

    def _softmax(self, logits):
        maximum = max(logits)
        values = [math.exp(max(-60.0, value - maximum)) for value in logits]
        total = sum(values)
        if not math.isfinite(total) or total <= 0:
            return [1.0 / len(logits)] * len(logits)
        return [value / total for value in values]

    def _initial_hidden(self, context):
        return [
            math.tanh(
                sum(weight * value for weight, value in zip(row, context))
                + self.b_context[index]
            )
            for index, row in enumerate(self.w_context)
        ]

    def _step(self, token_id, previous_hidden):
        embedding = self.embeddings[token_id]
        hidden = []
        for index in range(self.hidden_size):
            activation = (
                sum(weight * value for weight, value in zip(self.w_input[index], embedding))
                + sum(weight * value for weight, value in zip(
                    self.w_recurrent[index], previous_hidden
                ))
                + self.b_hidden[index]
            )
            hidden.append(math.tanh(activation))
        logits = [
            sum(weight * value for weight, value in zip(row, hidden)) + self.b_output[index]
            for index, row in enumerate(self.w_output)
        ]
        return hidden, self._softmax(logits)

    def _sequence(self, answer):
        tokens = self.tokenize(answer)[:self.max_sequence_length - 1]
        if not tokens:
            return [], []
        targets = [self.vocab.get(token, self.vocab["<unk>"]) for token in tokens]
        targets.append(self.vocab["<eos>"])
        inputs = [self.vocab["<bos>"]] + targets[:-1]
        return inputs, targets

    def train_pair(self, context, answer, learning_rate=None):
        context = self._validate_context(context)
        self.fit_vocabulary([answer])
        inputs, targets = self._sequence(answer)
        if not targets:
            raise ValueError("A resposta de treino não pode ser vazia.")
        rate = self.learning_rate if learning_rate is None else float(learning_rate)
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("learning_rate deve ser finito e positivo.")

        h0 = self._initial_hidden(context)
        previous = list(h0)
        caches = []
        loss = 0.0
        for input_id, target_id in zip(inputs, targets):
            hidden, probabilities = self._step(input_id, previous)
            loss -= math.log(max(probabilities[target_id], 1e-12))
            caches.append((input_id, target_id, list(previous), hidden, probabilities))
            previous = hidden
        sequence_length = len(targets)
        scale = 1.0 / sequence_length

        grad_w_context = [[0.0] * self.context_size for _ in range(self.hidden_size)]
        grad_w_input = [[0.0] * self.embedding_size for _ in range(self.hidden_size)]
        grad_w_recurrent = [[0.0] * self.hidden_size for _ in range(self.hidden_size)]
        grad_w_output = [[0.0] * self.hidden_size for _ in range(len(self.vocab))]
        grad_b_context = [0.0] * self.hidden_size
        grad_b_hidden = [0.0] * self.hidden_size
        grad_b_output = [0.0] * len(self.vocab)
        grad_embeddings = {}

        dh_next = [0.0] * self.hidden_size
        for input_id, target_id, previous_hidden, hidden, probabilities in reversed(caches):
            dlogits = list(probabilities)
            dlogits[target_id] -= 1.0
            for vocab_index, derivative in enumerate(dlogits):
                grad_b_output[vocab_index] += derivative * scale
                for hidden_index, activation in enumerate(hidden):
                    grad_w_output[vocab_index][hidden_index] += (
                        derivative * activation * scale
                    )

            dh = list(dh_next)
            for hidden_index in range(self.hidden_size):
                dh[hidden_index] += sum(
                    self.w_output[vocab_index][hidden_index] * dlogits[vocab_index]
                    for vocab_index in range(len(self.vocab))
                )
            da = [
                dh[index] * (1.0 - hidden[index] * hidden[index])
                for index in range(self.hidden_size)
            ]
            embedding = self.embeddings[input_id]
            embedding_gradient = grad_embeddings.setdefault(
                input_id, [0.0] * self.embedding_size
            )
            for hidden_index in range(self.hidden_size):
                grad_b_hidden[hidden_index] += da[hidden_index] * scale
                for embedding_index in range(self.embedding_size):
                    grad_w_input[hidden_index][embedding_index] += (
                        da[hidden_index] * embedding[embedding_index] * scale
                    )
                    embedding_gradient[embedding_index] += (
                        self.w_input[hidden_index][embedding_index]
                        * da[hidden_index] * scale
                    )
                for recurrent_index in range(self.hidden_size):
                    grad_w_recurrent[hidden_index][recurrent_index] += (
                        da[hidden_index] * previous_hidden[recurrent_index] * scale
                    )
            dh_next = [
                sum(
                    self.w_recurrent[hidden_index][index] * da[hidden_index]
                    for hidden_index in range(self.hidden_size)
                )
                for index in range(self.hidden_size)
            ]

        dh0 = [
            dh_next[index] * (1.0 - h0[index] * h0[index])
            for index in range(self.hidden_size)
        ]
        for hidden_index in range(self.hidden_size):
            grad_b_context[hidden_index] += dh0[hidden_index] * scale
            for context_index in range(self.context_size):
                grad_w_context[hidden_index][context_index] += (
                    dh0[hidden_index] * context[context_index] * scale
                )

        def apply_vector(parameters, gradients):
            for index, gradient in enumerate(gradients):
                parameters[index] -= rate * max(-5.0, min(5.0, gradient))

        def apply_matrix(parameters, gradients):
            for row_index, row in enumerate(gradients):
                apply_vector(parameters[row_index], row)

        apply_matrix(self.w_context, grad_w_context)
        apply_matrix(self.w_input, grad_w_input)
        apply_matrix(self.w_recurrent, grad_w_recurrent)
        apply_matrix(self.w_output, grad_w_output)
        apply_vector(self.b_context, grad_b_context)
        apply_vector(self.b_hidden, grad_b_hidden)
        apply_vector(self.b_output, grad_b_output)
        for token_id, gradients in grad_embeddings.items():
            apply_vector(self.embeddings[token_id], gradients)

        self.trained_steps += 1
        self.trained_tokens += sequence_length
        return {"loss": loss / sequence_length, "tokens": sequence_length}

    def _score_sequence(self, context, answer):
        context = self._validate_context(context)
        inputs, targets = self._sequence(answer)
        if not targets:
            return None
        hidden = self._initial_hidden(context)
        total_loss = 0.0
        correct = 0
        for input_id, target_id in zip(inputs, targets):
            hidden, probabilities = self._step(input_id, hidden)
            total_loss -= math.log(max(probabilities[target_id], 1e-12))
            if max(range(len(probabilities)), key=probabilities.__getitem__) == target_id:
                correct += 1
        count = len(targets)
        loss = total_loss / count
        return {
            "loss": loss,
            "perplexity": math.exp(min(loss, 20.0)),
            "token_accuracy": correct / count,
            "known_tokens": sum(
                token in self.vocab for token in self.tokenize(answer)[:self.max_sequence_length - 1]
            ),
            "oov_tokens": sum(
                token not in self.vocab for token in self.tokenize(answer)[:self.max_sequence_length - 1]
            ),
            "total_tokens": count,
        }

    def score(self, context, answer):
        result = self._score_sequence(context, answer)
        if result is None:
            return {
                "loss": None, "perplexity": None, "token_accuracy": None,
                "known_tokens": 0, "oov_tokens": 0, "total_tokens": 0,
            }
        return result

    def generate(self, context, max_tokens=None):
        context = self._validate_context(context)
        limit = self.max_sequence_length if max_tokens is None else int(max_tokens)
        if limit < 1:
            raise ValueError("max_tokens deve ser positivo.")
        limit = min(limit, self.max_sequence_length)
        if self.trained_steps <= 0:
            return {
                "text": "", "tokens": [], "token_count": 0,
                "confidence": 0.0, "terminated": False, "reason": "untrained",
            }

        hidden = self._initial_hidden(context)
        current = self.vocab["<bos>"]
        tokens = []
        confidences = []
        terminated = False
        for _ in range(limit):
            hidden, probabilities = self._step(current, hidden)
            next_id = max(range(len(probabilities)), key=probabilities.__getitem__)
            next_token = next(token for token, index in self.vocab.items() if index == next_id)
            if next_token == "<eos>":
                terminated = True
                break
            if next_token in {"<pad>", "<bos>"}:
                break
            if len(tokens) >= 2 and tokens[-1] == next_token and tokens[-2] == next_token:
                break
            if next_token != "<unk>":
                tokens.append(next_token)
                confidences.append(probabilities[next_id])
            current = next_id

        return {
            "text": self.detokenize(tokens),
            "tokens": tokens,
            "token_count": len(tokens),
            "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "terminated": terminated,
            "reason": None if tokens else "empty_generation",
        }

    def state_dict(self):
        return {
            "schema_version": 1,
            "context_size": self.context_size,
            "hidden_size": self.hidden_size,
            "embedding_size": self.embedding_size,
            "max_vocab": self.max_vocab,
            "learning_rate": self.learning_rate,
            "seed": self.seed,
            "max_sequence_length": self.max_sequence_length,
            "vocab": [token for token, _ in sorted(self.vocab.items(), key=lambda item: item[1])],
            "embeddings": self.embeddings,
            "w_context": self.w_context,
            "w_input": self.w_input,
            "w_recurrent": self.w_recurrent,
            "w_output": self.w_output,
            "b_context": self.b_context,
            "b_hidden": self.b_hidden,
            "b_output": self.b_output,
            "trained_steps": self.trained_steps,
            "trained_tokens": self.trained_tokens,
        }

    def load_state_dict(self, state):
        try:
            if not isinstance(state, dict) or state.get("schema_version") != 1:
                return False
            if (
                int(state["context_size"]) != self.context_size
                or int(state["hidden_size"]) != self.hidden_size
                or int(state["embedding_size"]) != self.embedding_size
            ):
                return False
            vocab = list(state["vocab"])
            if vocab[:len(self.SPECIAL_TOKENS)] != list(self.SPECIAL_TOKENS):
                return False
            if len(vocab) > self.max_vocab or len(set(vocab)) != len(vocab):
                return False
            embeddings = [[float(value) for value in row] for row in state["embeddings"]]
            w_context = [[float(value) for value in row] for row in state["w_context"]]
            w_input = [[float(value) for value in row] for row in state["w_input"]]
            w_recurrent = [[float(value) for value in row] for row in state["w_recurrent"]]
            w_output = [[float(value) for value in row] for row in state["w_output"]]
            b_context = [float(value) for value in state["b_context"]]
            b_hidden = [float(value) for value in state["b_hidden"]]
            b_output = [float(value) for value in state["b_output"]]
            expected_shapes = (
                len(embeddings) == len(vocab)
                and all(len(row) == self.embedding_size for row in embeddings)
                and len(w_context) == self.hidden_size
                and all(len(row) == self.context_size for row in w_context)
                and len(w_input) == self.hidden_size
                and all(len(row) == self.embedding_size for row in w_input)
                and len(w_recurrent) == self.hidden_size
                and all(len(row) == self.hidden_size for row in w_recurrent)
                and len(w_output) == len(vocab)
                and all(len(row) == self.hidden_size for row in w_output)
                and len(b_context) == self.hidden_size
                and len(b_hidden) == self.hidden_size
                and len(b_output) == len(vocab)
            )
            all_values = (
                [value for row in embeddings for value in row]
                + [value for row in w_context for value in row]
                + [value for row in w_input for value in row]
                + [value for row in w_recurrent for value in row]
                + [value for row in w_output for value in row]
                + b_context + b_hidden + b_output
            )
            if not expected_shapes or any(not math.isfinite(value) for value in all_values):
                return False
            self.vocab = {token: index for index, token in enumerate(vocab)}
            self.embeddings = embeddings
            self.w_context = w_context
            self.w_input = w_input
            self.w_recurrent = w_recurrent
            self.w_output = w_output
            self.b_context = b_context
            self.b_hidden = b_hidden
            self.b_output = b_output
            self.trained_steps = max(0, int(state.get("trained_steps", 0)))
            self.trained_tokens = max(0, int(state.get("trained_tokens", 0)))
            return True
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
