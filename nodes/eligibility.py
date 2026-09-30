from __future__ import annotations

from typing import Any

from schemas import (
    EligibilityResult,
    EligibilityStatus,
    GraphState,
    QueryStatus,
)


ALLOWED_ROUNDS = {"Seed", "Pre-A", "Series A", "Series B"}
INACTIVE_STATUSES = {"휴업", "폐업"}
REQUIRED_FACTS = {
    "unlisted": "비상장 여부",
    "latest_round": "최근 투자 단계",
    "exit_completed": "Exit 완료 여부",
    "operating_status": "영업 상태",
}
MISSING = object()


def eligibility_node(state: GraphState) -> dict[str, Any]:
    candidate = state["current_candidate"]
    profile = state["company_profile"]

    if candidate is None:
        raise ValueError("현재 평가 후보가 없습니다")

    if profile is None:
        raise ValueError("기업 정보 확인 결과가 없습니다")

    if profile.candidate_id != candidate.candidate_id:
        raise ValueError("기업 정보의 후보 ID가 현재 후보와 일치하지 않습니다")

    indicators = [indicator for indicator in profile.indicators if indicator.id == "G1"]

    if len(indicators) > 1:
        raise ValueError("G1 적격성 지표가 중복되었습니다")

    if not indicators:
        return {
            "eligibility": EligibilityResult(
                status=EligibilityStatus.UNKNOWN,
                reasons=["G1 적격성 자료가 없습니다"],
                unknown_items=list(REQUIRED_FACTS.values()),
            )
        }

    indicator = indicators[0]
    source_ids = collect_source_ids(indicator.source_ids, indicator.raw_value)

    if indicator.query_status != QueryStatus.SUCCESS or indicator.raw_value is None:
        return {
            "eligibility": EligibilityResult(
                status=EligibilityStatus.UNKNOWN,
                reasons=[indicator.missing_reason or "G1 적격성 자료를 확인하지 못했습니다"],
                source_ids=source_ids,
                unknown_items=list(REQUIRED_FACTS.values()),
            )
        }

    if not isinstance(indicator.raw_value, dict):
        raise ValueError("G1 원값은 사전 형식이어야 합니다")

    values = {
        key: extract_value(indicator.raw_value, key)
        for key in REQUIRED_FACTS
    }
    failure_reasons: list[str] = []
    unknown_items: list[str] = []

    unlisted = values["unlisted"]
    if unlisted is False:
        failure_reasons.append("상장사로 확인되었습니다")
    elif unlisted is not True:
        unknown_items.append(REQUIRED_FACTS["unlisted"])

    latest_round = values["latest_round"]
    if isinstance(latest_round, str) and latest_round:
        if latest_round not in ALLOWED_ROUNDS:
            failure_reasons.append(f"적격 투자 단계가 아닙니다: {latest_round}")
    else:
        unknown_items.append(REQUIRED_FACTS["latest_round"])

    exit_completed = values["exit_completed"]
    if exit_completed is True:
        failure_reasons.append("IPO 또는 M&A Exit 완료가 확인되었습니다")
    elif exit_completed is not False:
        unknown_items.append(REQUIRED_FACTS["exit_completed"])

    operating_status = values["operating_status"]
    if operating_status in INACTIVE_STATUSES:
        failure_reasons.append(f"영업 상태가 {operating_status}으로 확인되었습니다")
    elif operating_status != "정상":
        unknown_items.append(REQUIRED_FACTS["operating_status"])

    if failure_reasons:
        status = EligibilityStatus.FAIL
        reasons = failure_reasons
    elif unknown_items:
        status = EligibilityStatus.UNKNOWN
        reasons = ["G1 적격성 요건 일부를 확인하지 못했습니다"]
    else:
        status = EligibilityStatus.PASS
        reasons = ["G1 적격성 4개 요건을 모두 충족했습니다"]

    return {
        "eligibility": EligibilityResult(
            status=status,
            reasons=reasons,
            source_ids=source_ids,
            unknown_items=unknown_items,
        )
    }


def extract_value(raw_value: dict[str, Any], key: str) -> Any:
    fact = raw_value.get(key)

    if not isinstance(fact, dict):
        return MISSING

    return fact.get("value", MISSING)


def collect_source_ids(
    indicator_source_ids: list[str],
    raw_value: Any,
) -> list[str]:
    source_ids = list(indicator_source_ids)

    if isinstance(raw_value, dict):
        for fact in raw_value.values():
            if not isinstance(fact, dict):
                continue

            source_id = fact.get("source_id")

            if isinstance(source_id, str) and source_id:
                source_ids.append(source_id)

    return list(dict.fromkeys(source_ids))
