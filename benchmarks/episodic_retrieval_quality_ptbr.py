"""Benchmark offline de qualidade da recuperação episódica em PT-BR.

O modo lexical é o padrão e usa somente a biblioteca padrão do Python.
Encoders opcionais exigem checkpoint/diretório local explicitamente informado.
Nenhum modo baixa modelos, acessa a rede ou lê a memória pessoal do operador.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nixlms_core.encoding import SemanticEncoder
from nixlms_core.episodic import EpisodicMemory
from nixlms_core.pretrained_encoder import TransformersSentenceEncoder
from nixlms_core.utils import normalize


DEFAULT_DATA_DIR = ROOT / "datasets" / "episodic_retrieval_ptbr"
DATA_FILES = ("episodes.jsonl", "queries.jsonl", "qrels.tsv")
VALID_CATEGORIES = {
    "parafrase",
    "coloquial",
    "variacao_ortografica",
    "contextual",
    "sem_resposta",
}
VALID_SPLITS = {"validation", "test"}
METRIC_NAMES = ("ndcg_at_k", "mrr_at_k", "recall_at_k", "precision_at_k")


def _read_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    str(path.name) + " linha " + str(line_number)
                    + ": JSON inválido: " + str(exc)
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    str(path.name) + " linha " + str(line_number)
                    + ": cada linha deve conter um objeto JSON."
                )
            rows.append(value)
    return rows


def _read_qrels(path):
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["query_id", "episode_id", "relevance"]:
            raise ValueError(
                "qrels.tsv deve possuir as colunas query_id, episode_id e relevance."
            )
        rows = []
        for line_number, row in enumerate(reader, 2):
            try:
                relevance = int(row["relevance"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "qrels.tsv linha " + str(line_number)
                    + ": relevance deve ser um inteiro."
                ) from exc
            rows.append({
                "query_id": str(row["query_id"]).strip(),
                "episode_id": str(row["episode_id"]).strip(),
                "relevance": relevance,
            })
    return rows


def validate_dataset(episodes, queries, qrels):
    if len(episodes) < 50:
        raise ValueError("O corpus deve conter pelo menos 50 episódios.")
    if len(queries) < 30:
        raise ValueError("O conjunto deve conter pelo menos 30 consultas.")

    episode_ids = set()
    for index, episode in enumerate(episodes, 1):
        episode_id = str(episode.get("id", "")).strip()
        if not episode_id or episode_id in episode_ids:
            raise ValueError("ID de episódio vazio ou duplicado na posição " + str(index) + ".")
        episode_ids.add(episode_id)
        if not str(episode.get("user_input", "")).strip():
            raise ValueError("Episódio " + episode_id + " sem user_input.")
        if not str(episode.get("assistant_output", "")).strip():
            raise ValueError("Episódio " + episode_id + " sem assistant_output.")
        if not isinstance(episode.get("tags", []), list):
            raise ValueError("tags deve ser uma lista no episódio " + episode_id + ".")

    query_ids = set()
    normalized_queries = set()
    query_by_id = {}
    for index, query in enumerate(queries, 1):
        query_id = str(query.get("query_id", "")).strip()
        query_text = str(query.get("query", "")).strip()
        if not query_id or query_id in query_ids:
            raise ValueError("ID de consulta vazio ou duplicado na posição " + str(index) + ".")
        if not query_text:
            raise ValueError("Consulta " + query_id + " sem texto.")
        normalized = normalize(query_text)
        if not normalized or normalized in normalized_queries:
            raise ValueError("Consulta vazia ou duplicada após normalização: " + query_id + ".")
        if query.get("category") not in VALID_CATEGORIES:
            raise ValueError("Categoria inválida na consulta " + query_id + ".")
        if query.get("split") not in VALID_SPLITS:
            raise ValueError("Split inválido na consulta " + query_id + ".")
        if not isinstance(query.get("expects_no_answer"), bool):
            raise ValueError("expects_no_answer deve ser booleano em " + query_id + ".")
        if (query.get("category") == "sem_resposta") != query["expects_no_answer"]:
            raise ValueError("Categoria e expectativa de resposta inconsistentes em " + query_id + ".")
        query_ids.add(query_id)
        normalized_queries.add(normalized)
        query_by_id[query_id] = query

    qrels_by_query = {}
    seen_pairs = set()
    for row in qrels:
        query_id = row["query_id"]
        episode_id = row["episode_id"]
        relevance = row["relevance"]
        pair = (query_id, episode_id)
        if query_id not in query_ids:
            raise ValueError("qrel referencia consulta inexistente: " + query_id + ".")
        if episode_id not in episode_ids:
            raise ValueError("qrel referencia episódio inexistente: " + episode_id + ".")
        if pair in seen_pairs:
            raise ValueError("qrel duplicado para " + query_id + " / " + episode_id + ".")
        if relevance not in (1, 2):
            raise ValueError("relevance deve ser 1 ou 2 em " + query_id + ".")
        if query_by_id[query_id]["expects_no_answer"]:
            raise ValueError("Consulta sem resposta não pode possuir qrels: " + query_id + ".")
        seen_pairs.add(pair)
        qrels_by_query.setdefault(query_id, {})[episode_id] = relevance

    for query_id, query in query_by_id.items():
        has_qrels = bool(qrels_by_query.get(query_id))
        if query["expects_no_answer"] and has_qrels:
            raise ValueError("Consulta sem resposta possui julgamento: " + query_id + ".")
        if not query["expects_no_answer"] and not has_qrels:
            raise ValueError("Consulta respondível sem qrels: " + query_id + ".")

    return qrels_by_query


def compute_dataset_hash(data_dir):
    digest = hashlib.sha256()
    for filename in DATA_FILES:
        path = Path(data_dir) / filename
        digest.update(filename.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_dataset(data_dir=DEFAULT_DATA_DIR):
    data_dir = Path(data_dir)
    episodes = _read_jsonl(data_dir / "episodes.jsonl")
    queries = _read_jsonl(data_dir / "queries.jsonl")
    qrels = _read_qrels(data_dir / "qrels.tsv")
    qrels_by_query = validate_dataset(episodes, queries, qrels)
    return episodes, queries, qrels, qrels_by_query, compute_dataset_hash(data_dir)


def calculate_query_metrics(ranked_ids, relevant_grades, k=5):
    if int(k) < 1:
        raise ValueError("k deve ser um inteiro positivo.")
    relevant = {str(key): int(value) for key, value in relevant_grades.items()}
    if not relevant:
        raise ValueError("A consulta precisa possuir pelo menos um julgamento relevante.")

    top_ids = [str(value) for value in ranked_ids[:int(k)]]
    hits = [
        (rank, relevant[episode_id])
        for rank, episode_id in enumerate(top_ids, 1)
        if episode_id in relevant
    ]
    dcg = sum(
        (2 ** grade - 1) / math.log2(rank + 1)
        for rank, grade in hits
    )
    ideal_grades = sorted(relevant.values(), reverse=True)[:int(k)]
    idcg = sum(
        (2 ** grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(ideal_grades, 1)
    )
    first_rank = hits[0][0] if hits else None
    return {
        "ndcg_at_k": dcg / idcg if idcg else 0.0,
        "mrr_at_k": 1.0 / first_rank if first_rank else 0.0,
        "recall_at_k": len(hits) / len(relevant),
        "precision_at_k": len(hits) / int(k),
        "first_relevant_rank": first_rank,
        "relevant_retrieved": len(hits),
    }


def _rounded(value):
    return round(float(value), 6) if value is not None else None


def summarize_group(rows, k=5):
    answerable = [row for row in rows if not row["expects_no_answer"]]
    no_answer = [row for row in rows if row["expects_no_answer"]]

    metrics = {}
    for name in METRIC_NAMES:
        values = [row["metrics"][name] for row in answerable]
        metrics[name] = _rounded(statistics.mean(values)) if values else None

    abstained = sum(not row["ranked_episode_ids"] for row in no_answer)
    false_positives = len(no_answer) - abstained
    retrieved = sum(bool(row["ranked_episode_ids"]) for row in answerable)
    relevant_hits = sum(row["first_relevant_rank"] is not None for row in answerable)

    return {
        "query_count": len(rows),
        "answerable_query_count": len(answerable),
        **metrics,
        "retrieval_coverage": _rounded(retrieved / len(answerable)) if answerable else None,
        "relevant_hit_rate": _rounded(relevant_hits / len(answerable)) if answerable else None,
        "abstention": {
            "no_answer_query_count": len(no_answer),
            "abstained_query_count": abstained,
            "abstention_rate": _rounded(abstained / len(no_answer)) if no_answer else None,
            "false_positive_query_count": false_positives,
            "false_positive_rate": _rounded(false_positives / len(no_answer)) if no_answer else None,
        },
        "cutoff": int(k),
    }


def evaluate_dataset(data_dir=DEFAULT_DATA_DIR, *, encoder=None, encoder_info=None,
                     k=5, min_score=0.05, passage_batch_size=8):
    episodes, queries, qrels, qrels_by_query, data_hash = load_dataset(data_dir)
    with tempfile.TemporaryDirectory(prefix="nixlms-episodic-ptbr-") as temporary:
        memory_path = Path(temporary) / "episodic.json"
        memory_path.write_text(
            json.dumps(episodes, ensure_ascii=False),
            encoding="utf-8",
        )
        memory = EpisodicMemory(
            memory_path,
            max_items=len(episodes),
            embedding_cache_size=0,
            passage_batch_size=passage_batch_size,
        )
        query_results = []
        for query in queries:
            query_id = query["query_id"]
            results = memory.recall(
                query["query"],
                encoder,
                limit=k,
                min_score=min_score,
            )
            ranked_ids = [str(item.get("id", "")) for _, item in results]
            relevant = qrels_by_query.get(query_id, {})
            if relevant:
                values = calculate_query_metrics(ranked_ids, relevant, k=k)
                first_rank = values["first_relevant_rank"]
            else:
                values = None
                first_rank = None
            query_results.append({
                "query_id": query_id,
                "category": query["category"],
                "split": query["split"],
                "expects_no_answer": query["expects_no_answer"],
                "ranked_episode_ids": ranked_ids,
                "returned_count": len(ranked_ids),
                "relevant_count": len(relevant),
                "relevant_retrieved_count": values["relevant_retrieved"] if values else 0,
                "first_relevant_rank": first_rank,
                "abstained": not bool(ranked_ids),
                "metrics": values,
            })

    categories = sorted({query["category"] for query in queries})
    splits = sorted({query["split"] for query in queries})
    by_category = {
        category: summarize_group(
            [row for row in query_results if row["category"] == category], k=k
        )
        for category in categories
    }
    by_split = {
        split: summarize_group(
            [row for row in query_results if row["split"] == split], k=k
        )
        for split in splits
    }
    return {
        "schema_version": 1,
        "dataset": {
            "id": "nixlms-episodic-retrieval-ptbr-v1",
            "sha256": data_hash,
            "episode_count": len(episodes),
            "query_count": len(queries),
            "qrel_count": len(qrels),
            "answerable_query_count": sum(not row["expects_no_answer"] for row in queries),
            "no_answer_query_count": sum(row["expects_no_answer"] for row in queries),
        },
        "evaluation": {
            "target": "EpisodicMemory.recall",
            "k": int(k),
            "min_score": float(min_score),
            "passage_batch_size": int(passage_batch_size),
            "ranking_formula_changed": False,
        },
        "encoder": encoder_info or {
            "mode": "lexical",
            "identity": "jaccard_token_overlap",
        },
        "metrics": {
            "overall": summarize_group(query_results, k=k),
            "by_category": by_category,
            "by_split": by_split,
        },
        "queries": query_results,
        "limitations": [
            "Corpus piloto sintético; não representa todos os domínios do português brasileiro.",
            "Qrels são uma curadoria editorial inicial, sem anotação independente.",
            "Resultados não são diretamente comparáveis aos leaderboards MTEB-BR ou BEIR.",
        ],
    }


def load_encoder(native_checkpoint=None, e5_model_path=None):
    if native_checkpoint and e5_model_path:
        raise ValueError("Escolha somente um encoder opcional por execução.")

    if native_checkpoint:
        path = Path(native_checkpoint).expanduser()
        if not path.is_file():
            raise FileNotFoundError("Checkpoint nativo local não encontrado.")
        raw = path.read_bytes()
        state = json.loads(raw.decode("utf-8"))
        if not isinstance(state, dict):
            raise ValueError("Checkpoint nativo deve conter um objeto JSON.")
        dimensions = int(state.get("dimensions", 0))
        if dimensions < 1:
            raise ValueError("Checkpoint nativo sem dimensão válida.")
        encoder = SemanticEncoder(dimensions=dimensions)
        if not encoder.load_state_dict(state):
            raise ValueError("Checkpoint nativo incompatível ou inválido.")
        return encoder, {
            "mode": "native",
            "dimensions": encoder.dimensions,
            "updates": encoder.updates,
            "checkpoint_sha256": hashlib.sha256(raw).hexdigest(),
        }

    if e5_model_path:
        path = Path(e5_model_path).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(
                "Diretório E5 local não encontrado; o benchmark não baixa modelos."
            )
        encoder = TransformersSentenceEncoder(
            str(path),
            device="cpu",
            local_files_only=True,
        )
        encoder.encode_query("teste local de recuperação episódica")
        return encoder, {
            "mode": "e5_local",
            "model_directory": path.name or "local-model",
            "dimensions": encoder.dimensions,
            "local_files_only": True,
        }

    return None, {
        "mode": "lexical",
        "identity": "jaccard_token_overlap",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=8)
    encoders = parser.add_mutually_exclusive_group()
    encoders.add_argument("--native-checkpoint", type=Path)
    encoders.add_argument("--e5-model-path", type=Path)
    parser.add_argument("--output", type=Path, help="arquivo JSON opcional para salvar o relatório")
    args = parser.parse_args()

    if args.k < 1:
        parser.error("k deve ser positivo.")
    if args.min_score < 0:
        parser.error("min-score não pode ser negativo.")
    if not 1 <= args.batch_size <= 32:
        parser.error("batch-size deve estar entre 1 e 32.")

    try:
        encoder, encoder_info = load_encoder(
            native_checkpoint=args.native_checkpoint,
            e5_model_path=args.e5_model_path,
        )
        report = evaluate_dataset(
            args.dataset_dir,
            encoder=encoder,
            encoder_info=encoder_info,
            k=args.k,
            min_score=args.min_score,
            passage_batch_size=args.batch_size,
        )
    except (OSError, ValueError, ImportError) as exc:
        parser.error(str(exc))

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.expanduser().parent.mkdir(parents=True, exist_ok=True)
        args.output.expanduser().write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
