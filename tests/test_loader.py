from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from rag.loader import PDFLoadError, parse_page_ranges
from rag.models import DocumentType, ManifestEntry


def test_parse_page_ranges_returns_original_pages() -> None:
    assert parse_page_ranges("1-3;8,10", 10) == (1, 2, 3, 8, 10)


def test_parse_page_ranges_rejects_out_of_bounds() -> None:
    with pytest.raises(PDFLoadError, match="outside PDF page count"):
        parse_page_ranges("11", 10)


def test_source_id_is_deterministic() -> None:
    values = dict(
        doc_id="doc-a",
        publisher="publisher",
        published_at=date(2026, 9, 30),
        source_url="https://example.com/a.pdf",
        sha256="a" * 64,
        original_pages=10,
        used_pages=3,
        doc_type=DocumentType.TECH,
        candidate_id="company-a",
        local_path=Path("documents/a.pdf"),
        page_ranges="1-3",
    )
    assert ManifestEntry(**values).source_id == ManifestEntry(**values).source_id
