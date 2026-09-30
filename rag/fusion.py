"""Reciprocal Rank Fusion for Dense and BM25 retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .config import DEFAULT_TOP_K, DENSE_TOP_K, RRF_K as CONFIG_RRF_K
from .models import DocumentChunk, RetrievedChunk


RRF_K = CONFIG_RRF_K
RETRIEVAL_DEPTH = DENSE_TOP_K
DEFAULT_FINAL_TOP_K = DEFAULT_TOP_K


class RankedChunkResult(Protocol):
    chunk: DocumentChunk
    score: float


@dataclass(slots=True)
class _FusionEntry:
    chunk: DocumentChunk
    rrf_score: float = 0.0
    dense_rank: int | None = None
    bm25_rank: int | None = None
    dense_score: float | None = None
    bm25_score: float | None = None

    @property
    def best_rank(self) -> int:
        ranks = [rank for rank in (self.dense_rank, self.bm25_rank) if rank is not None]
        return min(ranks)


def _validate_same_chunk(existing: DocumentChunk, incoming: DocumentChunk) -> None:
    identity = ("source_id", "doc_id", "page", "content")
    mismatched = [
        field
        for field in identity
        if getattr(existing, field) != getattr(incoming, field)
    ]
    if mismatched:
        raise ValueError(
            f"chunk_id {existing.chunk_id!r} has conflicting metadata: "
            + ", ".join(mismatched)
        )


def _add_ranked_results(
    entries: dict[str, _FusionEntry],
    results: Sequence[RankedChunkResult],
    *,
    channel: str,
) -> None:
    seen: set[str] = set()
    for rank, result in enumerate(results[:RETRIEVAL_DEPTH], start=1):
        chunk_id = result.chunk.chunk_id
        if chunk_id in seen:
            continue
        seen.add(chunk_id)

        entry = entries.get(chunk_id)
        if entry is None:
            entry = _FusionEntry(chunk=result.chunk)
            entries[chunk_id] = entry
        else:
            _validate_same_chunk(entry.chunk, result.chunk)

        # Dense and BM25 have equal weight by design.
        entry.rrf_score += 1.0 / (RRF_K + rank)
        if channel == "dense":
            entry.dense_rank = rank
            entry.dense_score = float(result.score)
        else:
            entry.bm25_rank = rank
            entry.bm25_score = float(result.score)


def reciprocal_rank_fusion(
    dense_results: Sequence[RankedChunkResult],
    bm25_results: Sequence[RankedChunkResult],
    *,
    top_k: int = DEFAULT_FINAL_TOP_K,
) -> list[RetrievedChunk]:
    """Fuse Dense Top20 and BM25 Top20 with equal-weight RRF ``k=60``.

    The returned score is only a rank-fusion score. It is not evidence
    confidence, factual reliability, or probability.
    """

    if top_k <= 0:
        raise ValueError("top_k must be positive")

    entries: dict[str, _FusionEntry] = {}
    _add_ranked_results(entries, dense_results, channel="dense")
    _add_ranked_results(entries, bm25_results, channel="bm25")
    ranked = sorted(
        entries.values(),
        key=lambda entry: (-entry.rrf_score, entry.best_rank, entry.chunk.chunk_id),
    )

    fused: list[RetrievedChunk] = []
    for entry in ranked[:top_k]:
        chunk = entry.chunk
        metadata = dict(chunk.metadata)
        metadata["retrieval"] = {
            "fusion": "rrf",
            "rrf_k": RRF_K,
            "dense_rank": entry.dense_rank,
            "bm25_rank": entry.bm25_rank,
            "dense_score": entry.dense_score,
            "bm25_score": entry.bm25_score,
        }
        fused.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                doc_id=chunk.doc_id,
                candidate_id=chunk.candidate_id,
                doc_type=chunk.doc_type,
                page=chunk.page,
                content=chunk.content,
                score=entry.rrf_score,
                publisher=chunk.publisher,
                title=chunk.title,
                url=chunk.url,
                published_at=chunk.published_at,
                local_path=chunk.local_path,
                metadata=metadata,
            )
        )
    return fused
