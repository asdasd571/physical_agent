from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from rag import (
    DocumentChunk,
    DocumentType,
    RetrievedChunk,
    configure_search_backend,
    load_hybrid_retriever,
    search_documents,
)
from rag.indexing import build_indexes


class AgentTestTokenizer:
    def tokenize(self, text: str) -> list[str]:
        return text.lower().split()


class AgentTestEmbedder:
    dimension = 2
    model_name = "agent-test-embedder"
    metrics = None

    def _vector(self, text: str) -> list[float]:
        normalized = text.lower()
        return [
            float("robot" in normalized or "로봇" in normalized),
            float("market" in normalized or "시장" in normalized),
        ]

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return np.asarray([self._vector(text) for text in texts], dtype=np.float32)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        return np.asarray(self._vector(query), dtype=np.float32)


def make_chunk(
    index: int,
    *,
    candidate_id: str | None,
    doc_type: DocumentType,
    content: str,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"agent_chunk_{index}",
        page_id=f"agent_page_{index}",
        source_id=f"agent_source_{index}",
        doc_id=f"agent_doc_{index}",
        candidate_id=candidate_id,
        doc_type=doc_type,
        page=index + 10,
        content=content,
        token_start=0,
        token_end=4,
        token_count=4,
        publisher="Agent Integration Publisher",
        title=f"Agent Integration Document {index}",
        url="https://example.com/report.pdf",
        published_at=None,
        local_path=Path(f"data/rag/documents/tech/agent_{index}.pdf"),
        sha256=f"{index + 1:x}" * 64,
    )


def tech_agent_search() -> list[RetrievedChunk]:
    """Represent another team member's Agent using only the public RAG API."""

    return search_documents(
        query="이 회사의 로봇핸드 실물 조작 성공률은?",
        candidate_id="company_a",
        doc_types=["tech"],
        top_k=5,
    )


def test_agent_can_load_index_and_call_public_search_contract(tmp_path: Path) -> None:
    chunks = [
        make_chunk(
            0,
            candidate_id="company_a",
            doc_type=DocumentType.TECH,
            content="company_a robot hand physical manipulation success rate",
        ),
        make_chunk(
            1,
            candidate_id="company_b",
            doc_type=DocumentType.TECH,
            content="company_b robot hand physical manipulation success rate",
        ),
        make_chunk(
            2,
            candidate_id=None,
            doc_type=DocumentType.MARKET,
            content="robot market growth",
        ),
    ]
    embedder = AgentTestEmbedder()
    tokenizer = AgentTestTokenizer()
    build_indexes(
        chunks,
        tmp_path,
        embedder=embedder,
        sparse_tokenizer=tokenizer,
        document_count=3,
        page_count=3,
        embedding_model=embedder.model_name,
    )
    configure_search_backend(
        load_hybrid_retriever(
            tmp_path,
            embedder=embedder,
            sparse_tokenizer=tokenizer,
        )
    )

    results = tech_agent_search()

    assert results
    assert all(isinstance(result, RetrievedChunk) for result in results)
    assert all(result.candidate_id == "company_a" for result in results)
    assert all(result.doc_type == DocumentType.TECH for result in results)
    assert results[0].model_dump().keys() >= {
        "chunk_id",
        "source_id",
        "doc_id",
        "page",
        "content",
        "score",
    }
