from datetime import date
from decimal import Decimal
from typing import Any, cast

from nodes.judge import calculate_total_score, judge_node, score_indicator
from schemas import (
    AnalysisResult,
    Candidate,
    EligibilityResult,
    EligibilityStatus,
    EvidenceStatus,
    GraphState,
    IndicatorEvidence,
    QueryStatus,
    RunConfig,
)


def make_indicator(
    indicator_id: str,
    raw_value: Any,
    evidence_status: EvidenceStatus = EvidenceStatus.THIRD_PARTY_VERIFIED,
    condition: dict[str, Any] | None = None,
) -> IndicatorEvidence:
    query_status = QueryStatus.SUCCESS if raw_value is not None else QueryStatus.NO_DATA
    return IndicatorEvidence(
        id=indicator_id,
        raw_value=raw_value,
        unit="test",
        period="2023-2026",
        condition=condition or {},
        evidence_status=evidence_status if raw_value is not None else EvidenceStatus.NO_EVIDENCE,
        collected_by="test",
        query_status=query_status,
        missing_reason=None if raw_value is not None else "자료 없음",
    )


def make_analysis(candidate_id: str, indicators: list[IndicatorEvidence]) -> AnalysisResult:
    return AnalysisResult(
        candidate_id=candidate_id,
        summary="분석 결과",
        indicators=indicators,
    )


def make_state(s2_value: int = 4) -> GraphState:
    candidate = Candidate(
        candidate_id="candidate-1",
        legal_name="Company 1",
        country="KR",
        legal_id="legal-1",
        founded_at=date(2020, 1, 1),
        primary_segment="robot-hand",
        latest_round="Series A",
        listing_sources=["listing"],
        registry_sources=["registry"],
    )
    return cast(
        GraphState,
        {
            "run": RunConfig(
                run_id="run-1",
                evaluation_date=date(2026, 9, 30),
                rule_version="1.0.0",
                document_version="1.0.0",
            ),
            "current_candidate": candidate,
            "eligibility": EligibilityResult(
                status=EligibilityStatus.PASS,
                reasons=["적격"],
            ),
            "company_profile": make_analysis(
                candidate.candidate_id,
                [
                    make_indicator("G1", {"value": True}),
                    make_indicator("T1", 3),
                    make_indicator("R1", 150),
                    make_indicator("R3", 60),
                    make_indicator("F1", 24),
                    make_indicator(
                        "F2",
                        {"impairment_rate": 0, "debt_ratio": 50},
                    ),
                    make_indicator("F3", 0),
                ],
            ),
            "tech_analysis": make_analysis(
                candidate.candidate_id,
                [
                    make_indicator("T2", 4),
                    make_indicator("K1", 5),
                    make_indicator("K2", 95, condition={"total_attempts": 30}),
                    make_indicator("K3", 5),
                    make_indicator("R2", 30),
                ],
            ),
            "market_analysis": make_analysis(
                candidate.candidate_id,
                [make_indicator("P1", 20)],
            ),
            "competitor_analysis": make_analysis(
                candidate.candidate_id,
                [make_indicator("M1", 7)],
            ),
            "synergy_analysis": make_analysis(
                candidate.candidate_id,
                [
                    make_indicator("S1", 4),
                    make_indicator("S2", s2_value),
                    make_indicator("F4", {"explosive_area": False}),
                ],
            ),
        },
    )


def test_company_claim_score_is_capped() -> None:
    indicator = make_indicator(
        "K1",
        8,
        evidence_status=EvidenceStatus.COMPANY_CLAIM,
    )

    assert score_indicator(indicator) == 3


def test_k2_uses_agent_raw_value_shape() -> None:
    indicator = make_indicator(
        "K2",
        {
            "successful_trials": 28,
            "total_trials": 30,
            "success_rate_percent": 93.33,
        },
        condition={
            "task": "배터리 셀 집기",
            "environment": "실험실 실제 로봇",
            "success_definition": "지정 위치 이동",
        },
    )

    assert score_indicator(indicator) == 4


def test_s2_uses_agent_raw_value_shape() -> None:
    indicator = make_indicator(
        "S2",
        {"matched_task_count": 2, "matches": []},
    )

    assert score_indicator(indicator) == 3


def test_total_score_uses_round_half_up() -> None:
    category_scores = {
        "team": Decimal("3.5025"),
        "tech": Decimal("3.5025"),
        "synergy": Decimal("3.5025"),
        "market": Decimal("3.5025"),
        "traction": Decimal("3.5025"),
        "moat": Decimal("3.5025"),
    }

    assert calculate_total_score(category_scores) == Decimal("70.1")


def test_judge_invests_when_all_gates_pass() -> None:
    result = judge_node(make_state())

    assert result["evaluation"].total_score == Decimal("100.0")
    assert result["decision"].status.value == "INVEST"


def test_failed_g2_forces_hold() -> None:
    result = judge_node(make_state(s2_value=0))

    assert result["evaluation"].gates["G2"].passed is False
    assert result["decision"].status.value == "HOLD"
