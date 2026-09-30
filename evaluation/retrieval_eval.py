"""Evaluate a retriever with fixed questions and exact document-page labels."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from rag.embeddings import BgeM3Embedder
from rag.indexing import INDEX_RUN_FILENAME, load_hybrid_retriever
from rag.models import DocumentType, RetrievedChunk
from rag.tokenizer import KiwiTechnicalTokenizer


@dataclass(frozen=True, slots=True)
class RelevantPage:
    doc_id: str
    page: int


@dataclass(frozen=True, slots=True)
class RetrievalQuestion:
    question_id: str
    query: str
    relevant_pages: tuple[RelevantPage, ...]
    candidate_id: str | None = None
    doc_types: tuple[DocumentType, ...] | None = None
    language_pair: str | None = None


@dataclass(frozen=True, slots=True)
class QuestionResult:
    question_id: str
    hit: bool
    reciprocal_rank: float
    first_relevant_rank: int | None
    latency_ms: float
    returned_pages: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    evaluated_at: str
    question_count: int
    top_k: int
    hit_rate_at_5: float
    mrr_at_5: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    by_language_pair: dict[str, dict[str, float | int]]
    questions: tuple[QuestionResult, ...]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class Searcher(Protocol):
    def search(
        self,
        query: str,
        candidate_id: str | None = None,
        doc_types: Sequence[DocumentType] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]: ...


def _required_text(data: dict[str, Any], field: str, context: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{field} must be a non-empty string")
    return value.strip()


def load_questions(path: str | Path) -> list[RetrievalQuestion]:
    """Load and validate the fixed retrieval evaluation dataset."""

    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("retrieval question file must contain a non-empty JSON list")

    questions: list[RetrievalQuestion] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload):
        context = f"question[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{context} must be an object")
        question_id = _required_text(item, "question_id", context)
        if question_id in seen_ids:
            raise ValueError(f"duplicate question_id: {question_id}")
        seen_ids.add(question_id)

        raw_pages = item.get("relevant_pages")
        if not isinstance(raw_pages, list) or not raw_pages:
            raise ValueError(f"{context}.relevant_pages must be a non-empty list")
        relevant_pages: list[RelevantPage] = []
        seen_pages: set[tuple[str, int]] = set()
        for page_index, raw_page in enumerate(raw_pages):
            page_context = f"{context}.relevant_pages[{page_index}]"
            if not isinstance(raw_page, dict):
                raise ValueError(f"{page_context} must be an object")
            doc_id = _required_text(raw_page, "doc_id", page_context)
            page = raw_page.get("page")
            if not isinstance(page, int) or isinstance(page, bool) or page <= 0:
                raise ValueError(f"{page_context}.page must be a positive integer")
            key = (doc_id, page)
            if key not in seen_pages:
                relevant_pages.append(RelevantPage(doc_id=doc_id, page=page))
                seen_pages.add(key)

        raw_doc_types = item.get("doc_types")
        doc_types = (
            tuple(DocumentType(value) for value in raw_doc_types)
            if raw_doc_types is not None
            else None
        )
        candidate_id = item.get("candidate_id")
        if candidate_id is not None:
            if not isinstance(candidate_id, str) or not candidate_id.strip():
                raise ValueError(f"{context}.candidate_id must be null or non-empty")
            candidate_id = candidate_id.strip()
        language_pair = item.get("language_pair")
        if language_pair is not None:
            if not isinstance(language_pair, str) or not language_pair.strip():
                raise ValueError(f"{context}.language_pair must be null or non-empty")
            language_pair = language_pair.strip()

        questions.append(
            RetrievalQuestion(
                question_id=question_id,
                query=_required_text(item, "query", context),
                relevant_pages=tuple(relevant_pages),
                candidate_id=candidate_id,
                doc_types=doc_types,
                language_pair=language_pair,
            )
        )
    return questions


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _aggregate(results: Sequence[QuestionResult]) -> dict[str, float | int]:
    latencies = [result.latency_ms for result in results]
    return {
        "question_count": len(results),
        "hit_rate_at_5": sum(result.hit for result in results) / len(results),
        "mrr_at_5": sum(result.reciprocal_rank for result in results) / len(results),
        "mean_latency_ms": sum(latencies) / len(latencies),
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
    }


def evaluate_retrieval(
    retriever: Searcher,
    questions: Sequence[RetrievalQuestion],
    *,
    top_k: int = 5,
) -> EvaluationReport:
    """Run fixed questions and calculate exact-page Hit Rate, MRR, and latency."""

    if not questions:
        raise ValueError("at least one retrieval question is required")
    if top_k != 5:
        raise ValueError("STEP 9 metrics are fixed at top_k=5")

    results: list[QuestionResult] = []
    language_results: dict[str, list[QuestionResult]] = defaultdict(list)
    for question in questions:
        started = perf_counter()
        returned = retriever.search(
            question.query,
            candidate_id=question.candidate_id,
            doc_types=question.doc_types,
            top_k=top_k,
        )
        latency_ms = (perf_counter() - started) * 1000
        relevant = {(page.doc_id, page.page) for page in question.relevant_pages}
        first_rank = next(
            (
                rank
                for rank, result in enumerate(returned[:top_k], start=1)
                if (result.doc_id, result.page) in relevant
            ),
            None,
        )
        result = QuestionResult(
            question_id=question.question_id,
            hit=first_rank is not None,
            reciprocal_rank=1.0 / first_rank if first_rank else 0.0,
            first_relevant_rank=first_rank,
            latency_ms=latency_ms,
            returned_pages=tuple(
                {
                    "rank": rank,
                    "doc_id": chunk.doc_id,
                    "page": chunk.page,
                    "chunk_id": chunk.chunk_id,
                    "score": chunk.score,
                }
                for rank, chunk in enumerate(returned[:top_k], start=1)
            ),
        )
        results.append(result)
        if question.language_pair:
            language_results[question.language_pair].append(result)

    metrics = _aggregate(results)
    return EvaluationReport(
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        question_count=len(results),
        top_k=top_k,
        hit_rate_at_5=float(metrics["hit_rate_at_5"]),
        mrr_at_5=float(metrics["mrr_at_5"]),
        mean_latency_ms=float(metrics["mean_latency_ms"]),
        p50_latency_ms=float(metrics["p50_latency_ms"]),
        p95_latency_ms=float(metrics["p95_latency_ms"]),
        by_language_pair={
            pair: _aggregate(pair_results)
            for pair, pair_results in sorted(language_results.items())
        },
        questions=tuple(results),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate persisted Hybrid RAG retrieval")
    parser.add_argument("--questions", default="evaluation/retrieval_questions.json")
    parser.add_argument("--index-dir", default="data/rag/index")
    parser.add_argument("--output", default=None)
    parser.add_argument("--device", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    index_directory = Path(args.index_dir)
    embedder = BgeM3Embedder(device=args.device)
    retriever = load_hybrid_retriever(
        index_directory,
        embedder=embedder,
        sparse_tokenizer=KiwiTechnicalTokenizer(),
    )
    report = evaluate_retrieval(retriever, load_questions(args.questions))
    payload = report.model_dump()
    run_metadata_path = index_directory / INDEX_RUN_FILENAME
    if run_metadata_path.is_file():
        payload["index"] = json.loads(run_metadata_path.read_text(encoding="utf-8"))
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
