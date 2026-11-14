"""Encoders lexicais legados e encoder semântico treinável por pares contrastivos.

O SemanticEncoder é um modelo leve de embeddings de palavras/bigramas treináveis.
Ele não possui conhecimento semântico inato: aprende similaridade a partir de pares
rotulados fornecidos no dataset. HashEncoder permanece apenas para compatibilidade.
"""
import hashlib
import math
import random
from .utils import tokenize


class HashEncoder:
    """Codificação lexical determinística legada; não é semântica."""
    def __init__(self, dimensions=64):
        self.dimensions = int(dimensions)

    def encode(self, text):
        vec = [0.0] * self.dimensions
        for pos, word in enumerate(tokenize(text)):
            digest = hashlib.blake2b(word.encode("utf-8"), digest_size=16).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 else -1.0
            vec[idx] += sign / (1.0 + 0.08 * pos)
        return _normalize(vec)


def _normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else [0.0 for _ in vec]


class SemanticEncoder:
    """Encoder compacto, treinável e persistível, sem dependências externas.

    Representa frases pela média de embeddings de tokens e bigramas. O aprendizado
    contrastivo aproxima pares equivalentes e afasta pares negativos. A qualidade
    semântica depende da cobertura e qualidade dos pares de treinamento.
    """
    def __init__(self, dimensions=64, learning_rate=0.04, margin=0.25, seed=42,
                 max_vocab=30000):
        self.dimensions = int(dimensions)
        self.learning_rate = float(learning_rate)
        self.margin = float(margin)
        self.seed = int(seed)
        self.max_vocab = int(max_vocab)
        self.vocab = {}
        self.embeddings = []
        self.updates = 0

    def _features(self, text):
        words = tokenize(text)
        if not words:
            return ["<empty>"]
        features = list(words)
        features.extend("bi:" + a + "_" + b for a, b in zip(words, words[1:]))
        # Subwords de caracteres permitem compartilhar parâmetros entre flexões
        # e palavras OOV sem expandir o vocabulário durante a inferência.
        for word in words:
            padded = "^" + word[:48] + "$"
            for size in (3, 4, 5):
                features.extend(
                    "char:" + padded[index:index + size]
                    for index in range(len(padded) - size + 1)
                )
        return features

    def feature_coverage(self, text):
        """Mede cobertura lexical e de subwords sem alterar o vocabulário."""
        features = self._features(text)
        subwords = [feature for feature in features if feature.startswith("char:")]
        known = sum(feature in self.vocab for feature in features)
        known_subwords = sum(feature in self.vocab for feature in subwords)
        return {
            "total_features": len(features),
            "known_features": known,
            "feature_coverage": known / len(features) if features else 0.0,
            "total_subword_features": len(subwords),
            "known_subword_features": known_subwords,
            "subword_feature_coverage": (
                known_subwords / len(subwords) if subwords else 0.0
            ),
        }

    def _initial_vector(self, feature):
        # Hash é usado somente para inicialização determinística, não para codificar
        # a frase. Os parâmetros passam a ser ajustados pelo treinamento contrastivo.
        digest = hashlib.blake2b(
            (str(self.seed) + ":" + feature).encode("utf-8"), digest_size=16
        ).digest()
        rng = random.Random(int.from_bytes(digest, "little"))
        scale = 1.0 / math.sqrt(max(1, self.dimensions))
        return [rng.uniform(-scale, scale) for _ in range(self.dimensions)]

    def _ensure(self, feature):
        if feature not in self.vocab:
            if len(self.vocab) >= self.max_vocab:
                return None
            self.vocab[feature] = len(self.embeddings)
            self.embeddings.append(self._initial_vector(feature))
        return self.vocab[feature]

    def fit_vocabulary(self, texts):
        added = 0
        for text in texts:
            for feature in self._features(text):
                before = len(self.vocab)
                self._ensure(feature)
                added += len(self.vocab) - before
        return added

    def encode(self, text):
        features = self._features(text)
        vectors = []
        for feature in features:
            index = self.vocab.get(feature)
            # Tokens desconhecidos recebem um vetor inicial determinístico sem
            # alterar o vocabulário durante uma consulta de inferência.
            vectors.append(self.embeddings[index] if index is not None
                           else self._initial_vector(feature))
        if not vectors:
            return [0.0] * self.dimensions
        pooled = [sum(v[d] for v in vectors) / len(vectors)
                  for d in range(self.dimensions)]
        return _normalize(pooled)

    def fit_pair(self, text_a, text_b, label=1.0):
        """Executa uma atualização contrastiva; label=1 positivo, label=0 negativo."""
        if not str(text_a).strip() or not str(text_b).strip():
            raise ValueError("Os dois textos do par devem ser preenchidos.")
        y = float(label)
        if y not in (0.0, 1.0):
            raise ValueError("O rótulo contrastivo deve ser 0 ou 1.")
        fa, fb = self._features(text_a), self._features(text_b)
        self.fit_vocabulary([text_a, text_b])
        ia = [self.vocab[x] for x in fa if x in self.vocab]
        ib = [self.vocab[x] for x in fb if x in self.vocab]
        if not ia or not ib:
            return {"loss": 0.0, "similarity": 0.0, "updated": False}

        a = [sum(self.embeddings[i][d] for i in ia) / len(ia)
             for d in range(self.dimensions)]
        b = [sum(self.embeddings[i][d] for i in ib) / len(ib)
             for d in range(self.dimensions)]
        na = math.sqrt(sum(v * v for v in a)) or 1e-12
        nb = math.sqrt(sum(v * v for v in b)) or 1e-12
        cosine = max(-1.0, min(1.0, sum(x * z for x, z in zip(a, b)) / (na * nb)))

        if y == 1.0:
            loss = 1.0 - cosine
            active = True
            sign = -1.0
        else:
            loss = max(0.0, cosine - self.margin)
            active = loss > 0.0
            sign = 1.0
        if not active:
            return {"loss": loss, "similarity": cosine, "updated": False}

        grad_a = [sign * (b[d] / (na * nb) - cosine * a[d] / (na * na))
                  for d in range(self.dimensions)]
        grad_b = [sign * (a[d] / (na * nb) - cosine * b[d] / (nb * nb))
                  for d in range(self.dimensions)]
        rate = self.learning_rate
        for idx in ia:
            row = self.embeddings[idx]
            for d in range(self.dimensions):
                row[d] -= rate * grad_a[d] / len(ia)
        for idx in ib:
            row = self.embeddings[idx]
            for d in range(self.dimensions):
                row[d] -= rate * grad_b[d] / len(ib)
        self.updates += 1
        return {"loss": loss, "similarity": cosine, "updated": True}

    def state_dict(self):
        return {
            "version": 1, "dimensions": self.dimensions, "learning_rate": self.learning_rate,
            "margin": self.margin, "seed": self.seed, "max_vocab": self.max_vocab,
            "vocab": self.vocab, "embeddings": self.embeddings, "updates": self.updates,
        }

    def load_state_dict(self, state):
        try:
            dims = int(state["dimensions"])
            vocab = state["vocab"]
            embeddings = state["embeddings"]
            if dims != self.dimensions or not isinstance(vocab, dict):
                return False
            if len(vocab) != len(embeddings):
                return False
            if sorted(vocab.values()) != list(range(len(embeddings))):
                return False
            if any(len(row) != self.dimensions for row in embeddings):
                return False
            if any(not math.isfinite(float(v)) for row in embeddings for v in row):
                return False
            self.vocab = {str(k): int(v) for k, v in vocab.items()}
            self.embeddings = [[float(v) for v in row] for row in embeddings]
            self.learning_rate = float(state.get("learning_rate", self.learning_rate))
            self.margin = float(state.get("margin", self.margin))
            self.seed = int(state.get("seed", self.seed))
            self.max_vocab = int(state.get("max_vocab", self.max_vocab))
            self.updates = int(state.get("updates", 0))
            return True
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
