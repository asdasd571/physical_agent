from __future__ import annotations

from typing import Any

from schemas import (
    Decision,
    DecisionStatus,
    EligibilityStatus,
    EvaluationRecord,
    GateResult,
    GraphState,
)


def skip_node(state: GraphState) -> dict[str, Any]:
    candidate = state["current_candidate"]
    eligibility = state["eligibility"]

    if candidate is None:
        raise ValueError("current_candidate is required")

    if eligibility is None:
        raise ValueError("eligibility is required")

    if eligibility.status == EligibilityStatus.PASS:
        raise ValueError("PASS candidate cannot be skipped")

    decision = Decision(
        status=DecisionStatus.HOLD,
        reasons=list(eligibility.reasons),
    )
    gate = GateResult(
        passed=False,
        reasons=list(eligibility.reasons),
        source_ids=list(eligibility.source_ids),
        unknown_items=list(eligibility.unknown_items),
    )
    evaluation = EvaluationRecord(
        candidate_id=candidate.candidate_id,
        country=candidate.country,
        primary_segment=candidate.primary_segment,
        rule_version=state["run"].rule_version,
        gates={"G1": gate},
        total_score=None,
        decision=decision,
        unknown_items=list(eligibility.unknown_items),
        due_diligence_items=list(eligibility.unknown_items),
        metadata={"eligibility_status": eligibility.status.value},
    )

    return {
        "evaluation": evaluation,
        "decision": decision,
    }
