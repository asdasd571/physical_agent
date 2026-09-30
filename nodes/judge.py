from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from schemas import (
    Decision,
    DecisionStatus,
    EligibilityStatus,
    EvaluationRecord,
    EvidenceStatus,
    GateResult,
    GraphState,
    IndicatorEvidence,
    QueryStatus,
)


SCORE_INDICATOR_IDS = {
    "T1",
    "T2",
    "K1",
    "K2",
    "K3",
    "S1",
    "S2",
    "P1",
    "R1",
    "R2",
    "R3",
    "M1",
}
CATEGORY_INDICATORS = {
    "team": ("T1", "T2"),
    "tech": ("K1", "K2", "K3"),
    "synergy": ("S1", "S2"),
    "market": ("P1",),
    "traction": ("R1", "R2", "R3"),
    "moat": ("M1",),
}
CATEGORY_WEIGHTS = {
    "team": Decimal("20"),
    "tech": Decimal("20"),
    "synergy": Decimal("20"),
    "market": Decimal("15"),
    "traction": Decimal("15"),
    "moat": Decimal("10"),
}
ANALYSIS_FIELDS = (
    "company_profile",
    "tech_analysis",
    "market_analysis",
    "competitor_analysis",
    "synergy_analysis",
)


def judge_node(state: GraphState) -> dict[str, Any]:
    candidate = state["current_candidate"]
    eligibility = state["eligibility"]

    if candidate is None:
        raise ValueError("현재 평가 후보가 없습니다")

    if eligibility is None:
        raise ValueError("적격성 결과가 없습니다")

    indicators = collect_indicators(state)
    indicator_map = {indicator.id: indicator for indicator in indicators}
    missing_score_ids = SCORE_INDICATOR_IDS - set(indicator_map)

    if missing_score_ids:
        raise ValueError(
            "채점에 필요한 지표가 없습니다: " + ", ".join(sorted(missing_score_ids))
        )

    indicator_scores = {
        indicator_id: score_indicator(indicator_map[indicator_id])
        for indicator_id in sorted(SCORE_INDICATOR_IDS)
    }
    category_scores = calculate_category_scores(indicator_scores)
    total_score = calculate_total_score(category_scores)
    gates = calculate_gates(eligibility, indicator_map)
    failed_gates = [gate_id for gate_id, gate in gates.items() if not gate.passed]
    invest = not failed_gates and total_score >= Decimal("70.0")
    decision_reasons: list[str] = []

    if failed_gates:
        decision_reasons.append("미통과 게이트: " + ", ".join(failed_gates))

    if total_score < Decimal("70.0"):
        decision_reasons.append(f"총점이 70점 미만입니다: {total_score}")

    if invest:
        decision_reasons.append("모든 게이트를 통과하고 총점이 70점 이상입니다")

    missing_indicators = [
        indicator_id
        for indicator_id in sorted(SCORE_INDICATOR_IDS)
        if is_missing(indicator_map[indicator_id])
    ]
    unknown_items = list(
        dict.fromkeys(
            item
            for gate in gates.values()
            for item in gate.unknown_items
        )
    )
    due_diligence_items = list(unknown_items)

    if len(missing_indicators) >= 6:
        due_diligence_items.append(
            f"자료 없음 지표가 {len(missing_indicators)}개이므로 정보 부족 검토가 필요합니다"
        )

    due_diligence_items.extend(
        f"{indicator_id} 원값과 근거를 추가 확인해야 합니다"
        for indicator_id in missing_indicators
    )
    due_diligence_items = list(dict.fromkeys(due_diligence_items))
    decision = Decision(
        status=DecisionStatus.INVEST if invest else DecisionStatus.HOLD,
        reasons=decision_reasons,
    )
    confirmed_count = sum(
        not is_missing(indicator_map[indicator_id])
        for indicator_id in SCORE_INDICATOR_IDS
    )
    evidence_coverage = (
        Decimal(confirmed_count) / Decimal(len(SCORE_INDICATOR_IDS))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    evaluation = EvaluationRecord(
        candidate_id=candidate.candidate_id,
        country=candidate.country,
        primary_segment=candidate.primary_segment,
        rule_version=state["run"].rule_version,
        indicators=indicators,
        indicator_scores=indicator_scores,
        category_scores=category_scores,
        gates=gates,
        total_score=total_score,
        decision=decision,
        evidence_coverage=evidence_coverage,
        unknown_items=unknown_items,
        due_diligence_items=due_diligence_items,
        metadata={
            "missing_indicator_count": len(missing_indicators),
            "missing_indicator_ids": missing_indicators,
        },
    )

    return {
        "evaluation": evaluation,
        "decision": decision,
    }


def collect_indicators(state: GraphState) -> list[IndicatorEvidence]:
    indicators: list[IndicatorEvidence] = []
    seen_ids: set[str] = set()

    for field_name in ANALYSIS_FIELDS:
        analysis = state[field_name]

        if analysis is None:
            raise ValueError(f"분석 결과가 없습니다: {field_name}")

        for indicator in analysis.indicators:
            if indicator.id in seen_ids:
                raise ValueError(f"지표가 중복되었습니다: {indicator.id}")

            seen_ids.add(indicator.id)
            indicators.append(indicator)

    return indicators


def score_indicator(indicator: IndicatorEvidence) -> int:
    if is_missing(indicator):
        return 1

    value = numeric_value(indicator.raw_value, indicator.id)

    if value is None:
        score = 1
    elif indicator.id == "T1":
        if value < 1:
            score = 1
        elif value < 2:
            score = 2 if indicator.evidence_status == EvidenceStatus.COMPANY_CLAIM else 3
        elif value < 3:
            score = 4
        else:
            score = 5
    elif indicator.id == "T2":
        score = 1 if value <= 0 else score_ranges(
            value,
            (1, 2, 4),
            (2, 3, 4, 5),
        )
    elif indicator.id == "K1":
        score = score_count(value, (1, 2, 3, 5), (2, 3, 4, 5, 5))
    elif indicator.id == "K2":
        attempts = None
        if isinstance(indicator.raw_value, dict):
            attempts = numeric_from_mapping(
                indicator.raw_value,
                ("total_trials", "total_attempts", "attempts", "trial_count"),
            )
        if attempts is None:
            attempts = numeric_from_mapping(
                indicator.condition,
                ("total_trials", "total_attempts", "attempts", "trial_count"),
            )
        score = 1 if attempts is not None and attempts < 30 else score_ranges(
            value,
            (50, 70, 85, 95),
            (1, 2, 3, 4, 5),
        )
    elif indicator.id == "K3":
        score = score_count(value, (1, 2, 3, 5), (2, 3, 4, 5, 5))
    elif indicator.id in {"S1", "S2"}:
        score = score_count(value, (1, 2, 3, 4), (2, 3, 4, 5, 5))
    elif indicator.id == "P1":
        score = score_ranges(value, (0, 5, 10, 20), (1, 2, 3, 4, 5))
    elif indicator.id == "R1":
        score = score_ranges(value, (5, 20, 50, 150), (1, 2, 3, 4, 5))
    elif indicator.id == "R2":
        score = score_ranges(value, (1, 5, 15, 30), (1, 2, 3, 4, 5))
    elif indicator.id == "R3":
        score = score_ranges(value, (0, 10, 30, 60), (1, 2, 3, 4, 5))
        previous_count = numeric_from_mapping(
            indicator.condition,
            ("previous_employee_count", "previous_count"),
        )
        if previous_count is not None and 1 <= previous_count <= 9:
            score = min(score, 3)
    elif indicator.id == "M1":
        score = score_count(value, (1, 2, 4, 7), (2, 3, 4, 5, 5))
    else:
        raise ValueError(f"지원하지 않는 채점 지표입니다: {indicator.id}")

    if indicator.id == "S1" and indicator.evidence_status == EvidenceStatus.COMPANY_CLAIM:
        score = 1
    elif indicator.evidence_status == EvidenceStatus.COMPANY_CLAIM:
        score = min(score, 3)

    return score


def calculate_category_scores(
    indicator_scores: dict[str, int],
) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}

    for category, indicator_ids in CATEGORY_INDICATORS.items():
        average = sum(
            Decimal(indicator_scores[indicator_id])
            for indicator_id in indicator_ids
        ) / Decimal(len(indicator_ids))
        result[category] = average.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    return result


def calculate_total_score(category_scores: dict[str, Decimal]) -> Decimal:
    total = sum(
        category_scores[category] / Decimal("5") * weight
        for category, weight in CATEGORY_WEIGHTS.items()
    )
    return total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def calculate_gates(
    eligibility: Any,
    indicator_map: dict[str, IndicatorEvidence],
) -> dict[str, GateResult]:
    g1_passed = eligibility.status == EligibilityStatus.PASS
    g1 = GateResult(
        passed=g1_passed,
        reasons=list(eligibility.reasons),
        source_ids=list(eligibility.source_ids),
        unknown_items=list(eligibility.unknown_items),
    )
    s2 = indicator_map.get("S2")
    s2_count = numeric_value(s2.raw_value, "S2") if s2 and not is_missing(s2) else None
    g2_passed = s2_count is not None and s2_count >= 1
    g2_unknown = [] if s2_count is not None else ["S2 모기업 수요 연결"]
    g2 = GateResult(
        passed=g2_passed,
        reasons=[
            "모기업 수요와 연결된 인정 작업이 있습니다"
            if g2_passed
            else "모기업 수요와 연결된 인정 작업이 없습니다"
        ],
        source_ids=list(s2.source_ids) if s2 else [],
        unknown_items=g2_unknown,
    )
    g3_failures: list[str] = []
    g3_unknown: list[str] = []
    g3_source_ids: list[str] = []

    for indicator_id in ("F1", "F2", "F3"):
        indicator = indicator_map.get(indicator_id)
        if indicator is None or is_missing(indicator):
            g3_unknown.append(indicator_id)
            continue

        g3_source_ids.extend(indicator.source_ids)
        gate_score = score_risk_indicator(indicator)
        if gate_score is None:
            g3_unknown.append(indicator_id)
        elif gate_score == 1:
            g3_failures.append(f"{indicator_id} 결격 기준에 해당합니다")

    f4 = indicator_map.get("F4")
    if f4 is None or is_missing(f4):
        g3_unknown.append("F4")
    else:
        g3_source_ids.extend(f4.source_ids)
        f4_result = evaluate_f4(f4.raw_value)
        if f4_result is False:
            g3_failures.append("F4 현장 필수 인증 결격 기준에 해당합니다")
        elif f4_result is None:
            g3_unknown.append("F4")

    g3 = GateResult(
        passed=not g3_failures,
        reasons=g3_failures or ["확인된 결격 리스크가 없습니다"],
        source_ids=list(dict.fromkeys(g3_source_ids)),
        unknown_items=g3_unknown,
    )
    return {"G1": g1, "G2": g2, "G3": g3}


def score_risk_indicator(indicator: IndicatorEvidence) -> int | None:
    if indicator.id == "F1":
        if isinstance(indicator.raw_value, dict) and indicator.raw_value.get(
            "positive_operating_cash_flow"
        ) is True:
            return 5
        value = numeric_value(indicator.raw_value, "F1")
        if value is None:
            return None
        return score_ranges(value, (6, 12, 18, 24), (1, 2, 3, 4, 5))

    if indicator.id == "F2":
        if not isinstance(indicator.raw_value, dict):
            return None
        opinion = indicator.raw_value.get("audit_opinion")
        equity = numeric_from_mapping(indicator.raw_value, ("total_equity",))
        impairment = numeric_from_mapping(indicator.raw_value, ("impairment_rate",))
        debt_ratio = numeric_from_mapping(indicator.raw_value, ("debt_ratio",))
        going_concern = indicator.raw_value.get("going_concern_uncertainty")
        if equity is not None and equity < 0:
            return 1
        if opinion in {"한정", "부적정", "의견거절"}:
            return 1
        if impairment is not None and impairment >= 50:
            return 2
        if going_concern is True:
            return 2
        if impairment is not None and impairment > 0:
            return 3
        if impairment is not None and impairment <= 0:
            return 5 if debt_ratio is not None and debt_ratio <= 100 else 4
        return None

    if indicator.id == "F3":
        value = numeric_value(indicator.raw_value, "F3")
        if value is None:
            return None
        if value >= 4:
            return 1
        if value == 3:
            return 2
        if value == 2:
            return 3
        if value == 1:
            return 4
        return 5

    return None


def evaluate_f4(raw_value: Any) -> bool | None:
    if not isinstance(raw_value, dict):
        return None

    explosive = first_value(
        raw_value,
        ("explosive_area", "is_explosive_area", "hazardous_area"),
    )
    certified = first_value(
        raw_value,
        ("certified_or_in_progress", "certification_evidence", "has_certification"),
    )

    if explosive is False:
        return True
    if explosive is True and certified is True:
        return True
    if explosive is True and certified is False:
        return False
    return None


def is_missing(indicator: IndicatorEvidence) -> bool:
    return (
        indicator.raw_value is None
        or indicator.query_status != QueryStatus.SUCCESS
        or indicator.evidence_status == EvidenceStatus.NO_EVIDENCE
    )


def numeric_value(raw_value: Any, indicator_id: str) -> Decimal | None:
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, (int, float, Decimal)):
        return Decimal(str(raw_value))
    if isinstance(raw_value, (list, tuple, set)):
        return Decimal(len(raw_value))
    if isinstance(raw_value, dict):
        keys = {
            "T1": ("count", "experienced_people"),
            "T2": ("papers_per_founder", "value"),
            "K1": ("count", "paper_count"),
            "K2": ("success_rate_percent", "success_rate", "value"),
            "K3": ("count", "site_count"),
            "S1": ("count", "task_count"),
            "S2": ("matched_task_count", "count", "connected_task_count"),
            "P1": ("cagr", "value"),
            "R1": ("amount_krw_100m", "value"),
            "R2": ("amount_krw_100m", "value"),
            "R3": ("growth_rate", "value"),
            "M1": ("count", "family_count"),
            "F1": ("runway_months", "value"),
            "F3": ("event_count", "count", "value"),
        }.get(indicator_id, ("value", "count"))
        return numeric_from_mapping(raw_value, keys)
    return None


def numeric_from_mapping(
    values: dict[str, Any],
    keys: tuple[str, ...],
) -> Decimal | None:
    value = first_value(values, keys)
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    return Decimal(str(value))


def first_value(values: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in values:
            return values[key]
    return None


def score_ranges(
    value: Decimal,
    thresholds: tuple[int, ...],
    scores: tuple[int, ...],
) -> int:
    for index, threshold in enumerate(thresholds):
        if value < Decimal(threshold):
            return scores[index]
    return scores[-1]


def score_count(
    value: Decimal,
    thresholds: tuple[int, ...],
    scores: tuple[int, ...],
) -> int:
    for index, threshold in enumerate(thresholds):
        if value < Decimal(threshold):
            return 1 if index == 0 else scores[index - 1]
    return scores[-1]
