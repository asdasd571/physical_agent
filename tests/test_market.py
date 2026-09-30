from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import pytest

from agents.market import (
    calculate_cagr,
    map_segment_to_evidence_key,
    market_candidate,
    market_node,
)
from schemas import (
    Candidate,
    ControlState,
    EvidenceStatus,
    GraphState,
    QueryStatus,
    RunConfig,
)


@pytest.fixture
def arobot_parts_candidate() -> Candidate:
    candidates_file = Path(__file__).resolve().parent.parent / "data" / "candidates.json"
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Candidate.model_validate(data[0])  # primary_segment: robot_hand


@pytest.fixture
def aidin_sensor_candidate() -> Candidate:
    candidates_file = Path(__file__).resolve().parent.parent / "data" / "candidates.json"
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Candidate.model_validate(data[1])  # primary_segment: force_tactile_sensor


def test_calculate_cagr() -> None:
    # 2022: 1420 -> 2025: 1980
    cagr = calculate_cagr(1420, 1980, years=3)
    assert cagr == 11.72

    with pytest.raises(ValueError, match="positive"):
        calculate_cagr(0, 100, years=3)


def test_map_segment_rules() -> None:
    # Components -> robot_parts
    assert map_segment_to_evidence_key("robot_hand") == "robot_parts"
    assert map_segment_to_evidence_key("force_tactile_sensor") == "robot_parts"
    assert map_segment_to_evidence_key("gripper") == "robot_parts"

    # Complete robots -> manufacturing_robot
    assert map_segment_to_evidence_key("humanoid") == "manufacturing_robot"
    assert map_segment_to_evidence_key("manipulator") == "manufacturing_robot"

    # VLA software -> VLA_NO_DATA (no arbitrary mapping)
    assert map_segment_to_evidence_key("vla") == "VLA_NO_DATA"
    assert map_segment_to_evidence_key("vision_language_action") == "VLA_NO_DATA"

    # Unknown
    assert map_segment_to_evidence_key("drone_delivery") is None


def test_market_candidate_robot_parts(arobot_parts_candidate: Candidate) -> None:
    analysis, sources, ref_info = market_candidate(arobot_parts_candidate)

    assert analysis.candidate_id == "arobot"
    assert len(analysis.indicators) == 1

    p1 = analysis.indicators[0]
    assert p1.id == "P1"
    assert p1.query_status == QueryStatus.SUCCESS
    assert p1.evidence_status == EvidenceStatus.THIRD_PARTY_VERIFIED
    assert p1.unit == "원"
    assert p1.period == "2022-2025"

    assert p1.raw_value["stat_segment"] == "로봇 부품 및 부분품"
    assert p1.raw_value["start_year"] == 2022
    assert p1.raw_value["end_year"] == 2025
    assert p1.raw_value["cagr_percent"] == 11.72
    assert p1.raw_value["start_revenue"] == 1420000000000
    assert p1.raw_value["end_revenue"] == 1980000000000

    assert len(sources) == 1
    assert sources[0].source_id == "src_market_robot_parts_2025"
    assert p1.source_ids == ["src_market_robot_parts_2025"]
    assert len(ref_info) > 0


def test_market_candidate_sensor(aidin_sensor_candidate: Candidate) -> None:
    analysis, sources, _ = market_candidate(aidin_sensor_candidate)
    p1 = analysis.indicators[0]
    assert p1.query_status == QueryStatus.SUCCESS
    assert p1.raw_value["stat_segment"] == "로봇 부품 및 부분품"


def test_market_candidate_vla_strict_no_data() -> None:
    vla_candidate = Candidate(
        candidate_id="vla_mind",
        legal_name="주식회사 브이엘에이",
        country="KR",
        legal_id="123-45-67890",
        founded_at=date(2023, 1, 1),
        primary_segment="vla",
        latest_round="Seed",
        listing_sources=["https://kind.krx.co.kr/"],
        registry_sources=["https://dart.fss.or.kr/"],
    )

    analysis, sources, _ = market_candidate(vla_candidate)
    p1 = analysis.indicators[0]

    # Must be NO_DATA and raw_value is None, never arbitrarily assigned to manufacturing robot!
    assert p1.query_status == QueryStatus.NO_DATA
    assert p1.raw_value is None
    assert p1.evidence_status == EvidenceStatus.NO_EVIDENCE
    assert "임의 배정하지 않음" in (p1.missing_reason or "")
    assert len(sources) == 0


def test_market_candidate_target_mismatch() -> None:
    unknown_candidate = Candidate(
        candidate_id="service_bot",
        legal_name="주식회사 서빙로봇",
        country="KR",
        legal_id="123-45-67890",
        founded_at=date(2023, 1, 1),
        primary_segment="unmatched_service_sector",
        latest_round="Seed",
        listing_sources=["https://kind.krx.co.kr/"],
        registry_sources=["https://dart.fss.or.kr/"],
    )

    analysis, sources, _ = market_candidate(unknown_candidate)
    p1 = analysis.indicators[0]
    assert p1.query_status == QueryStatus.TARGET_MISMATCH
    assert p1.raw_value is None


def test_market_node_execution(arobot_parts_candidate: Candidate) -> None:
    mock_state: GraphState = {
        "run": RunConfig(
            run_id="run_001",
            evaluation_date=date(2026, 9, 30),
            rule_version="1.0.0",
            document_version="1.0.0",
        ),
        "candidates": [arobot_parts_candidate],
        "candidate_index": 0,
        "current_candidate": arobot_parts_candidate,
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

    update = market_node(mock_state)
    assert "market_analysis" in update
    assert "sources" in update
    assert update["market_analysis"].candidate_id == "arobot"
    assert update["market_analysis"].indicators[0].id == "P1"

    # Missing candidate must raise ValueError
    with pytest.raises(ValueError, match="current_candidate is required"):
        market_node({**mock_state, "current_candidate": None})
