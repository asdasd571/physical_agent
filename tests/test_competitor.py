from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import pytest

from agents.competitor import (
    competitor_candidate,
    competitor_node,
    validate_patent_raw_value,
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


def test_competitor_candidate_arobot(arobot_candidate: Candidate) -> None:
    analysis, sources, comp_products = competitor_candidate(arobot_candidate)

    assert analysis.candidate_id == "arobot"
    assert len(analysis.indicators) == 1

    m1 = analysis.indicators[0]
    assert m1.id == "M1"
    assert m1.query_status == QueryStatus.SUCCESS
    assert m1.evidence_status == EvidenceStatus.THIRD_PARTY_VERIFIED
    assert m1.unit == "특허 패밀리"

    # Patent family counts
    assert m1.raw_value["valid_registered_patents"] == 3
    assert m1.raw_value["unique_priority_families"] == 3
    assert len(m1.raw_value["family_ids"]) == 3
    assert len(m1.raw_value["patents"]) == 3
    assert len(m1.raw_value["excluded"]) == 2

    # Check sources list (must not be single source)
    assert len(sources) >= 1
    assert sources[0].source_id == "src_patent_arobot_kipris"
    assert len(comp_products) == 2

    # Check summary
    assert "3개 패밀리" in analysis.summary
    assert "2개 벤치마크" in analysis.summary


def test_competitor_candidate_aidin_multi_sources(aidin_candidate: Candidate) -> None:
    analysis, sources, comp_products = competitor_candidate(aidin_candidate)

    assert analysis.candidate_id == "aidin_robotics"
    # Multiple sources from KR and US
    assert len(sources) == 2
    source_ids = {s.source_id for s in sources}
    assert "src_patent_aidin_kipris" in source_ids
    assert "src_patent_aidin_uspto" in source_ids

    m1 = analysis.indicators[0]
    assert m1.query_status == QueryStatus.SUCCESS
    assert m1.raw_value["valid_registered_patents"] == 5
    assert m1.raw_value["unique_priority_families"] == 4


def test_competitor_summary_does_not_say_zero_on_failure(tmp_path: Path, arobot_candidate: Candidate) -> None:
    # Prepare mock evidence file with ACCESS_FAILED
    failed_data = {
        "candidate_id": "arobot",
        "searched_at": "2026-09-30T10:30:00+09:00",
        "checked_by": "박세진",
        "query_status": "ACCESS_FAILED",
        "missing_reason": "특허정보넷 KIPRIS Open API 일시적 타임아웃 장애",
        "evidence_status": "NO_DATA",
        "unit": "특허 패밀리",
        "as_of": "2026-09-30",
        "raw_value": None,
        "sources": [
            {
                "source_id": "src_patent_fail",
                "kind": "WEB",
                "publisher": "KIPRIS",
                "title": "KIPRIS 응답 로그",
                "evidence_excerpt": "Connection timeout"
            }
        ],
        "comparison_products": []
    }

    mock_file = tmp_path / "arobot_patents.json"
    with open(mock_file, "w", encoding="utf-8") as f:
        json.dump(failed_data, f)

    analysis, sources, _ = competitor_candidate(arobot_candidate, evidence_dir=tmp_path)

    # Must state ACCESS_FAILED and MUST NOT state "0개 패밀리"
    assert "ACCESS_FAILED" in analysis.summary
    assert "0개 패밀리" not in analysis.summary
    assert "타임아웃" in analysis.summary


def test_competitor_missing_file_raises_filenotfound(arobot_candidate: Candidate, tmp_path: Path) -> None:
    # Empty dir with no file must raise FileNotFoundError, not silently turn into 1 point NO_DATA
    with pytest.raises(FileNotFoundError, match="특허 원천 근거 파일 부재"):
        competitor_candidate(arobot_candidate, evidence_dir=tmp_path)


def test_validate_patent_raw_value_checks() -> None:
    # 1. family_ids mismatch
    with pytest.raises(ValueError, match="len"):
        validate_patent_raw_value({
            "valid_registered_patents": 3,
            "unique_priority_families": 2,
            "family_ids": ["FAM-01"],  # len is 1, but unique_priority_families is 2
            "searched_offices": [{"office": "KR", "query": "..."}],
        })

    # 2. unique_families > valid_count
    with pytest.raises(ValueError, match="cannot exceed"):
        validate_patent_raw_value({
            "valid_registered_patents": 1,
            "unique_priority_families": 2,
            "family_ids": ["FAM-01", "FAM-02"],
            "searched_offices": [{"office": "KR", "query": "..."}],
        })

    # 3. empty searched offices
    with pytest.raises(ValueError, match="searched_offices"):
        validate_patent_raw_value({
            "valid_registered_patents": 1,
            "unique_priority_families": 1,
            "family_ids": ["FAM-01"],
            "searched_offices": [],
        })


def test_competitor_benchmark_candidate_pool_collision(arobot_candidate: Candidate, tmp_path: Path) -> None:
    # If comparison products include an investment candidate, it must be rejected
    colliding_data = {
      "candidate_id": "arobot",
      "searched_at": "2026-09-30T10:30:00+09:00",
      "checked_by": "박세진",
      "query_status": "SUCCESS",
      "missing_reason": None,
      "evidence_status": "THIRD_PARTY_VERIFIED",
      "unit": "특허 패밀리",
      "as_of": "2026-09-30",
      "raw_value": {
        "valid_registered_patents": 1,
        "unique_priority_families": 1,
        "family_ids": ["FAM-1"],
        "searched_offices": [{"office": "KR", "query": "Q"}],
        "patents": [{"number": "1", "title": "그리퍼", "q_basis": "그리퍼"}]
      },
      "sources": [{"source_id": "s1", "kind": "WEB", "publisher": "p", "title": "t"}],
      "comparison_products": [
          {"company": "주식회사 에이로봇", "product": "Robot Hand", "attributes": {"source_ids": ["s1"]}}
      ]
    }
    mock_file = tmp_path / "arobot_patents.json"
    with open(mock_file, "w", encoding="utf-8") as f:
        json.dump(colliding_data, f)

    with pytest.raises(ValueError, match="투자 평가 대상 후보군에 포함"):
        competitor_candidate(arobot_candidate, evidence_dir=tmp_path, candidate_pool=[arobot_candidate])


def test_competitor_node_repair_with_control_variants(arobot_candidate: Candidate) -> None:
    mock_state: GraphState = {
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
        "control": ControlState(retry_count=1, repaired_indicator_ids=["M1"]),
        "evaluation": None,
        "decision": None,
        "evaluations": [],
        "sources": [],
        "report": None,
    }

    update = competitor_node(mock_state)
    assert update["competitor_analysis"].indicators[0].id == "M1"
