from __future__ import annotations

from pathlib import Path

import pytest

from rag.bm25_store import Bm25Store
from rag.models import DocumentChunk, DocumentType


class SimpleTokenizer:
    def tokenize(self, text: str) -> list[str]:
        return text.lower().split()


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
        local_path=Path("data/rag/documents/tech/test.pdf"),
        sha256="a" * 64,
        metadata={"section": "test"},
    )


@pytest.fixture
def chunks() -> list[DocumentChunk]:
    return [
        make_chunk(0, "robot-hand tactile manipulation success", 3),
        make_chunk(1, "battery market growth statistics", 4),
        make_chunk(2, "explosion safety certification", 5),
    ]


def test_bm25_returns_matching_chunk_first(chunks: list[DocumentChunk]) -> None:
    store = Bm25Store()
    tokenizer = SimpleTokenizer()
    store.build(chunks, tokenizer)

    results = store.search("robot-hand tactile", tokenizer, top_k=20)

    assert store.size == 3
    assert results[0].chunk.chunk_id == "chunk_0"
    assert results[0].score > 0


def test_bm25_returns_only_positive_matches(chunks: list[DocumentChunk]) -> None:
    store = Bm25Store()
    tokenizer = SimpleTokenizer()
    store.build(chunks, tokenizer)

    assert store.search("unknown-term", tokenizer) == []


def test_save_and_load_preserves_sparse_results(
    tmp_path: Path,
    chunks: list[DocumentChunk],
) -> None:
    tokenizer = SimpleTokenizer()
    store = Bm25Store(k1=1.2, b=0.6)
    store.build(chunks, tokenizer)
    store.save(tmp_path)

    loaded = Bm25Store.load(tmp_path)
    results = loaded.search("battery growth", tokenizer)

    assert loaded.size == 3
    assert loaded.k1 == pytest.approx(1.2)
    assert loaded.b == pytest.approx(0.6)
    assert results[0].chunk.chunk_id == "chunk_1"
    assert results[0].chunk.page == 4
    assert results[0].chunk.metadata["section"] == "test"


def test_duplicate_chunk_ids_are_rejected(chunks: list[DocumentChunk]) -> None:
    with pytest.raises(ValueError, match="duplicate chunk_id"):
        Bm25Store().build([chunks[0], chunks[0]], SimpleTokenizer())


def test_invalid_bm25_parameters_are_rejected() -> None:
    with pytest.raises(ValueError, match="k1"):
        Bm25Store(k1=0)
    with pytest.raises(ValueError, match="b"):
        Bm25Store(b=1.1)
