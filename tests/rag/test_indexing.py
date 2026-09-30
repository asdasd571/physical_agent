from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from rag.indexing import INDEX_RUN_FILENAME, build_indexes, load_hybrid_retriever
from rag.models import DocumentChunk, DocumentType


class SimpleTokenizer:
    def tokenize(self, text: str) -> list[str]:
        return text.lower().split()


class SimpleEmbedder:
    dimension = 2
    model_name = "test-embedder"
    metrics = None

    def _vector(self, text: str) -> list[float]:
        return [float("robot" in text.lower()), float("market" in text.lower())]

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return np.asarray([self._vector(text) for text in texts], dtype=np.float32)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        return np.asarray(self._vector(query), dtype=np.float32)


def make_chunk(index: int, content: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"chunk_{index}",
        page_id=f"page_{index}",
        source_id=f"src_{index}",
        doc_id=f"doc_{index}",
        candidate_id="company_a" if index == 0 else None,
        doc_type=DocumentType.TECH if index == 0 else DocumentType.MARKET,
        page=index + 1,
        content=content,
        token_start=0,
        token_end=2,
        token_count=2,
        publisher="Publisher",
        title="Title",
        url=None,
        published_at=None,
        local_path=Path(f"doc_{index}.pdf"),
        sha256=f"{index + 1:x}" * 64,
    )


def test_build_save_load_and_search_indexes(tmp_path: Path) -> None:
    chunks = [make_chunk(0, "robot hand"), make_chunk(1, "robot market")]
    embedder = SimpleEmbedder()
    tokenizer = SimpleTokenizer()

    report = build_indexes(
        chunks,
        tmp_path,
        embedder=embedder,
        sparse_tokenizer=tokenizer,
        document_count=2,
        page_count=2,
        embedding_model=embedder.model_name,
    )
    retriever = load_hybrid_retriever(
        tmp_path,
        embedder=embedder,
        sparse_tokenizer=tokenizer,
    )
    results = retriever.search("robot", candidate_id="company_a", top_k=5)

    assert report.document_count == 2
    assert report.page_count == 2
    assert report.chunk_count == 2
    assert (tmp_path / INDEX_RUN_FILENAME).is_file()
    assert results[0].candidate_id == "company_a"
    assert {result.doc_type for result in results} == {
        DocumentType.TECH,
        DocumentType.MARKET,
    }
