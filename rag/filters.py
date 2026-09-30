"""Shared candidate and document-type filters applied before retrieval."""

from __future__ import annotations

from collections.abc import Sequence

from .models import DocumentChunk, DocumentType


def chunk_matches_filters(
    chunk: DocumentChunk,
    *,
    candidate_id: str | None = None,
    doc_types: Sequence[DocumentType] | None = None,
) -> bool:
    """Return whether a chunk belongs to the requested retrieval scope.

    Any document whose ``candidate_id`` is ``None`` is common and remains
    visible during a candidate-specific search. A requested ``doc_types`` list
    is always applied, so ``doc_types=[TECH]`` does not implicitly add other
    document types.
    """

    if doc_types is not None and chunk.doc_type not in set(doc_types):
        return False
    if candidate_id is None:
        return True
    if chunk.candidate_id == candidate_id:
        return True
    return chunk.candidate_id is None


def filter_chunk_indices(
    chunks: Sequence[DocumentChunk],
    *,
    candidate_id: str | None = None,
    doc_types: Sequence[DocumentType] | None = None,
) -> list[int]:
    return [
        index
        for index, chunk in enumerate(chunks)
        if chunk_matches_filters(
            chunk,
            candidate_id=candidate_id,
            doc_types=doc_types,
        )
    ]
