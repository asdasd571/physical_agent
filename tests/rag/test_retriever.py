from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from rag.bm25_store import Bm25Store
from rag.dense_store import FaissDenseStore
from rag.models import DocumentChunk, DocumentType
from rag.retriever import HybridRetriever
from rag.service import configure_search_backend, search_documents


class TestTokenizer:
    def tokenize(self, text: str) -> list[str]:
        return text.lower().split()


class TestEmbedder:
    dimension = 3

    def _vector(self, text: str) -> list[float]:
        normalized = text.lower()
        return [
            float("robot" in normalized),
            float("parent" in normalized or "market" in normalized),
            float("risk" in normalized),
        ]

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return np.asarray([self._vector(text) for text in texts], dtype=np.float32)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        return np.asarray(self._vector(query), dtype=np.float32)


def make_chunk(
    index: int,
    doc_type: DocumentType,
    candidate_id: str | None,
    content: str,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"chunk_{index}",
        page_id=f"page_{index}",
        source_id=f"src_{index}",
        doc_id=f"doc_{index}",
        candidate_id=candidate_id,
        doc_type=doc_type,
        page=index + 1,
        content=content,
        token_start=0,
        token_end=4,
        token_count=4,
        publisher="Publisher",
        title=f"Document {index}",
        url=None,
        published_at=None,
        local_path=Path(f"document_{index}.pdf"),
        sha256=f"{index + 1:x}" * 64,
    )


def build_retriever() -> HybridRetriever:
    chunks = [
        make_chunk(0, DocumentType.TECH, "company_a", "robot hand company-a"),
        make_chunk(1, DocumentType.TECH, "company_b", "robot hand company-b"),
        make_chunk(2, DocumentType.RISK, "company_a", "risk company-a"),
        make_chunk(3, DocumentType.PARENT, None, "parent manufacturing robot"),
        make_chunk(4, DocumentType.MARKET, None, "market robot growth"),
    ]
    embedder = TestEmbedder()
    tokenizer = TestTokenizer()
    dense = FaissDenseStore(dimension=embedder.dimension)
    dense.build(chunks, embedder)
    bm25 = Bm25Store()
    bm25.build(chunks, tokenizer)
    return HybridRetriever(dense, bm25, embedder, tokenizer)


def test_candidate_search_excludes_other_company_and_keeps_common_docs() -> None:
    results = build_retriever().search("robot", candidate_id="company_a", top_k=10)

    assert all(result.candidate_id != "company_b" for result in results)
    assert {result.doc_type for result in results} >= {
        DocumentType.TECH,
        DocumentType.PARENT,
        DocumentType.MARKET,
    }


def test_doc_type_filter_returns_only_requested_type() -> None:
    results = build_retriever().search(
        "robot",
        candidate_id="company_a",
        doc_types=[DocumentType.TECH],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].candidate_id == "company_a"
    assert results[0].doc_type == DocumentType.TECH


def test_public_search_documents_calls_complete_hybrid_backend() -> None:
    configure_search_backend(build_retriever())

    results = search_documents(
        query="robot",
        candidate_id="company_a",
        doc_types=["tech"],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].candidate_id == "company_a"
    assert results[0].metadata["retrieval"]["fusion"] == "rrf"
    assert results[0].score > 0


def test_public_search_normalizes_candidate_id() -> None:
    configure_search_backend(build_retriever())
    results = search_documents("robot", candidate_id=" company_a ", top_k=5)
    assert all(result.candidate_id != "company_b" for result in results)
