from __future__ import annotations

from pathlib import Path

from rag.filters import chunk_matches_filters
from rag.models import DocumentChunk, DocumentType


def make_chunk(doc_type: DocumentType, candidate_id: str | None) -> DocumentChunk:
    key = candidate_id or "common"
    return DocumentChunk(
        chunk_id=f"chunk_{doc_type.value}_{key}",
        page_id=f"page_{doc_type.value}_{key}",
        source_id="src_test",
        doc_id=f"doc_{doc_type.value}_{key}",
        candidate_id=candidate_id,
        doc_type=doc_type,
        page=1,
        content="evidence",
        token_start=0,
        token_end=1,
        token_count=1,
        publisher="Publisher",
        title="Title",
        url=None,
        published_at=None,
        local_path=Path("test.pdf"),
        sha256="a" * 64,
    )


def test_candidate_filter_includes_matching_and_common_documents() -> None:
    assert chunk_matches_filters(
        make_chunk(DocumentType.TECH, "company_a"), candidate_id="company_a"
    )
    assert not chunk_matches_filters(
        make_chunk(DocumentType.TECH, "company_b"), candidate_id="company_a"
    )
    assert chunk_matches_filters(
        make_chunk(DocumentType.PARENT, None), candidate_id="company_a"
    )
    assert chunk_matches_filters(
        make_chunk(DocumentType.MARKET, None), candidate_id="company_a"
    )


def test_common_risk_document_is_included_for_every_candidate() -> None:
    assert chunk_matches_filters(
        make_chunk(DocumentType.RISK, None), candidate_id="company_a"
    )


def test_doc_type_filter_is_applied_before_common_document_rule() -> None:
    assert not chunk_matches_filters(
        make_chunk(DocumentType.PARENT, None),
        candidate_id="company_a",
        doc_types=[DocumentType.TECH],
    )
    assert chunk_matches_filters(
        make_chunk(DocumentType.TECH, "company_a"),
        candidate_id="company_a",
        doc_types=[DocumentType.TECH],
    )


def test_no_candidate_filter_allows_all_candidates() -> None:
    assert chunk_matches_filters(make_chunk(DocumentType.RISK, "company_b"))
