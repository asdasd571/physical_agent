from datetime import date
from decimal import Decimal
from typing import Any, cast

from nodes.judge import calculate_total_score, judge_node, score_indicator, numeric_value, score_risk_indicator
import json
from pathlib import Path
import pytest
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


@pytest.mark.parametrize("key,raw,expected", [
    ("T1", {"qualified_count": 2}, Decimal(2)),
    ("P1", {"cagr_percent": 9.5}, Decimal("9.5")),
    ("M1", {"unique_priority_families": 4}, Decimal(4)),
    ("F3", {"case_count": 0}, Decimal(0)),
    ("R2", {"amount_krw_100m": "2.5"}, Decimal("2.5")),
])
def test_producer_field_names_are_read(key, raw, expected):
    assert numeric_value(raw, key) == expected


def test_round_amounts_exclude_cumulative_and_deduplicate():
    row = {"round_name": "A", "announced_at": "2025-01-01", "amount_original": 10_000_000_000,
           "currency": "KRW", "is_cumulative_announcement": False}
    cumulative = {**row, "amount_original": 20_000_000_000, "is_cumulative_announcement": True}
    assert numeric_value({"rounds": [row, dict(row), cumulative]}, "R1") == Decimal(100)
    with pytest.raises(ValueError):
        numeric_value({"rounds": [row, {**row, "amount_original": 1}]}, "R1")
    assert numeric_value({"rounds": [{**row, "currency": "USD"}]}, "R1") is None


def test_growth_uses_matching_scope_and_small_baseline_cap():
    raw = {"prior": {"count": 5, "as_of": "2025-01-01", "scope": "법인"},
           "latest": {"count": 10, "as_of": "2026-01-01", "scope": "법인"}}
    assert numeric_value(raw, "R3") == Decimal(100)
    assert score_indicator(make_indicator("R3", raw)) == 3
    raw["prior"]["count"] = 0
    assert numeric_value(raw, "R3") is None
    raw["prior"]["count"] = 5
    raw["latest"]["scope"] = "그룹"
    assert numeric_value(raw, "R3") is None


def test_financial_raw_values_support_risk_rules():
    raw = {"cash_and_equivalents": 100, "short_term_financial_instruments": 20,
           "operating_cash_flow": -60, "currency": "KRW", "fiscal_period": "2025-01-01~2025-12-31"}
    assert numeric_value(raw, "F1") == Decimal(24)
    assert score_risk_indicator(make_indicator("F1", raw)) == 5
    assert score_risk_indicator(make_indicator("F1", {**raw, "operating_cash_flow": 10})) == 5
    assert score_risk_indicator(make_indicator("F2", {"capital_stock": 100, "total_equity": 50,
                                                     "total_liabilities": 20})) == 2
    assert score_risk_indicator(make_indicator("F2", {"capital_stock": 100, "total_equity": 200,
                                                     "total_liabilities": 100})) == 5


@pytest.mark.parametrize("candidate", ["arobot", "aidin_robotics"])
def test_repository_values_do_not_all_fall_back_to_one(candidate):
    root = Path(__file__).resolve().parents[1]
    company = json.loads((root / f"data/evidence/company/{candidate}.json").read_text())
    for key in ("T1", "R1", "R3"):
        indicator = IndicatorEvidence.model_validate({"id": key, "collected_by": "discover",
                                                     **company["indicators"][key]})
        assert numeric_value(indicator.raw_value, key) is not None
        assert score_indicator(indicator) > 1
