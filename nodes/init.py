from __future__ import annotations

from typing import Any

from schemas import ControlState, GraphState


def init_node(state: GraphState) -> dict[str, Any]:
    candidates = state["candidates"]

    if not 2 <= len(candidates) <= 3:
        raise ValueError("candidates must contain 2 or 3 items")

    candidate_ids = [candidate.candidate_id for candidate in candidates]

    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_id must be unique")

    return {
        "candidate_index": -1,
        "current_candidate": None,
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
        "evaluations": [],
        "sources": [],
        "report": None,
        "errors": [],
    }
