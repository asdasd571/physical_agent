from __future__ import annotations

from typing import Literal

from schemas import EligibilityStatus, GraphState


def route_after_eligibility(
    state: GraphState,
) -> Literal["tech", "skip"]:
    eligibility = state["eligibility"]

    if eligibility is None:
        raise ValueError("eligibility is required")

    if eligibility.status == EligibilityStatus.PASS:
        return "tech"

    return "skip"


def route_after_review(
    state: GraphState,
) -> Literal["repair", "judge"]:
    review = state["evidence_review"]

    if review is None:
        raise ValueError("evidence_review is required")

    if review.repair_required and state["control"].retry_count < 1:
        return "repair"

    return "judge"


def route_after_archive(
    state: GraphState,
) -> Literal["select_candidate", "report"]:
    completed_count = len(state["evaluations"])
    candidate_count = len(state["candidates"])

    if completed_count > candidate_count:
        raise ValueError("evaluations cannot exceed candidates")

    if completed_count < candidate_count:
        return "select_candidate"

    return "report"
