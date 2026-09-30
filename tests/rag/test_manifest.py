from __future__ import annotations

import csv
from pathlib import Path

import pytest

from rag.manifest import ManifestError, load_manifest


FIELDS = [
    "doc_id",
    "publisher",
    "published_at",
    "source_url",
    "sha256",
    "original_pages",
    "used_pages",
    "doc_type",
    "candidate_id",
    "local_path",
    "title",
    "page_ranges",
]


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "doc_id": "doc-a",
        "publisher": "publisher",
        "published_at": "2026-09-30",
        "source_url": "https://example.com/a.pdf",
        "sha256": "a" * 64,
        "original_pages": 10,
        "used_pages": 10,
        "doc_type": "tech",
        "candidate_id": "company-a",
        "local_path": "documents/a.pdf",
        "title": "Document A",
        "page_ranges": "",
    }
    base.update(overrides)
    return base


def test_load_manifest_normalizes_common_candidate(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    write_manifest(path, [row(doc_type="market", candidate_id="COMMON")])

    manifest = load_manifest(path)

    assert manifest.entries[0].candidate_id is None
    assert manifest.total_used_pages == 10


def test_candidate_document_can_be_common(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    write_manifest(path, [row(candidate_id="")])

    manifest = load_manifest(path)

    assert manifest.entries[0].candidate_id is None


def test_total_page_budget_is_hard_limit(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    write_manifest(
        path,
        [
            row(doc_id="a", used_pages=101, original_pages=101),
            row(
                doc_id="b",
                sha256="b" * 64,
                used_pages=100,
                original_pages=100,
            ),
        ],
    )

    with pytest.raises(ManifestError, match="201/200"):
        load_manifest(path)
