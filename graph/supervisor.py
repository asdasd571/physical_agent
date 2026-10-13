"""모든 담당 에이전트가 Supervisor로 돌아오는 그래프이다."""

from langgraph.graph import END, START, StateGraph

from agents.supervised import make_supervised_worker, missing_analysis
from nodes.init import init_node
from nodes.select_candidate import select_candidate_node
from nodes.judge import judge_node
from nodes.early_stage import compare_early_stage
from nodes.skip import skip_node
from nodes.review import ANALYSIS_REQUIREMENTS, validate_indicator
from nodes.supervisor import supervisor_node, route_supervisor
from nodes.report_quality import report_quality_node, route_quality, revise_report_node, finalize_node
from reporting.supervisor_report import supervisor_report_node
from schemas import Decision, DecisionStatus, EvidenceStatus, QueryStatus
from schemas.supervisor import SupervisorControl, SupervisorGraphState, SupervisorPolicy


def initialize(state):
    return {**init_node(state), "policy": state.get("policy", SupervisorPolicy()),
            "supervisor": SupervisorControl(), "routing_history": {}, "draft": None,
            "quality": None, "quality_history": [], "report_revision": 0,
            "completion_status": "running"}


def select(state):
    return {**select_candidate_node(state), "supervisor": SupervisorControl()}


def conservative_judge(state):
    # 호출 예산이 먼저 소진되어도 빠진 필드를 명시적인 NO_EVIDENCE로 채운다.
    checked = dict(state)
    source_ids = {source.source_id for source in state["sources"]}
    for owner, (field, _) in ANALYSIS_REQUIREMENTS.items():
        analysis = state.get(field) or missing_analysis(state, owner, "조사 한도에 도달하여 확인하지 못했습니다.")
        indicators = []
        for indicator in analysis.indicators:
            issues = validate_indicator(indicator, analysis.source_ids, source_ids)
            if issues and indicator.query_status == QueryStatus.SUCCESS:
                # 출처·기간·분모 등이 검증되지 않은 값으로 점수를 계산하지 않는다.
                indicator = indicator.model_copy(update={
                    "raw_value": None, "query_status": QueryStatus.NO_DATA,
                    "evidence_status": EvidenceStatus.NO_EVIDENCE,
                    "missing_reason": "; ".join(issues),
                    "source_ids": [s for s in indicator.source_ids if s in source_ids],
                })
            indicators.append(indicator)
        checked[field] = analysis.model_copy(update={"indicators": indicators})
    result = judge_node(checked)
    evaluation = result["evaluation"]
    if not state["supervisor"].evidence_sufficient:
        decision = Decision(status=DecisionStatus.HOLD, reasons=[
            *evaluation.decision.reasons, "Supervisor가 근거 충분성을 확인하지 못하여 판정을 보류합니다.",
        ])
        evaluation = evaluation.model_copy(update={"decision": decision})
        result["decision"] = decision
    result["evaluation"] = evaluation.model_copy(update={"metadata": {
        **evaluation.metadata, "evidence_sufficient": state["supervisor"].evidence_sufficient,
        "termination_reason": state["supervisor"].termination_reason,
        "technical_findings": [f.model_dump(mode="json") for f in checked["tech_analysis"].findings],
        "early_stage_comparison": compare_early_stage(evaluation.indicators, evaluation.indicator_scores,
                                                      state["run"].evaluation_date),
    }})
    return result


def make_safe_narrative(handler):
    def narrative(state):
        if handler is None:
            return {"evaluation": state["evaluation"]}
        try:
            result = handler(state)
            before = state["evaluation"].model_dump(exclude={"metadata"})
            after = result["evaluation"].model_dump(exclude={"metadata"})
            if before != after:
                raise ValueError("해설이 확정된 평가를 변경했습니다.")
            return {"evaluation": result["evaluation"]}
        except Exception as exc:
            evaluation = state["evaluation"]
            return {"evaluation": evaluation.model_copy(update={"metadata": {
                **evaluation.metadata, "narrative_error": type(exc).__name__, "narratives": [],
            }})}
    return narrative


def archive(state):
    candidate_id = state["current_candidate"].candidate_id
    return {"evaluations": [state["evaluation"]],
            "routing_history": {**state["routing_history"], candidate_id: state["supervisor"]}}


def build_supervisor_graph(bindings, *, checkpointer=None, report_handler=None, interrupt_after=None):
    graph = StateGraph(SupervisorGraphState)
    graph.add_node("init", initialize)
    graph.add_node("select_candidate", select)
    graph.add_node("supervisor", supervisor_node)
    for owner in ANALYSIS_REQUIREMENTS:
        graph.add_node(owner, make_supervised_worker(owner, getattr(bindings, owner)))
        graph.add_edge(owner, "supervisor")
    graph.add_node("judge", conservative_judge)
    graph.add_node("skip", skip_node)
    graph.add_node("narrative", make_safe_narrative(bindings.narrative))
    graph.add_node("archive", archive)
    graph.add_node("report", report_handler or supervisor_report_node)
    graph.add_node("quality", report_quality_node)
    graph.add_node("revise_report", revise_report_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "init")
    graph.add_edge("init", "select_candidate")
    graph.add_edge("select_candidate", "supervisor")
    graph.add_conditional_edges("supervisor", route_supervisor,
                               {name: name for name in (*ANALYSIS_REQUIREMENTS, "judge", "skip")})
    graph.add_edge("judge", "narrative")
    graph.add_edge("narrative", "archive")
    graph.add_edge("skip", "archive")
    graph.add_conditional_edges("archive", lambda s: "select_candidate" if len(s["evaluations"]) < len(s["candidates"]) else "report",
                               {"select_candidate": "select_candidate", "report": "report"})
    graph.add_edge("report", "quality")
    graph.add_conditional_edges("quality", route_quality,
                               {"revise_report": "revise_report", "finalize": "finalize"})
    graph.add_edge("revise_report", "report")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)
