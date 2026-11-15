"""Benchmark comparativo da recuperação episódica: cache desabilitado, cold e warm.

O encoder sintético determinístico é o padrão e não requer dependências externas.
O modo E5 aceita somente um caminho local/cache já disponível; nenhum peso é baixado.
Os tempos excluem a criação dos objetos de memória e o carregamento inicial do modelo.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
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

    @staticmethod
    def _vector(text):
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [(value / 127.5) - 1.0 for value in digest]
        norm = sum(value * value for value in values) ** 0.5
        return [value / norm for value in values] if norm else [0.0] * len(values)

    def encode_query(self, text):
        return self._vector(text)

    def encode_passages(self, texts, batch_size=8):
        return [self._vector(text) for text in texts]


def percentile(values, percent):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Não é possível calcular percentil sem amostras.")
    rank = max(1, math.ceil((float(percent) / 100.0) * len(ordered)))
    return ordered[min(len(ordered) - 1, rank - 1)]


def summarize_latency(samples):
    return {
        "median_ms": round(median(samples), 3),
        "p95_ms": round(percentile(samples, 95), 3),
        "samples": len(samples),
    }


def assert_same_retrieval(reference, candidate, *, label, tolerance=1e-5):
    reference_ids = [item["id"] for _, item in reference]
    candidate_ids = [item["id"] for _, item in candidate]
    if reference_ids != candidate_ids:
        raise RuntimeError(label + ": IDs ou ordenação divergiram do cache desabilitado.")

    reference_scores = {item["id"]: score for score, item in reference}
    candidate_scores = {item["id"]: score for score, item in candidate}
    max_delta = max(
        (
            abs(reference_scores[episode_id] - candidate_scores[episode_id])
            for episode_id in reference_scores
        ),
        default=0.0,
    )
    if max_delta > tolerance:
        raise RuntimeError(
            label + ": diferença de score " + str(max_delta)
            + " excedeu a tolerância " + str(tolerance) + "."
        )
    return max_delta


def make_episodes(size):
    timestamp = datetime.now(timezone.utc).isoformat()
    return [{
        "id": str(index),
        "timestamp": timestamp,
        "user_input": "pergunta de memória número " + str(index),
        "assistant_output": "resposta sintética de referência " + str(index),
        "context": {},
        "outcome": "",
        "source": "benchmark",
        "importance": 0.5,
        "feedback": None,
        "tags": [],
    } for index in range(size)]


def make_memory(path, size, batch_size, cache_size):
    return EpisodicMemory(
        path,
        max_items=size,
        embedding_cache_size=cache_size,
        passage_batch_size=batch_size,
    )


def run_case(size, batch_size, model_path, repeats):
    with tempfile.TemporaryDirectory() as tmp:
        episode_path = Path(tmp) / "episodic.json"
        episode_path.write_text(
            json.dumps(make_episodes(size), ensure_ascii=False),
            encoding="utf-8",
        )

        if model_path:
            encoder = TransformersSentenceEncoder(
                model_path, device="cpu", local_files_only=True
            )
            encoder.encode_query("")
            encoder_name = "sentence-transformers-local"
        else:
            encoder = SyntheticEncoder()
            encoder_name = "synthetic"

        query = "pergunta de memória"
        baseline_memory = make_memory(episode_path, size, batch_size, 0)
        baseline_samples = []
        baseline_results = None
        for _ in range(repeats):
            start = perf_counter()
            baseline_results = baseline_memory.recall(
                query, encoder, limit=5, min_score=0
            )
            baseline_samples.append((perf_counter() - start) * 1000.0)
        baseline_stats = baseline_memory.stats()

        cold_samples = []
        cold_results = None
        cold_stats = None
        for _ in range(repeats):
            cold_memory = make_memory(episode_path, size, batch_size, size)
            start = perf_counter()
            cold_results = cold_memory.recall(
                query, encoder, limit=5, min_score=0
            )
            cold_samples.append((perf_counter() - start) * 1000.0)
            cold_stats = cold_memory.stats()

        warm_memory = make_memory(episode_path, size, batch_size, size)
        warm_memory.recall(query, encoder, limit=5, min_score=0)
        warm_before = warm_memory.stats()
        warm_samples = []
        warm_results = None
        for _ in range(repeats):
            start = perf_counter()
            warm_results = warm_memory.recall(
                query, encoder, limit=5, min_score=0
            )
            warm_samples.append((perf_counter() - start) * 1000.0)
        warm_after = warm_memory.stats()

        cold_delta = assert_same_retrieval(
            baseline_results, cold_results, label="Cache cold"
        )
        warm_delta = assert_same_retrieval(
            baseline_results, warm_results, label="Cache warm"
        )
        warm_encoded = (
            warm_after["episodic_encoded_passages"]
            - warm_before["episodic_encoded_passages"]
        )
        warm_calls = (
            warm_after["episodic_passage_encoder_calls"]
            - warm_before["episodic_passage_encoder_calls"]
        )
        if warm_encoded != 0 or warm_calls != 0:
            raise RuntimeError(
                "A recuperação warm voltou a codificar passagens: "
                + str(warm_encoded) + " passagens, " + str(warm_calls) + " chamadas."
            )

        return {
            "episodes": size,
            "encoder": encoder_name,
            "repeats": repeats,
            "latency_ms": {
                "cache_disabled": summarize_latency(baseline_samples),
                "cache_cold": summarize_latency(cold_samples),
                "cache_warm": summarize_latency(warm_samples),
            },
            "parity": {
                "same_ids_and_order": True,
                "max_abs_score_delta": round(max(cold_delta, warm_delta), 8),
                "score_tolerance": 1e-5,
            },
            "cache_disabled_encoded_passages_per_run": (
                baseline_stats["episodic_encoded_passages"] // repeats
            ),
            "cache_disabled_encoder_calls_per_run": (
                baseline_stats["episodic_passage_encoder_calls"] // repeats
            ),
            "cold_encoded_passages": cold_stats["episodic_encoded_passages"],
            "cold_encoder_calls": cold_stats["episodic_passage_encoder_calls"],
            "warm_additional_encoded_passages": warm_encoded // repeats,
            "warm_additional_encoder_calls": warm_calls // repeats,
            "warm_cache_hits_per_run": (
                warm_after["episodic_embedding_cache_hits"]
                - warm_before["episodic_embedding_cache_hits"]
            ) // repeats,
            "cache_entries": warm_after["episodic_embedding_cache_entries"],
            "cache_evictions": warm_after["episodic_embedding_cache_evictions"],
            "cold_ms": summarize_latency(cold_samples)["median_ms"],
            "warm_ms": summarize_latency(warm_samples)["median_ms"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes", nargs="+", type=int, default=[100, 500, 2000],
        help="quantidades de episódios para medir",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument(
        "--repeats", type=int, default=7,
        help="repetições por cenário para calcular mediana e p95",
    )
    parser.add_argument(
        "--model-path",
        default=os.getenv("NIXLMS_EMBEDDING_MODEL_PATH", "").strip(),
        help="caminho de modelo E5 já disponível localmente; não baixa pesos",
    )
    args = parser.parse_args()
    if any(size < 1 for size in args.sizes):
        parser.error("todos os tamanhos devem ser positivos")
    if not 1 <= args.batch_size <= 32:
        parser.error("batch-size deve estar entre 1 e 32")
    if args.repeats < 1:
        parser.error("repeats deve ser pelo menos 1")

    results = [
        run_case(size, args.batch_size, args.model_path, args.repeats)
        for size in args.sizes
    ]
    print(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "batch_size": args.batch_size,
        "repeats": args.repeats,
        "encoder": "sentence-transformers-local" if args.model_path else "synthetic",
        "cache_disabled_definition": (
            "embedding_cache_size=0 na mesma revisão; mede o caminho com cache "
            "desabilitado, não uma cópia pré-cache do código."
        ),
        "results": results,
        "note": (
            "O encoder sintético mede o custo do caminho de recuperação sem pesos "
            "externos. O modo E5 usa somente arquivos locais/cache e exclui o "
            "carregamento inicial do modelo dos tempos medidos. Os tempos dependem "
            "do hardware e não são limites de aceitação da CI."
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
