"""Eligibility, review, scoring, and archived evaluation result schemas."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .base import SchemaModel
from .evidence import IndicatorEvidence


class EligibilityStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class DecisionStatus(StrEnum):
    INVEST = "INVEST"
    HOLD = "HOLD"


class EligibilityResult(SchemaModel):
    status: EligibilityStatus
    reasons: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    unknown_items: list[str] = Field(default_factory=list)


class GateResult(SchemaModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    unknown_items: list[str] = Field(default_factory=list)


class RepairTarget(SchemaModel):
    owner: str = Field(min_length=1)
    indicator_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)


class EvidenceReview(SchemaModel):
    candidate_id: str = Field(min_length=1)
    passed: bool
    repair_required: bool
    repair_targets: list[RepairTarget] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_repair_targets(self) -> "EvidenceReview":
        if self.repair_required and not self.repair_targets:
            raise ValueError("repair_required=True requires repair_targets")
        return self


class Decision(SchemaModel):
    status: DecisionStatus
    reasons: list[str] = Field(min_length=1)


class EvaluationRecord(SchemaModel):
    candidate_id: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=2)
    primary_segment: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    indicators: list[IndicatorEvidence] = Field(default_factory=list)
    indicator_scores: dict[str, int] = Field(default_factory=dict)
    category_scores: dict[str, Decimal] = Field(default_factory=dict)
    gates: dict[str, GateResult] = Field(default_factory=dict)
    total_score: Decimal | None = Field(default=None, ge=0, le=100)
    decision: Decision
    evidence_coverage: Decimal | None = Field(default=None, ge=0, le=1)
    unknown_items: list[str] = Field(default_factory=list)
    due_diligence_items: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_skipped_score(self) -> "EvaluationRecord":
        eligibility = self.gates.get("G1")
        if eligibility is not None and not eligibility.passed and self.total_score is not None:
            raise ValueError("G1-failed or unknown evaluation must have total_score=None")
        return self
