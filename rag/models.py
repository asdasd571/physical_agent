"""Data models shared by the manifest, loader, and later retrieval steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
import hashlib
import json
from pathlib import Path
from typing import Any, Final


COMMON_CANDIDATE_ID: Final[str] = "COMMON"


class DocumentType(StrEnum):
    """Document categories defined by the RAG design."""

    TECH = "tech"
    PARENT = "parent"
    MARKET = "market"
    RISK = "risk"

    @property
    def is_common(self) -> bool:
        """Whether documents of this type are shared by every candidate."""

        return self in {DocumentType.PARENT, DocumentType.MARKET}


def stable_id(namespace: str, *parts: object, length: int = 24) -> str:
    """Return a deterministic, readable identifier from canonical input values."""

    normalized = "\x1f".join(str(part).strip() for part in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]
    return f"{namespace}_{digest}"


def _normalize_candidate_id(
    candidate_id: str | None,
    doc_type: DocumentType,
) -> str | None:
    value = candidate_id.strip() if candidate_id else None
    if value and value.upper() == COMMON_CANDIDATE_ID:
        value = None
    if doc_type.is_common:
        if value is not None:
            raise ValueError(
                f"{doc_type.value} documents are common and must not have candidate_id"
            )
        return None
    if value is None:
        raise ValueError(f"{doc_type.value} documents require candidate_id")
    return value


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One source document registered in ``data/manifest.csv``.

    ``page_ranges`` is optional. When present, it selects 1-based pages from the
    original PDF (for example ``1-3;8;11-12``). This preserves original page
    numbers without creating a renumbered excerpt PDF.
    """

    doc_id: str
    publisher: str
    published_at: date | None
    source_url: str | None
    sha256: str
    original_pages: int
    used_pages: int
    doc_type: DocumentType
    candidate_id: str | None
    local_path: Path
    title: str | None = None
    page_ranges: str | None = None
    source_id: str = field(init=False)

    def __post_init__(self) -> None:
        doc_id = self.doc_id.strip()
        publisher = self.publisher.strip()
        sha256 = self.sha256.strip().lower()
        local_path = Path(self.local_path).expanduser()
        title = self.title.strip() if self.title else doc_id
        page_ranges = self.page_ranges.strip() if self.page_ranges else None

        if not doc_id:
            raise ValueError("doc_id must not be empty")
        if not publisher:
            raise ValueError(f"publisher must not be empty for {doc_id}")
        if str(local_path) in {"", "."}:
            raise ValueError(f"local_path must not be empty for {doc_id}")
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError(f"sha256 must be a 64-character hex digest for {doc_id}")
        if self.original_pages <= 0:
            raise ValueError(f"original_pages must be positive for {doc_id}")
        if not 0 < self.used_pages <= self.original_pages:
            raise ValueError(
                f"used_pages must be between 1 and original_pages for {doc_id}"
            )

        candidate_id = _normalize_candidate_id(self.candidate_id, self.doc_type)
        object.__setattr__(self, "doc_id", doc_id)
        object.__setattr__(self, "publisher", publisher)
        object.__setattr__(self, "sha256", sha256)
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "local_path", local_path)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "page_ranges", page_ranges)
        object.__setattr__(self, "source_id", stable_id("src", sha256))


@dataclass(frozen=True, slots=True)
class DocumentPage:
    """Text extracted from one original PDF page."""

    source_id: str
    doc_id: str
    candidate_id: str | None
    doc_type: DocumentType
    publisher: str
    title: str
    url: str | None
    published_at: date | None
    local_path: Path
    sha256: str
    page: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    page_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.page <= 0:
            raise ValueError("page must be a 1-based original PDF page number")
        if not self.content.strip():
            raise ValueError(f"page content must not be empty: {self.doc_id} p.{self.page}")
        object.__setattr__(self, "content", self.content.strip())
        object.__setattr__(self, "page_id", stable_id("page", self.source_id, self.page))

    def to_metadata(self) -> dict[str, Any]:
        """Return JSON-serializable metadata for future vector/BM25 indexes."""

        return {
            "page_id": self.page_id,
            "source_id": self.source_id,
            "doc_id": self.doc_id,
            "candidate_id": self.candidate_id,
            "doc_type": self.doc_type.value,
            "publisher": self.publisher,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "local_path": str(self.local_path),
            "sha256": self.sha256,
            "page": self.page,
            **self.metadata,
        }


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Public result model returned by the future ``search_documents`` API."""

    chunk_id: str
    source_id: str
    doc_id: str
    candidate_id: str | None
    doc_type: DocumentType
    page: int
    content: str
    score: float
    publisher: str | None = None
    title: str | None = None
    url: str | None = None
    published_at: date | None = None
    local_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        """Return a serialization-friendly dictionary without requiring Pydantic."""

        payload = {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "doc_id": self.doc_id,
            "candidate_id": self.candidate_id,
            "doc_type": self.doc_type.value,
            "page": self.page,
            "content": self.content,
            "score": self.score,
            "publisher": self.publisher,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "local_path": str(self.local_path) if self.local_path else None,
            "metadata": self.metadata,
        }
        return payload

    def model_dump_json(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False)
