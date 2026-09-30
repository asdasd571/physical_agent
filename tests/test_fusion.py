from __future__ import annotations

from pathlib import Path

import pytest

from rag.bm25_store import Bm25SearchResult
from rag.dense_store import DenseSearchResult
from rag.fusion import RETRIEVAL_DEPTH, RRF_K, reciprocal_rank_fusion
from rag.models import DocumentChunk, DocumentType


def make_chunk(index: int, *, content: str | None = None) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"chunk_{index:02d}",
        page_id=f"page_{index + 1}",
        source_id="src_test",
        doc_id="doc_test",
        candidate_id="company_a",
        doc_type=DocumentType.TECH,
        page=index + 1,
        content=content or f"evidence {index}",
        token_start=index * 10,
        token_end=index * 10 + 10,
        token_count=10,
        publisher="Test Publisher",
        title="Test Report",
        url="https://example.com/report.pdf",
        published_at=None,
        local_path=Path("data/documents/tech/test.pdf"),
        sha256="a" * 64,
        metadata={"section": "test"},
    )


def test_chunk_found_by_both_channels_receives_sum_of_reciprocal_ranks() -> None:
    shared = make_chunk(0)
    dense = [DenseSearchResult(shared, 0.92)]
    bm25 = [Bm25SearchResult(shared, 8.4)]

    results = reciprocal_rank_fusion(dense, bm25)

    assert results[0].chunk_id == shared.chunk_id
    assert results[0].score == pytest.approx(2 / (RRF_K + 1))
    assert results[0].metadata["retrieval"]["dense_rank"] == 1
    assert results[0].metadata["retrieval"]["bm25_rank"] == 1


def test_dense_and_bm25_have_equal_rank_weight() -> None:
    dense_only = make_chunk(0)
    bm25_only = make_chunk(1)

    results = reciprocal_rank_fusion(
        [DenseSearchResult(dense_only, 0.99)],
        [Bm25SearchResult(bm25_only, 10.0)],
    )

    assert results[0].score == pytest.approx(results[1].score)
    assert {result.chunk_id for result in results} == {
        dense_only.chunk_id,
        bm25_only.chunk_id,
    }


def test_rank_is_used_instead_of_raw_retrieval_score() -> None:
    first = make_chunk(0)
    second = make_chunk(1)
    dense = [DenseSearchResult(first, 0.01), DenseSearchResult(second, 999.0)]

    results = reciprocal_rank_fusion(dense, [])

    assert [result.chunk_id for result in results] == [first.chunk_id, second.chunk_id]
    assert results[0].score == pytest.approx(1 / 61)
    assert results[1].score == pytest.approx(1 / 62)


def test_only_top_20_from_each_channel_are_fused() -> None:
    chunks = [make_chunk(index) for index in range(RETRIEVAL_DEPTH + 1)]
    dense = [DenseSearchResult(chunk, 1.0) for chunk in chunks]

    results = reciprocal_rank_fusion(dense, [], top_k=RETRIEVAL_DEPTH + 1)

    assert len(results) == RETRIEVAL_DEPTH
    assert chunks[-1].chunk_id not in {result.chunk_id for result in results}


def test_default_result_count_is_top_5() -> None:
    chunks = [make_chunk(index) for index in range(10)]
    dense = [DenseSearchResult(chunk, 1.0) for chunk in chunks]

    assert len(reciprocal_rank_fusion(dense, [])) == 5


def test_conflicting_chunk_metadata_is_rejected() -> None:
    dense_chunk = make_chunk(0, content="dense content")
    bm25_chunk = make_chunk(0, content="different content")

    with pytest.raises(ValueError, match="conflicting metadata"):
        reciprocal_rank_fusion(
            [DenseSearchResult(dense_chunk, 1.0)],
            [Bm25SearchResult(bm25_chunk, 1.0)],
        )


def test_empty_results_return_empty_list() -> None:
    assert reciprocal_rank_fusion([], []) == []
