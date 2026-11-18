"""Backend opcional de embeddings multilíngues pré-treinados.

Carrega Sentence Transformers somente no primeiro encode e somente de arquivos
locais/cache. Não baixa pesos nem faz chamadas de rede durante a inferência.
"""
import math


class TransformersSentenceEncoder:
    DEFAULT_PASSAGE_BATCH_SIZE = 8
    MAX_PASSAGE_BATCH_SIZE = 32

    def __init__(self, model_path, device="cpu", local_files_only=True,
                 max_seq_length=256, model_loader=None):
        self.model_path = str(model_path).strip()
        if not self.model_path:
            raise ValueError("model_path é obrigatório.")
        if str(device).lower() != "cpu":
            raise ValueError("Este backend suporta somente CPU nesta versão.")
        if not local_files_only:
            raise ValueError("Carregamento remoto está desativado; use arquivos locais.")
        self.device = "cpu"
        self.local_files_only = True
        self.max_seq_length = max(8, min(512, int(max_seq_length)))
        self.model_loader = model_loader
        self._model = None
        self.dimensions = None
        self.updates = 0
        self.semantic_weight = 0.85

    def _load(self):
        if self._model is not None:
            return self._model
        if self.model_loader is not None:
            model = self.model_loader(
                model_path=self.model_path, device=self.device,
                local_files_only=self.local_files_only,
                max_seq_length=self.max_seq_length,
            )
        else:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "Backend opcional ausente. Instale requirements-embeddings.txt "
                    "e disponibilize o modelo localmente."
                ) from exc
            model = SentenceTransformer(
                self.model_path, device="cpu", local_files_only=True
            )
            model.max_seq_length = self.max_seq_length
        self._model = model
        self.dimensions = int(model.get_sentence_embedding_dimension())
        return model

    @staticmethod
    def _normalize(vector):
        values = [float(value) for value in vector]
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values] if norm else [0.0] * len(values)

    def _encode(self, text, prefix):
        model = self._load()
        value = str(text).strip()
        if not value:
            return [0.0] * self.dimensions
        result = model.encode(
            [prefix + value], batch_size=1, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        )
        vector = result[0]
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        vector = self._normalize(vector)
        if len(vector) != self.dimensions:
            raise ValueError("O backend retornou dimensão de embedding inconsistente.")
        return vector

    def encode_query(self, text):
        return self._encode(text, "query: ")

    def encode_passages(self, texts, batch_size=DEFAULT_PASSAGE_BATCH_SIZE):
        """Codifica passagens em lotes pequenos, mantendo o prefixo E5."""
        try:
            batch_size = int(batch_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("batch_size deve ser um inteiro positivo.") from exc
        if batch_size < 1:
            raise ValueError("batch_size deve ser um inteiro positivo.")
        batch_size = min(self.MAX_PASSAGE_BATCH_SIZE, batch_size)

        values = [str(text).strip() for text in texts]
        model = self._load()
        vectors = [None] * len(values)
        nonempty_indices = [
            index for index, value in enumerate(values) if value
        ]

        for offset in range(0, len(nonempty_indices), batch_size):
            indices = nonempty_indices[offset:offset + batch_size]
            inputs = ["passage: " + values[index] for index in indices]
            result = model.encode(
                inputs, batch_size=min(batch_size, len(inputs)),
                normalize_embeddings=True, convert_to_numpy=True,
                show_progress_bar=False,
            )
            if hasattr(result, "tolist"):
                result = result.tolist()
            if len(result) != len(indices):
                raise ValueError(
                    "O backend retornou uma quantidade de embeddings inconsistente."
                )
            for index, vector in zip(indices, result):
                if hasattr(vector, "tolist"):
                    vector = vector.tolist()
                vector = self._normalize(vector)
                if len(vector) != self.dimensions:
                    raise ValueError(
                        "O backend retornou dimensão de embedding inconsistente."
                    )
                vectors[index] = vector

        for index, vector in enumerate(vectors):
            if vector is None:
                vectors[index] = [0.0] * self.dimensions
        return vectors

    def encode_passage(self, text):
        return self.encode_passages([text], batch_size=1)[0]

    def encode(self, text):
        return self.encode_query(text)

    def status(self):
        return {"type": "transformers_sentence_encoder",
                "model_path": self.model_path, "device": self.device,
                "local_files_only": self.local_files_only,
                "loaded": self._model is not None, "dimensions": self.dimensions,
                "semantic_weight": self.semantic_weight,
                "passage_batch_size": self.DEFAULT_PASSAGE_BATCH_SIZE}
