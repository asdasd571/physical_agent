from __future__ import annotations

from collections import defaultdict
from typing import Any

from schemas import (
    EvidenceReview,
    EvidenceStatus,
    GraphState,
    QueryStatus,
    RepairTarget,
)


ANALYSIS_REQUIREMENTS = {
    "discover": ("company_profile", {"G1", "T1", "R1", "R3", "F1", "F2", "F3"}),
    "tech": ("tech_analysis", {"T2", "K1", "K2", "K3", "R2"}),
    "market": ("market_analysis", {"P1"}),
    "competitor": ("competitor_analysis", {"M1"}),
    "synergy": ("synergy_analysis", {"S1", "S2", "F4"}),
}
PERIOD_REQUIRED = {"T2", "K1", "K3", "P1", "R2", "R3", "F3"}
CONDITION_REQUIRED = {"K2", "S1", "S2", "F4"}


def review_node(state: GraphState) -> dict[str, Any]:
    candidate = state["current_candidate"]

    if candidate is None:
        raise ValueError("현재 평가 후보가 없습니다")

    available_source_ids = {source.source_id for source in state["sources"]}
    issues_by_owner: dict[str, list[str]] = defaultdict(list)
    indicator_ids_by_owner: dict[str, set[str]] = defaultdict(set)

    for owner, (field_name, required_ids) in ANALYSIS_REQUIREMENTS.items():
        analysis = state[field_name]

        if analysis is None:
            issues_by_owner[owner].append(f"{field_name} 분석 결과가 없습니다")
            indicator_ids_by_owner[owner].update(required_ids)
            continue

        if analysis.candidate_id != candidate.candidate_id:
            issues_by_owner[owner].append(
                f"{field_name}의 후보 ID가 현재 후보와 일치하지 않습니다"
            )
            indicator_ids_by_owner[owner].update(required_ids)

        missing_analysis_sources = set(analysis.source_ids) - available_source_ids
        if missing_analysis_sources:
            issues_by_owner[owner].append(
                "State에 없는 분석 출처가 있습니다: "
                + ", ".join(sorted(missing_analysis_sources))
            )

        seen_ids: set[str] = set()
        duplicate_ids: set[str] = set()

        for indicator in analysis.indicators:
            if indicator.id in seen_ids:
                duplicate_ids.add(indicator.id)
            seen_ids.add(indicator.id)

        if duplicate_ids:
            issues_by_owner[owner].append(
                "중복 지표가 있습니다: " + ", ".join(sorted(duplicate_ids))
            )
            indicator_ids_by_owner[owner].update(duplicate_ids)

        missing_ids = required_ids - seen_ids
        if missing_ids:
            issues_by_owner[owner].append(
                "필수 지표가 없습니다: " + ", ".join(sorted(missing_ids))
            )
            indicator_ids_by_owner[owner].update(missing_ids)

        for indicator in analysis.indicators:
            indicator_issues = validate_indicator(
                indicator,
                analysis.source_ids,
                available_source_ids,
            )
            if indicator_issues:
                indicator_ids_by_owner[owner].add(indicator.id)
                issues_by_owner[owner].extend(indicator_issues)

    repair_targets = [
        RepairTarget(
            owner=owner,
            indicator_ids=sorted(indicator_ids_by_owner[owner]),
            reason="; ".join(dict.fromkeys(issues)),
        )
        for owner, issues in issues_by_owner.items()
        if issues
    ]
    all_issues = [
        f"{owner}: {issue}"
        for owner, issues in issues_by_owner.items()
        for issue in dict.fromkeys(issues)
    ]

    return {
        "evidence_review": EvidenceReview(
            candidate_id=candidate.candidate_id,
            passed=not all_issues,
            repair_required=bool(repair_targets),
            repair_targets=repair_targets,
            issues=all_issues,
        )
    }


def validate_indicator(
    indicator: Any,
    analysis_source_ids: list[str],
    available_source_ids: set[str],
) -> list[str]:
    issues: list[str] = []

    missing_from_analysis = set(indicator.source_ids) - set(analysis_source_ids)
    if missing_from_analysis:
        issues.append(
            f"{indicator.id} 지표 출처가 분석 출처에 없습니다: "
            + ", ".join(sorted(missing_from_analysis))
        )

    missing_from_state = set(indicator.source_ids) - available_source_ids
    if missing_from_state:
        issues.append(
            f"{indicator.id} 지표 출처가 State에 없습니다: "
            + ", ".join(sorted(missing_from_state))
        )

    if indicator.query_status != QueryStatus.SUCCESS:
        issues.append(f"{indicator.id} 조회가 완료되지 않았습니다")

    if indicator.evidence_status == EvidenceStatus.NO_EVIDENCE:
        issues.append(f"{indicator.id} 근거 자료가 없습니다")

    if indicator.query_status == QueryStatus.SUCCESS and not indicator.source_ids:
        issues.append(f"{indicator.id} 출처가 없습니다")

    if indicator.query_status == QueryStatus.SUCCESS and indicator.unit is None:
        issues.append(f"{indicator.id} 단위가 없습니다")

    if indicator.id in PERIOD_REQUIRED and not indicator.period:
        issues.append(f"{indicator.id} 관측 기간이 없습니다")

    if indicator.id in CONDITION_REQUIRED and not indicator.condition:
        issues.append(f"{indicator.id} 계산 또는 적용 조건이 없습니다")

    return issues
