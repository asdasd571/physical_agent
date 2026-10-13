"""기존 담당 에이전트에 Supervisor의 요청만 전달하는 어댑터이다."""

from copy import deepcopy

from graph.reducers import merge_sources
from nodes.review import ANALYSIS_REQUIREMENTS
from schemas import AnalysisResult, ControlState, EvidenceReview, EvidenceStatus
from schemas import IndicatorEvidence, QueryStatus, RepairTarget


def missing_analysis(state, owner, reason):
    _, required = ANALYSIS_REQUIREMENTS[owner]
    return AnalysisResult(
        candidate_id=state["current_candidate"].candidate_id, summary=reason,
        indicators=[IndicatorEvidence(
            id=key, collected_by=owner, as_of=state["run"].evaluation_date,
            evidence_status=EvidenceStatus.NO_EVIDENCE, query_status=QueryStatus.ACCESS_FAILED,
            missing_reason=reason,
        ) for key in sorted(required)],
    )


def make_supervised_worker(owner, handler):
    field, required = ANALYSIS_REQUIREMENTS[owner]
    auxiliary = {"discover": {"handoff_urls"}, "market": {"reference_market_info"},
                 "competitor": {"comparison_products"}}.get(owner, set())

    def worker(state):
        control = state["supervisor"]
        request = control.assignment
        if request is None or request.owner != owner or request.candidate_id != state["current_candidate"].candidate_id:
            raise ValueError("Supervisor의 담당자·후보 지정과 호출이 일치하지 않습니다.")
        # 전체 State를 넘기지 않는다. 각 담당자는 자신의 이전 결과와 명시적 전달 자료만 읽는다.
        local = {
            "run": state["run"], "candidates": state["candidates"],
            "current_candidate": state["current_candidate"], "sources": state["sources"],
            "control": ControlState(repaired_indicator_ids=request.indicator_ids if request.repair else []),
            "evidence_review": None,
        }
        local.update({name: None for name, _ in ANALYSIS_REQUIREMENTS.values()})
        local[field] = state.get(field)
        if request.tech_context is not None:
            local["tech_analysis"] = request.tech_context
        if request.repair:
            local["evidence_review"] = EvidenceReview(
                candidate_id=request.candidate_id, passed=False, repair_required=True,
                repair_targets=[RepairTarget(owner=owner, indicator_ids=request.indicator_ids, reason=request.reason)],
            )
        attempts = {**control.attempts, owner: control.attempts.get(owner, 0) + 1}
        failures = dict(control.failures)
        try:
            update = handler(deepcopy(local))
            if set(update) - {field, "sources"} - auxiliary:
                raise ValueError("담당 에이전트가 다른 담당자 또는 제어 필드를 수정했습니다.")
            result = AnalysisResult.model_validate(update[field])
            if result.candidate_id != request.candidate_id:
                raise ValueError("분석 결과의 후보가 다릅니다.")
            ids = [item.id for item in result.indicators]
            if len(ids) != len(set(ids)) or set(ids) != required:
                raise ValueError("담당 지표가 누락되었거나 중복되었습니다.")
            new_sources = update.get("sources", [])
            merged = merge_sources(state["sources"], new_sources)
            if len(merged) > state["policy"].max_sources:
                raise ValueError("실행별 출처 저장 상한을 초과했습니다.")
            if not set(result.source_ids) <= {source.source_id for source in merged}:
                raise ValueError("등록되지 않은 출처를 반환했습니다.")
            failures.pop(owner, None)
        except Exception as exc:
            # 예외 메시지는 API 응답이나 민감한 요청 내용을 포함할 수 있어 유형만 보관한다.
            reason = f"{owner} 작업 실패({type(exc).__name__})입니다. 추가 확인이 필요합니다."
            failures[owner] = reason
            result = state.get(field) or missing_analysis(state, owner, reason)
            new_sources = []
        return {
            field: result, "sources": new_sources,
            "supervisor": control.model_copy(update={"attempts": attempts, "failures": failures}),
        }

    return worker
