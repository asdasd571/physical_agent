from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from numpy.typing import NDArray
import pytest

from rag.dense_store import FaissDenseStore
from rag.models import DocumentChunk, DocumentType


class FakeDenseEmbedder:
    """Small deterministic embedder for FAISS contract tests."""

    dimension = 3

    def __init__(self) -> None:
        self.vectors = {
            "robot hand manipulation": [1.0, 0.0, 0.0],
            "battery market growth": [0.0, 1.0, 0.0],
            "explosion safety risk": [0.0, 0.0, 1.0],
            "robot hand": [1.0, 0.0, 0.0],
        }

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return np.asarray([self.vectors[text] for text in texts], dtype=np.float32)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        return np.asarray(self.vectors[query], dtype=np.float32)


def make_chunk(index: int, content: str, page: int) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"chunk_{index}",
        page_id=f"page_{page}",
        source_id="src_test",
        doc_id="doc_test",
        candidate_id="company_a",
        doc_type=DocumentType.TECH,
        page=page,
        content=content,
        token_start=index * 10,
        token_end=index * 10 + 10,
        token_count=10,
        publisher="Test Publisher",
        title="Test Report",
        url="https://example.com/report.pdf",
        published_at=None,
        local_path=Path("data/documents/tech/test.pdf"),
        sha256="a" * 64,
    )


@pytest.fixture
def chunks() -> list[DocumentChunk]:
    return [
        make_chunk(0, "robot hand manipulation", 3),
        make_chunk(1, "battery market growth", 4),
        make_chunk(2, "explosion safety risk", 5),
    ]


def test_build_and_search_returns_most_similar_chunk(
    chunks: list[DocumentChunk],
) -> None:
    store = FaissDenseStore(dimension=3)
    embedder = FakeDenseEmbedder()
    store.build(chunks, embedder)

    results = store.search("robot hand", embedder, top_k=2)

    assert store.size == 3
    assert results[0].chunk.chunk_id == "chunk_0"
    assert results[0].score == pytest.approx(1.0)
    assert len(results) == 2


def test_save_and_load_preserves_index_and_chunk_metadata(
    tmp_path: Path,
    chunks: list[DocumentChunk],
) -> None:
    embedder = FakeDenseEmbedder()
    store = FaissDenseStore(dimension=3)
    store.build(chunks, embedder)
    store.save(tmp_path)

    loaded = FaissDenseStore.load(tmp_path)
    results = loaded.search("robot hand", embedder, top_k=3)

    assert loaded.size == 3
    assert results[0].chunk.chunk_id == "chunk_0"
    assert results[0].chunk.page == 3
    assert results[0].chunk.source_id == "src_test"
    assert results[0].chunk.local_path == Path("data/documents/tech/test.pdf")


def test_duplicate_chunk_ids_are_rejected(chunks: list[DocumentChunk]) -> None:
    store = FaissDenseStore(dimension=3)
    with pytest.raises(ValueError, match="duplicate chunk_id"):
        store.build([chunks[0], chunks[0]], FakeDenseEmbedder())


def test_embedding_dimension_mismatch_is_rejected(
    chunks: list[DocumentChunk],
) -> None:
    store = FaissDenseStore(dimension=4)
    with pytest.raises(ValueError, match="dimension mismatch"):
        store.build(chunks, FakeDenseEmbedder())


def test_empty_store_search_returns_empty_list() -> None:
    store = FaissDenseStore(dimension=3)
    assert store.search("robot hand", FakeDenseEmbedder(), top_k=20) == []
