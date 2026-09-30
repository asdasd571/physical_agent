from __future__ import annotations

from typing import Any

from schemas import ControlState, GraphState


def select_candidate_node(state: GraphState) -> dict[str, Any]:
    current_index = state["candidate_index"]
    candidates = state["candidates"]

    if current_index < -1:
        raise ValueError("candidate_index must be -1 or greater")

    next_index = current_index + 1

    if next_index >= len(candidates):
        raise IndexError("no remaining candidate")

    return {
        "candidate_index": next_index,
        "current_candidate": candidates[next_index],
        "company_profile": None,
        "eligibility": None,
        "tech_analysis": None,
        "market_analysis": None,
        "competitor_analysis": None,
        "synergy_analysis": None,
        "evidence_review": None,
        "control": ControlState(),
        "evaluation": None,
        "decision": None,
    }
