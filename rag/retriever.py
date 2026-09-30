"""Hybrid Dense + BM25 retriever used by the public search service."""

from __future__ import annotations

from collections.abc import Sequence

from .bm25_store import Bm25Store, SparseTokenizer
from .config import DEFAULT_TOP_K
from .dense_store import FaissDenseStore
from .embeddings import DenseEmbedder
from .fusion import RETRIEVAL_DEPTH, reciprocal_rank_fusion
from .models import DocumentType, RetrievedChunk


class HybridRetriever:
    """Search a shared chunk corpus through Dense, BM25, then RRF."""

    def __init__(
        self,
        dense_store: FaissDenseStore,
        bm25_store: Bm25Store,
        embedder: DenseEmbedder,
        tokenizer: SparseTokenizer,
    ) -> None:
        dense_chunk_ids = {chunk.chunk_id for chunk in dense_store.chunks}
        bm25_chunk_ids = {chunk.chunk_id for chunk in bm25_store.chunks}
        if dense_chunk_ids != bm25_chunk_ids:
            raise ValueError("Dense and BM25 stores must contain the same chunk IDs")
        self.dense_store = dense_store
        self.bm25_store = bm25_store
        self.embedder = embedder
        self.tokenizer = tokenizer

    def search(
        self,
        query: str,
        candidate_id: str | None = None,
        doc_types: Sequence[DocumentType] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        dense_results = self.dense_store.search(
            query,
            self.embedder,
            top_k=RETRIEVAL_DEPTH,
            candidate_id=candidate_id,
            doc_types=doc_types,
        )
        bm25_results = self.bm25_store.search(
            query,
            self.tokenizer,
            top_k=RETRIEVAL_DEPTH,
            candidate_id=candidate_id,
            doc_types=doc_types,
        )
        return reciprocal_rank_fusion(dense_results, bm25_results, top_k=top_k)
