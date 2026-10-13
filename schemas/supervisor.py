"""Supervisor의 제어 상태와 보고서 품질 평가 계약이다."""

from typing import Literal

from pydantic import Field

from .analysis import AnalysisResult
from .base import SchemaModel
from .state import GraphState


Owner = Literal["discover", "tech", "market", "competitor", "synergy"]
Route = Literal["discover", "tech", "market", "competitor", "synergy", "judge", "skip"]
Perspective = Literal["technology", "market", "stakeholders", "application"]


class SupervisorPolicy(SchemaModel):
    allow_stage_benchmarks: bool = False
    max_attempts_per_agent: int = Field(default=2, ge=1, le=3)
    max_dispatches_per_candidate: int = Field(default=15, ge=5, le=30)
    max_report_revisions: int = Field(default=2, ge=1, le=3)
    max_sources: int = Field(default=300, ge=1, le=1000)


class Assignment(SchemaModel):
    owner: Owner
    candidate_id: str
    reason: str
    indicator_ids: list[str] = Field(default_factory=list)
    repair: bool = False
    # 다른 담당자의 결과는 Supervisor가 선택한 경우에만 전달한다.
    tech_context: AnalysisResult | None = None


class RoutingDecision(SchemaModel):
    sequence: int
    candidate_id: str
    route: Route
    reason: str
    deficits: dict[str, int] = Field(default_factory=dict)
    evidence_sufficient: bool = False


class SupervisorControl(SchemaModel):
    next_node: Route = "discover"
    attempts: dict[str, int] = Field(default_factory=dict)
    dispatch_count: int = 0
    assignment: Assignment | None = None
    evidence_sufficient: bool = False
    termination_reason: str | None = None
    decisions: list[RoutingDecision] = Field(default_factory=list)
    failures: dict[str, str] = Field(default_factory=dict)


class ReportSection(SchemaModel):
    candidate_id: str
    perspective: Perspective
    title: str
    text: str
    source_ids: list[str] = Field(default_factory=list)
    indicator_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportDraft(SchemaModel):
    run_id: str
    revision: int
    summary: str
    sections: list[ReportSection]
    reference_ids: list[str]


class QualityCriterion(SchemaModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


class ReportQuality(SchemaModel):
    revision: int
    passed: bool
    mode: Literal["rules"] = "rules"
    groundedness: QualityCriterion
    neutrality: QualityCriterion
    bias_control: QualityCriterion
    perspective_coverage: QualityCriterion
    artifact: QualityCriterion


class SupervisorGraphState(GraphState):
    policy: SupervisorPolicy
    supervisor: SupervisorControl
    # 후보 수(최대 3개)와 호출 상한으로 크기가 제한된다.
    routing_history: dict[str, SupervisorControl]
    draft: ReportDraft | None
    quality: ReportQuality | None
    quality_history: list[ReportQuality]
    report_revision: int
    completion_status: Literal["running", "passed", "quality_failed"]
