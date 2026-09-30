"""Stable search interface consumed by analysis Agents."""

from __future__ import annotations

from typing import Protocol, Sequence

from .models import DocumentType, RetrievedChunk


class SearchBackend(Protocol):
    def search(
        self,
        query: str,
        candidate_id: str | None = None,
        doc_types: Sequence[DocumentType] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]: ...


class SearchBackendNotConfiguredError(RuntimeError):
    pass


_backend: SearchBackend | None = None


def configure_search_backend(backend: SearchBackend) -> None:
    """Register the concrete hybrid retriever during application startup."""

    global _backend
    _backend = backend


def search_documents(
    query: str,
    candidate_id: str | None = None,
    doc_types: list[str] | None = None,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Search indexed evidence using the project-wide public contract.

    The concrete BGE-M3/BM25/RRF backend is supplied by ``feature/rag``. This
    interface intentionally returns no mock results when the backend is absent.
    """

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    normalized_candidate_id = candidate_id.strip() if candidate_id else None
    if candidate_id is not None and normalized_candidate_id is None:
        raise ValueError("candidate_id must not be blank")
    parsed_doc_types = (
        [DocumentType(value.strip().lower()) for value in doc_types]
        if doc_types is not None
        else None
    )
    if _backend is None:
        raise SearchBackendNotConfiguredError(
            "RAG search backend is not configured; build/load the index first"
        )
    return _backend.search(
        query=normalized_query,
        candidate_id=normalized_candidate_id,
        doc_types=parsed_doc_types,
        top_k=top_k,
    )
