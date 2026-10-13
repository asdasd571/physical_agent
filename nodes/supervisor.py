"""현재 근거의 결손을 기준으로 담당자를 선택하는 규칙 기반 Supervisor이다."""

from typing import Any

from nodes.eligibility import eligibility_node
from nodes.review import ANALYSIS_REQUIREMENTS, review_node
from schemas import EligibilityStatus
from schemas.supervisor import Assignment, RoutingDecision, SupervisorControl


def supervisor_node(state) -> dict[str, Any]:
    candidate = state["current_candidate"]
    control = state["supervisor"]
    policy = state["policy"]
    review = review_node(state)["evidence_review"]
    targets = {target.owner: target for target in review.repair_targets}
    deficits = {owner: len(target.indicator_ids) for owner, target in targets.items()}
    eligibility = None
    if state.get("company_profile") is not None:
        eligibility = eligibility_node(state)["eligibility"]

    def decide(route, reason, *, sufficient=False, termination=None):
        assignment = None
        count = control.dispatch_count
        if route in ANALYSIS_REQUIREMENTS:
            field, required = ANALYSIS_REQUIREMENTS[route]
            previous = state.get(field)
            target = targets.get(route)
            assignment = Assignment(
                owner=route, candidate_id=candidate.candidate_id, reason=reason,
                indicator_ids=target.indicator_ids if target and target.indicator_ids else sorted(required),
                repair=previous is not None,
                tech_context=state.get("tech_analysis") if route in {"market", "synergy"} else None,
            )
            count += 1
        decision = RoutingDecision(
            sequence=len(control.decisions) + 1, candidate_id=candidate.candidate_id,
            route=route, reason=reason, deficits=deficits, evidence_sufficient=sufficient,
        )
        updated = control.model_copy(update={
            "next_node": route, "assignment": assignment, "dispatch_count": count,
            "evidence_sufficient": sufficient, "termination_reason": termination,
            "decisions": [*control.decisions, decision],
        })
        return {"supervisor": updated, "evidence_review": review, "eligibility": eligibility}

    budget_left = control.dispatch_count < policy.max_dispatches_per_candidate

    def available(owner):
        return budget_left and control.attempts.get(owner, 0) < policy.max_attempts_per_agent

    # 적격성 확인은 심층 조사 비용을 쓰기 위한 선행 조건이다.
    if eligibility is None or eligibility.status == EligibilityStatus.UNKNOWN:
        if available("discover"):
            return decide("discover", "기업 적격성 근거가 없거나 불충분하여 확인을 요청합니다.")
        return decide("skip", "적격성 확인 한도에 도달하여 심층 평가를 보류합니다.", termination="eligibility_unresolved")
    if eligibility.status == EligibilityStatus.FAIL:
        return decide("skip", "적격성 기준에 해당하지 않아 심층 평가를 생략합니다.", termination="ineligible")

    if not targets:
        return decide("judge", "모든 필수 지표의 출처와 조건을 확인하여 투자 규칙 평가로 진행합니다.",
                      sufficient=True, termination="evidence_sufficient")

    options = [owner for owner in targets if available(owner)]
    if options:
        # 미수행 관점을 먼저 확보하고, 같은 조건에서는 미확인 지표 수가 큰 담당자를 선택한다.
        # 이름은 동점일 때만 사용하므로 기술→시장 등의 실행 순서는 고정하지 않는다.
        owner = min(options, key=lambda name: (
            control.attempts.get(name, 0) > 0, -deficits[name], name,
        ))
        return decide(owner, targets[owner].reason)
    return decide("judge", "추가 조사 한도에 도달했습니다. 미확인 근거를 명시하고 보수적으로 판정합니다.",
                  termination="evidence_exhausted")


def route_supervisor(state):
    return state["supervisor"].next_node
