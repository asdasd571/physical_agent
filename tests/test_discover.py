from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import pytest

from agents.discover import (
    build_indicator,
    discover_candidate,
    discover_node,
    replace_indicators,
)
from schemas import (
    Candidate,
    EvidenceStatus,
    GraphState,
    IndicatorEvidence,
    QueryAttempt,
    QueryStatus,
    RunConfig,
    ControlState,
)


@pytest.fixture
def arobot_candidate() -> Candidate:
    candidates_file = Path(__file__).resolve().parent.parent / "data" / "candidates.json"
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Candidate.model_validate(data[0])


@pytest.fixture
def aidin_candidate() -> Candidate:
    candidates_file = Path(__file__).resolve().parent.parent / "data" / "candidates.json"
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Candidate.model_validate(data[1])


def test_discover_candidate_arobot_facts_and_units(arobot_candidate: Candidate) -> None:
    analysis, sources, handoff = discover_candidate(arobot_candidate)

    assert analysis.candidate_id == "arobot"
    assert len(analysis.indicators) == 7

    # Check summary contains strictly factual info without subjective adjectives
    assert "주식회사 에이로봇" in analysis.summary
    assert "854-88-00929" in analysis.summary
    assert "비상장" not in analysis.summary  # Eligibility check decides unlisted status
    assert "전문 기업" not in analysis.summary  # No subjective evaluation

    ind_map = {ind.id: ind for ind in analysis.indicators}

    # Units must match raw value definitions
    assert ind_map["T1"].unit == "명"
    assert ind_map["R1"].unit == "원"
    assert ind_map["R3"].unit == "명"
    assert ind_map["F1"].unit == "원"
    assert ind_map["F2"].unit == "원"
    assert ind_map["F3"].unit == "건"

    # Evidence status must reflect claim vs third party verification
    assert ind_map["T1"].evidence_status == EvidenceStatus.COMPANY_CLAIM
    assert ind_map["R1"].evidence_status == EvidenceStatus.COMPANY_CLAIM
    assert ind_map["R3"].evidence_status == EvidenceStatus.THIRD_PARTY_VERIFIED
    assert ind_map["F1"].evidence_status == EvidenceStatus.THIRD_PARTY_VERIFIED

    # Check source_ids are read from section, not hardcoded
    assert ind_map["F1"].source_ids == ["src_arobot_financials"]
    assert ind_map["F3"].source_ids == ["src_arobot_risk"]

    assert len(handoff) == 3
    assert handoff[0]["type"] == "founder_profile"


def test_build_indicator_status_variants() -> None:
    # 1. Missing section -> NO_DATA
    missing_ind = build_indicator("F1", None, default_unit="원")
    assert missing_ind.query_status == QueryStatus.NO_DATA
    assert missing_ind.evidence_status == EvidenceStatus.NO_EVIDENCE
    assert missing_ind.raw_value is None
    assert "근거 섹션이 evidence 파일에 없음" in (missing_ind.missing_reason or "")

    # 2. Denominator error
    denom_sec = {
        "raw_value": None,
        "query_status": "DENOMINATOR_ERROR",
        "missing_reason": "영업활동현금흐름이 0으로 런웨이 계산 불가",
        "evidence_status": "NO_DATA",
    }
    denom_ind = build_indicator("F1", denom_sec, default_unit="원")
    assert denom_ind.query_status == QueryStatus.INVALID_DENOMINATOR
    assert denom_ind.raw_value is None
    assert denom_ind.evidence_status == EvidenceStatus.NO_EVIDENCE

    # 3. Target mismatch
    mismatch_sec = {
        "raw_value": None,
        "query_status": "TARGET_MISMATCH",
        "missing_reason": "두 시점의 종업원 집계 범위가 달라 비교 불가",
        "evidence_status": "NO_DATA",
    }
    mismatch_ind = build_indicator("R3", mismatch_sec, default_unit="명")
    assert mismatch_ind.query_status == QueryStatus.TARGET_MISMATCH


def test_discover_candidate_fallback_when_file_missing() -> None:
    missing_candidate = Candidate(
        candidate_id="ghost_startup",
        legal_name="주식회사 유령로봇",
        country="KR",
        legal_id="000-00-00000",
        founded_at=date(2023, 1, 1),
        primary_segment="robot_hand",
        latest_round="Seed",
        listing_sources=["https://kind.krx.co.kr/"],
        registry_sources=["https://dart.fss.or.kr/"],
    )

    analysis, sources, handoff = discover_candidate(missing_candidate)
    assert len(analysis.indicators) == 7
    for ind in analysis.indicators:
        assert ind.query_status == QueryStatus.NO_DATA
        assert ind.raw_value is None
        assert ind.evidence_status == EvidenceStatus.NO_EVIDENCE


def test_discover_node_requires_current_candidate(arobot_candidate: Candidate) -> None:
    mock_state_no_candidate: GraphState = {
        "run": RunConfig(
            run_id="run_001",
            evaluation_date=date(2026, 9, 30),
            rule_version="1.0.0",
            document_version="1.0.0",
        ),
        "candidates": [arobot_candidate],
        "candidate_index": 0,
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
    }

    # Must raise ValueError, never silently substitute candidates[0]
    with pytest.raises(ValueError, match="current_candidate is required"):
        discover_node(mock_state_no_candidate)


def test_discover_node_repair_and_handoff(arobot_candidate: Candidate) -> None:
    # First full run
    initial_state: GraphState = {
        "run": RunConfig(
            run_id="run_001",
            evaluation_date=date(2026, 9, 30),
            rule_version="1.0.0",
            document_version="1.0.0",
        ),
        "candidates": [arobot_candidate],
        "candidate_index": 0,
        "current_candidate": arobot_candidate,
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
    }

    update = discover_node(initial_state)
    assert "company_profile" in update
    assert "handoff_urls" in update
    assert len(update["handoff_urls"]) == 3

    # Now simulate a repair request for F1 only
    repair_state: GraphState = {
        **initial_state,
        "company_profile": update["company_profile"],
        "control": ControlState(retry_count=1, repaired_indicator_ids=["F1"]),
    }

    repair_update = discover_node(repair_state)
    repaired_profile = repair_update["company_profile"]
    assert len(repaired_profile.indicators) == 7
    # Query attempts merged
    assert len(repaired_profile.query_attempts) == 2
