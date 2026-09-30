"""Common inputs and outputs for the four analysis Agent groups."""

from __future__ import annotations

from datetime import date
from typing import NotRequired, TypedDict

from pydantic import Field, model_validator

from .base import SchemaModel
from .evidence import IndicatorEvidence, QueryAttempt, SourceRecord


class Candidate(SchemaModel):
    candidate_id: str = Field(min_length=1)
    legal_name: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=2)
    legal_id: str = Field(min_length=1)
    founded_at: date
    primary_segment: str = Field(min_length=1)
    latest_round: str = Field(min_length=1)
    listing_sources: list[str] = Field(min_length=1)
    registry_sources: list[str] = Field(min_length=1)
    evidence_urls: list[str] = Field(default_factory=list)


class AnalysisResult(SchemaModel):
    candidate_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    indicators: list[IndicatorEvidence] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    query_attempts: list[QueryAttempt] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_ids(self) -> "AnalysisResult":
        indicator_sources = {
            source_id
            for indicator in self.indicators
            for source_id in indicator.source_ids
        }
        missing = indicator_sources - set(self.source_ids)
        if missing:
            raise ValueError(
                "indicator source_ids must be included in AnalysisResult.source_ids: "
                + ", ".join(sorted(missing))
            )
        return self


class AgentNodeUpdate(TypedDict, total=False):
    """Permitted partial State update returned by analysis Nodes."""

    company_profile: NotRequired[AnalysisResult]
    tech_analysis: NotRequired[AnalysisResult]
    market_analysis: NotRequired[AnalysisResult]
    competitor_analysis: NotRequired[AnalysisResult]
    synergy_analysis: NotRequired[AnalysisResult]
    sources: NotRequired[list[SourceRecord]]
