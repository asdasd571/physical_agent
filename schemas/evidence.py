"""Evidence and source models shared by collection, review, and reporting."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .base import SchemaModel


class EvidenceStatus(StrEnum):
    THIRD_PARTY_VERIFIED = "THIRD_PARTY_VERIFIED"
    COMPANY_CLAIM = "COMPANY_CLAIM"
    NO_EVIDENCE = "NO_EVIDENCE"


class QueryStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NO_DATA = "NO_DATA"
    ACCESS_FAILED = "ACCESS_FAILED"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    INVALID_DENOMINATOR = "INVALID_DENOMINATOR"


class SourceKind(StrEnum):
    PDF = "PDF"
    WEB = "WEB"
    API = "API"
    MANUAL = "MANUAL"


class QueryAttempt(SchemaModel):
    query: str = Field(min_length=1)
    status: QueryStatus
    attempted_at: datetime
    result_count: int | None = Field(default=None, ge=0)
    note: str | None = None


class IndicatorEvidence(SchemaModel):
    """Unscored raw value and its provenance for one investment indicator."""

    id: str = Field(min_length=1)
    raw_value: Any = None
    unit: str | None = None
    period: str | None = None
    as_of: date | None = None
    condition: dict[str, Any] = Field(default_factory=dict)
    evidence_status: EvidenceStatus
    source_ids: list[str] = Field(default_factory=list)
    collected_by: str = Field(min_length=1)
    query_status: QueryStatus
    missing_reason: str | None = None

    @model_validator(mode="after")
    def validate_missing_value(self) -> "IndicatorEvidence":
        if self.query_status == QueryStatus.SUCCESS and self.raw_value is None:
            raise ValueError("SUCCESS requires raw_value; use 0 for a verified zero result")
        if self.query_status != QueryStatus.SUCCESS and self.missing_reason is None:
            raise ValueError("non-success query_status requires missing_reason")
        if self.evidence_status == EvidenceStatus.NO_EVIDENCE and self.raw_value is not None:
            raise ValueError("NO_EVIDENCE requires raw_value=None")
        return self


class SourceRecord(SchemaModel):
    """Canonical source referenced by Agent results and the final report."""

    source_id: str = Field(min_length=1)
    kind: SourceKind
    publisher: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str | None = None
    published_at: date | None = None
    collected_at: datetime
    local_path: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    doc_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    response_id: str | None = None
    evidence_excerpt: str | None = None

    @model_validator(mode="after")
    def validate_locator(self) -> "SourceRecord":
        if self.kind == SourceKind.PDF:
            missing = [
                name
                for name, value in {
                    "local_path": self.local_path,
                    "sha256": self.sha256,
                    "doc_id": self.doc_id,
                    "page": self.page,
                }.items()
                if value is None
            ]
            if missing:
                raise ValueError(f"PDF source requires: {', '.join(missing)}")
        if self.kind == SourceKind.API and self.response_id is None:
            raise ValueError("API source requires response_id")
        return self
