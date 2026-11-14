"""Benchmark reproduzível da recuperação episódica com cache frio e aquecido.

Sem modelo local configurado, usa um encoder sintético determinístico para medir
o custo do caminho de cache e confirmar a quantidade de codificações. Para medir
o backend E5 real, informe --model-path ou configure NIXLMS_EMBEDDING_MODEL_PATH.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nixlms_core.episodic import EpisodicMemory
from nixlms_core.pretrained_encoder import TransformersSentenceEncoder


class SyntheticEncoder:
    dimensions = 32
    updates = 0
    semantic_weight = 1.0

    def __init__(self):
        self.batch_calls = 0
        self.encoded_passages = 0

    @staticmethod
    def _vector(text):
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [(value / 127.5) - 1.0 for value in digest]
        norm = sum(value * value for value in values) ** 0.5
        return [value / norm for value in values] if norm else [0.0] * len(values)

    def encode_query(self, text):
        return self._vector(text)

    def encode_passages(self, texts, batch_size=8):
        self.batch_calls += 1
        self.encoded_passages += len(texts)
        return [self._vector(text) for text in texts]


def run_case(size, batch_size, model_path):
    with tempfile.TemporaryDirectory() as tmp:
        memory = EpisodicMemory(
            Path(tmp) / "episodic.json",
            max_items=size,
            embedding_cache_size=size,
            passage_batch_size=batch_size,
        )
        timestamp = datetime.now(timezone.utc).isoformat()
        memory.items = [{
            "id": str(index),
            "timestamp": timestamp,
            "user_input": "pergunta de memória número " + str(index),
            "assistant_output": "resposta sintética de referência " + str(index),
            "tags": [],
            "outcome": "",
            "importance": 0.5,
            "feedback": None,
        } for index in range(size)]

        if model_path:
            encoder = TransformersSentenceEncoder(
                model_path, device="cpu", local_files_only=True
            )
            encoder.encode_query("")
            encoder_name = "sentence-transformers-local"
        else:
            encoder = SyntheticEncoder()
            encoder_name = "synthetic"

        start = perf_counter()
        cold = memory.recall(
            "pergunta de memória", encoder, limit=5, min_score=0
        )
        cold_ms = (perf_counter() - start) * 1000.0
        cold_stats = memory.stats()

        start = perf_counter()
        warm = memory.recall(
            "pergunta de memória", encoder, limit=5, min_score=0
        )
        warm_ms = (perf_counter() - start) * 1000.0
        warm_stats = memory.stats()

        cold_ids = [item["id"] for _, item in cold]
        warm_ids = [item["id"] for _, item in warm]
        if cold_ids != warm_ids:
            raise RuntimeError("A ordenação mudou entre a recuperação fria e aquecida.")

        return {
            "episodes": size,
            "encoder": encoder_name,
            "cold_ms": round(cold_ms, 3),
            "warm_ms": round(warm_ms, 3),
            "cold_encoded_passages": cold_stats["episodic_encoded_passages"],
            "warm_additional_encoded_passages": (
                warm_stats["episodic_encoded_passages"]
                - cold_stats["episodic_encoded_passages"]
            ),
            "cold_encoder_calls": cold_stats["episodic_passage_encoder_calls"],
            "warm_additional_encoder_calls": (
                warm_stats["episodic_passage_encoder_calls"]
                - cold_stats["episodic_passage_encoder_calls"]
            ),
            "cache_hits": warm_stats["episodic_embedding_cache_hits"],
            "cache_misses": warm_stats["episodic_embedding_cache_misses"],
            "cache_evictions": warm_stats["episodic_embedding_cache_evictions"],
            "cache_entries": warm_stats["episodic_embedding_cache_entries"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes", nargs="+", type=int, default=[100, 500, 2000],
        help="quantidades de episódios para medir",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument(
        "--model-path",
        default=os.getenv("NIXLMS_EMBEDDING_MODEL_PATH", "").strip(),
        help="caminho local do modelo E5; não baixa pesos",
    )
    args = parser.parse_args()
    if any(size < 1 for size in args.sizes):
        parser.error("todos os tamanhos devem ser positivos")
    if not 1 <= args.batch_size <= 32:
        parser.error("batch-size deve estar entre 1 e 32")

    results = [
        run_case(size, args.batch_size, args.model_path)
        for size in args.sizes
    ]
    print(json.dumps({
        "batch_size": args.batch_size,
        "results": results,
        "note": (
            "O encoder sintético mede o caminho de cache; use model-path para "
            "medir latência do modelo E5 local. Os tempos variam por hardware."
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
