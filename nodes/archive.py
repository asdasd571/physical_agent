from __future__ import annotations

from typing import Any

from schemas import GraphState


def archive_node(state: GraphState) -> dict[str, Any]:
    candidate = state["current_candidate"]
    evaluation = state["evaluation"]
    decision = state["decision"]

    if candidate is None:
        raise ValueError("현재 평가 후보가 없습니다")

    if evaluation is None:
        raise ValueError("평가 결과가 없습니다")

    if decision is None:
        raise ValueError("투자 판정 결과가 없습니다")

    if evaluation.candidate_id != candidate.candidate_id:
        raise ValueError("평가 결과의 후보 ID가 현재 후보와 일치하지 않습니다")

    if evaluation.decision != decision:
        raise ValueError("평가 결과의 판정과 State 판정이 일치하지 않습니다")

    return {"evaluations": [evaluation]}
