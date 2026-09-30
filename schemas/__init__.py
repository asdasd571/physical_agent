"""Public data contracts shared across RAG, Agents, Graph, and reporting."""

INTERFACE_VERSION = "1.0.0"

from .analysis import AgentNodeUpdate, AnalysisResult, Candidate
from .evaluation import (
    Decision,
    DecisionStatus,
    EligibilityResult,
    EligibilityStatus,
    EvaluationRecord,
    EvidenceReview,
    GateResult,
    RepairTarget,
)
from .evidence import (
    EvidenceStatus,
    IndicatorEvidence,
    QueryAttempt,
    QueryStatus,
    SourceKind,
    SourceRecord,
)
from .state import ControlState, GraphState, ReportResult, RunConfig

__all__ = [
    "AgentNodeUpdate",
    "AnalysisResult",
    "Candidate",
    "ControlState",
    "Decision",
    "DecisionStatus",
    "EligibilityResult",
    "EligibilityStatus",
    "EvaluationRecord",
    "EvidenceReview",
    "EvidenceStatus",
    "GateResult",
    "GraphState",
    "IndicatorEvidence",
    "INTERFACE_VERSION",
    "QueryAttempt",
    "QueryStatus",
    "RepairTarget",
    "ReportResult",
    "RunConfig",
    "SourceKind",
    "SourceRecord",
]
