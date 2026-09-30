from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import pytest

from agents.competitor import competitor_node
from agents.discover import discover_node
from agents.market import market_node
from schemas import (
    Candidate,
    ControlState,
    GraphState,
    QueryStatus,
    RunConfig,
)


@pytest.fixture
def all_candidates() -> list[Candidate]:
    candidates_file = Path(__file__).resolve().parent.parent / "data" / "candidates.json"
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Candidate.model_validate(item) for item in data]


def _build_initial_state(candidate: Candidate, candidates: list[Candidate]) -> GraphState:
    return {
        "run": RunConfig(
            run_id="run_pipeline_test",
            evaluation_date=date(2026, 9, 30),
            rule_version="1.0.0",
            document_version="1.0.0",
        ),
        "candidates": candidates,
        "candidate_index": candidates.index(candidate),
        "current_candidate": candidate,
        "company_profile": None,
        "eligibility": None,
        "tech_analysis": None,
        "market_analysis": None,
        "competitor_analysis": None,
        "synergy_analysis": None,
        "evidence_review": None,
        "control": None,
        "evaluation": None,
        "decision": None,
        "evaluations": [],
        "sources": [],
        "report": None,
    }


def _apply_update(state: GraphState, update: dict) -> None:
    """Simulate LangGraph state update semantics: merge fields, append sources."""
    for key, value in update.items():
        if key == "sources":
            existing_ids = {s.source_id for s in state.get("sources", [])}
            new_sources = [s for s in value if s.source_id not in existing_ids]
            state["sources"].extend(new_sources)
        else:
            state[key] = value


@pytest.mark.parametrize("cand_idx", [0, 1])
def test_full_pipeline_discover_market_competitor(all_candidates: list[Candidate], cand_idx: int) -> None:
    candidate = all_candidates[cand_idx]
    state = _build_initial_state(candidate, all_candidates)

    # 1. Execute discover_node
    discover_update = discover_node(state)
    assert "company_profile" in discover_update
    assert "sources" in discover_update
    _apply_update(state, discover_update)

    profile = state["company_profile"]
    assert profile.candidate_id == candidate.candidate_id
    discover_indicator_ids = {ind.id for ind in profile.indicators}
    expected_discover_ids = {"G1", "T1", "R1", "R3", "F1", "F2", "F3"}
    assert expected_discover_ids.issubset(discover_indicator_ids)

    # 2. Execute market_node
    market_update = market_node(state)
    assert "market_analysis" in market_update
    _apply_update(state, market_update)

    market_analysis = state["market_analysis"]
    assert market_analysis.candidate_id == candidate.candidate_id
    assert any(ind.id == "P1" for ind in market_analysis.indicators)
    p1 = next(ind for ind in market_analysis.indicators if ind.id == "P1")
    assert p1.query_status == QueryStatus.SUCCESS
    assert p1.raw_value["cagr_percent"] > 0

    # 3. Execute competitor_node
    competitor_update = competitor_node(state)
    assert "competitor_analysis" in competitor_update
    _apply_update(state, competitor_update)

    competitor_analysis = state["competitor_analysis"]
    assert competitor_analysis.candidate_id == candidate.candidate_id
    assert any(ind.id == "M1" for ind in competitor_analysis.indicators)
    m1 = next(ind for ind in competitor_analysis.indicators if ind.id == "M1")
    assert m1.query_status == QueryStatus.SUCCESS
    assert m1.raw_value["unique_priority_families"] >= 3

    # Benchmark comparison products exist
    assert "comparison_products" in state
    assert len(state["comparison_products"]) >= 2

    # 4. Source linkage integrity check:
    # All indicator source_ids and comparison_product source_ids must exist in accumulated sources
    accumulated_source_ids = {s.source_id for s in state["sources"]}
    all_tested_indicators = profile.indicators + market_analysis.indicators + competitor_analysis.indicators

    for ind in all_tested_indicators:
        for sid in ind.source_ids:
            assert sid in accumulated_source_ids, f"Indicator {ind.id} references missing source: {sid}"

    for cp in state["comparison_products"]:
        cp_sids = cp.get("attributes", {}).get("source_ids", [])
        for sid in cp_sids:
            assert sid in accumulated_source_ids, f"Comparison product {cp.get('company')} references missing source: {sid}"


def test_pipeline_repair_loop_simulation(all_candidates: list[Candidate]) -> None:
    candidate = all_candidates[0]
    state = _build_initial_state(candidate, all_candidates)

    # Initial run
    _apply_update(state, discover_node(state))
    _apply_update(state, market_node(state))
    _apply_update(state, competitor_node(state))

    # Simulate Judge requesting repair for F1 and M1 via ControlState
    state["control"] = ControlState(
        retry_count=1,
        repaired_indicator_ids=["F1", "M1"],
    )

    # Re-run discover with repair target
    discover_repaired = discover_node(state)
    _apply_update(state, discover_repaired)
    repaired_f1 = next(ind for ind in state["company_profile"].indicators if ind.id == "F1")
    assert repaired_f1.query_status == QueryStatus.SUCCESS

    # Re-run competitor with repair target
    competitor_repaired = competitor_node(state)
    _apply_update(state, competitor_repaired)
    repaired_m1 = next(ind for ind in state["competitor_analysis"].indicators if ind.id == "M1")
    assert repaired_m1.query_status == QueryStatus.SUCCESS


def test_pipeline_repair_with_evidence_review_dict(all_candidates: list[Candidate]) -> None:
    """Test compatibility when control is passed as a dict with repair_targets from EvidenceReview."""
    candidate = all_candidates[1]
    state = _build_initial_state(candidate, all_candidates)

    # Initial run
    _apply_update(state, discover_node(state))
    _apply_update(state, market_node(state))
    _apply_update(state, competitor_node(state))

    # Control specified as dict with repair_targets
    state["control"] = {
        "retry_count": 1,
        "repair_targets": [
            {"owner": "discover", "indicator_ids": ["R1"]},
            {"owner": "market", "indicator_ids": ["P1"]},
            {"owner": "competitor", "indicator_ids": ["M1"]},
        ],
    }

    # All nodes should safely parse repair_targets without error
    _apply_update(state, discover_node(state))
    _apply_update(state, market_node(state))
    _apply_update(state, competitor_node(state))

    assert state["company_profile"] is not None
    assert state["market_analysis"] is not None
    assert state["competitor_analysis"] is not None


def test_full_pipeline_figure_ai_global_vla(all_candidates: list[Candidate]) -> None:
    """Verify Figure AI as a global VLA candidate: Series C, VLA NO_DATA market rule, USPTO patents."""
    figure_candidate = next((c for c in all_candidates if c.candidate_id == "figure_ai"), None)
    assert figure_candidate is not None, "figure_ai must exist in candidates.json"
    assert figure_candidate.country == "US"
    assert figure_candidate.primary_segment == "vla"
    assert figure_candidate.latest_round == "Series C"

    state = _build_initial_state(figure_candidate, all_candidates)

    # 1. Discover node
    discover_update = discover_node(state)
    _apply_update(state, discover_update)
    profile = state["company_profile"]
    assert profile.candidate_id == "figure_ai"

    g1 = next(ind for ind in profile.indicators if ind.id == "G1")
    assert g1.raw_value["latest_round"]["value"] == "Series C"
    # COMPANY_CLAIM reflects high self-reported bias (Section 5-2)
    assert g1.evidence_status.value in ("COMPANY_CLAIM", "SELF_REPORTED")

    r1 = next(ind for ind in profile.indicators if ind.id == "R1")
    assert r1.raw_value["cumulative_amount"] > 1_000_000_000_000  # > 1 trillion KRW ($1B+)

    # 2. Market node: VLA segment must result in NO_DATA according to Design Spec 5-8
    market_update = market_node(state)
    _apply_update(state, market_update)
    market_analysis = state["market_analysis"]
    p1 = next(ind for ind in market_analysis.indicators if ind.id == "P1")
    assert p1.query_status == QueryStatus.NO_DATA
    assert p1.raw_value is None
    assert "VLA" in (p1.missing_reason or "")

    # 3. Competitor node: USPTO registered patents and global benchmarks
    competitor_update = competitor_node(state)
    _apply_update(state, competitor_update)
    competitor_analysis = state["competitor_analysis"]
    m1 = next(ind for ind in competitor_analysis.indicators if ind.id == "M1")
    assert m1.query_status == QueryStatus.SUCCESS
    assert m1.raw_value["valid_registered_patents"] == 2
    assert m1.raw_value["unique_priority_families"] == 2

    # Global benchmarks: Tesla, Boston Dynamics
    assert "comparison_products" in state
    comp_companies = {cp["company"] for cp in state["comparison_products"]}
    assert "Tesla" in comp_companies
    assert "Boston Dynamics" in comp_companies

    # Source linkage integrity
    accumulated_source_ids = {s.source_id for s in state["sources"]}
    all_tested_indicators = profile.indicators + market_analysis.indicators + competitor_analysis.indicators

    for ind in all_tested_indicators:
        for sid in ind.source_ids:
            assert sid in accumulated_source_ids, f"Indicator {ind.id} references missing source: {sid}"

