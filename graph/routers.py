from __future__ import annotations

from typing import Literal

from schemas import EligibilityStatus, GraphState


def route_after_eligibility(
    state: GraphState,
) -> Literal["tech", "skip"]:
    eligibility = state["eligibility"]

    if eligibility is None:
        raise ValueError("적격성 결과가 없습니다")

    if eligibility.status == EligibilityStatus.PASS:
        return "tech"

    return "skip"


def route_after_review(
    state: GraphState,
) -> Literal["repair", "judge"]:
    review = state["evidence_review"]

    if review is None:
        raise ValueError("근거 검증 결과가 없습니다")

    if review.repair_required and state["control"].retry_count < 1:
        return "repair"

    return "judge"


def route_after_archive(
    state: GraphState,
) -> Literal["select_candidate", "report"]:
    completed_count = len(state["evaluations"])
    candidate_count = len(state["candidates"])

    if completed_count > candidate_count:
        raise ValueError("완료된 평가 수가 전체 후보 수보다 많습니다")

    if completed_count < candidate_count:
        return "select_candidate"

    return "report"
