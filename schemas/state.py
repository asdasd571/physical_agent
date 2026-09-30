"""LangGraph State contract. Routers read it; Nodes return partial updates."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, NotRequired, TypedDict

from pydantic import Field

from graph.reducers import merge_errors, merge_evaluations, merge_sources

from .analysis import AnalysisResult, Candidate
from .base import SchemaModel
from .evaluation import Decision, EligibilityResult, EvaluationRecord, EvidenceReview
from .evidence import SourceRecord


class RunConfig(SchemaModel):
    run_id: str = Field(min_length=1)
    evaluation_date: date
    rule_version: str = Field(min_length=1)
    embedding_model: str = "BAAI/bge-m3"
    document_version: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)


class ControlState(SchemaModel):
    retry_count: int = Field(default=0, ge=0, le=1)
    repaired_indicator_ids: list[str] = Field(default_factory=list)


class ReportResult(SchemaModel):
    output_path: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)


class GraphState(TypedDict):
    run: RunConfig
    candidates: list[Candidate]
    candidate_index: int
    current_candidate: Candidate | None
    company_profile: AnalysisResult | None
    eligibility: EligibilityResult | None
    tech_analysis: AnalysisResult | None
    market_analysis: AnalysisResult | None
    competitor_analysis: AnalysisResult | None
    synergy_analysis: AnalysisResult | None
    evidence_review: EvidenceReview | None
    control: ControlState
    evaluation: EvaluationRecord | None
    decision: Decision | None
    evaluations: Annotated[list[EvaluationRecord], merge_evaluations]
    sources: Annotated[list[SourceRecord], merge_sources]
    report: ReportResult | None
    errors: NotRequired[Annotated[list[str], merge_errors]]
