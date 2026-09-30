"""Read and validate the document manifest before any PDF is loaded."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, Iterable

from .models import DocumentType, ManifestEntry


MAX_TOTAL_PAGES: Final[int] = 200
PAGE_BUDGET_GUIDE: Final[dict[DocumentType, int]] = {
    DocumentType.TECH: 70,
    DocumentType.PARENT: 40,
    DocumentType.MARKET: 40,
    DocumentType.RISK: 30,
}
RESERVE_PAGE_GUIDE: Final[int] = 20

REQUIRED_COLUMNS: Final[set[str]] = {
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
}


class ManifestError(ValueError):
    """Raised when manifest data is missing, inconsistent, or over budget."""


@dataclass(frozen=True, slots=True)
class Manifest:
    path: Path
    entries: tuple[ManifestEntry, ...]

    @property
    def total_used_pages(self) -> int:
        return sum(entry.used_pages for entry in self.entries)

    @property
    def pages_by_type(self) -> dict[DocumentType, int]:
        return {
            doc_type: sum(
                entry.used_pages for entry in self.entries if entry.doc_type == doc_type
            )
            for doc_type in DocumentType
        }

    def validate_page_budget(self, max_pages: int = MAX_TOTAL_PAGES) -> None:
        if self.total_used_pages > max_pages:
            raise ManifestError(
                f"manifest page budget exceeded: {self.total_used_pages}/{max_pages}"
            )

    def resolve_local_path(self, entry: ManifestEntry) -> Path:
        path = entry.local_path
        if not path.is_absolute():
            path = self.path.parent / path
        return path.resolve()


def _optional(value: str | None) -> str | None:
    stripped = value.strip() if value else ""
    return stripped or None


def _parse_date(value: str | None, *, doc_id: str) -> date | None:
    raw = _optional(value)
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ManifestError(
            f"published_at must use YYYY-MM-DD for {doc_id}: {raw!r}"
        ) from exc


def _parse_positive_int(value: str | None, field: str, *, doc_id: str) -> int:
    try:
        parsed = int(value or "")
    except ValueError as exc:
        raise ManifestError(f"{field} must be an integer for {doc_id}") from exc
    if parsed <= 0:
        raise ManifestError(f"{field} must be positive for {doc_id}")
    return parsed


def _build_entry(row: dict[str, str | None], row_number: int) -> ManifestEntry:
    doc_id = _optional(row.get("doc_id")) or f"row {row_number}"
    try:
        doc_type = DocumentType((_optional(row.get("doc_type")) or "").lower())
        return ManifestEntry(
            doc_id=doc_id,
            publisher=row.get("publisher") or "",
            published_at=_parse_date(row.get("published_at"), doc_id=doc_id),
            source_url=_optional(row.get("source_url")),
            sha256=row.get("sha256") or "",
            original_pages=_parse_positive_int(
                row.get("original_pages"), "original_pages", doc_id=doc_id
            ),
            used_pages=_parse_positive_int(
                row.get("used_pages"), "used_pages", doc_id=doc_id
            ),
            doc_type=doc_type,
            candidate_id=_optional(row.get("candidate_id")),
            local_path=Path(row.get("local_path") or ""),
            title=_optional(row.get("title")),
            page_ranges=_optional(row.get("page_ranges")),
        )
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"invalid manifest row {row_number} ({doc_id}): {exc}") from exc


def _reject_duplicates(entries: Iterable[ManifestEntry]) -> None:
    seen_doc_ids: set[str] = set()
    seen_sources: set[str] = set()
    for entry in entries:
        if entry.doc_id in seen_doc_ids:
            raise ManifestError(f"duplicate doc_id: {entry.doc_id}")
        if entry.source_id in seen_sources:
            raise ManifestError(
                f"duplicate source document: {entry.doc_id} ({entry.source_id})"
            )
        seen_doc_ids.add(entry.doc_id)
        seen_sources.add(entry.source_id)


def load_manifest(
    path: str | Path = "data/rag/manifest.csv",
    *,
    max_pages: int = MAX_TOTAL_PAGES,
) -> Manifest:
    """Load a CSV manifest and fail before indexing if it violates the design."""

    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.is_file():
        raise ManifestError(f"manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ManifestError(
                f"manifest is missing required columns: {', '.join(sorted(missing))}"
            )
        entries = tuple(_build_entry(row, number) for number, row in enumerate(reader, 2))

    _reject_duplicates(entries)
    manifest = Manifest(path=manifest_path, entries=entries)
    manifest.validate_page_budget(max_pages)
    return manifest
