from dataclasses import replace
from datetime import date
from pathlib import Path

import pymupdf
import pytest

import test_graph_flow as fixture
from graph.builder import NodeBindings
from graph.checkpoints import sqlite_checkpointer
from graph.supervisor import build_supervisor_graph, initialize, select
from nodes.supervisor import supervisor_node
from nodes.report_quality import report_quality_node
from reporting.supervisor_report import supervisor_report_node
from schemas import RunConfig, EvidenceStatus, QueryStatus
from schemas.supervisor import SupervisorControl, SupervisorPolicy


SECOND_SOURCE = fixture.SOURCE.model_copy(update={"source_id": "source-2", "publisher": "Independent institute"})


def market(state):
    update = fixture.market_node(state)
    analysis = update["market_analysis"]
    update["market_analysis"] = analysis.model_copy(update={
        "source_ids": [SECOND_SOURCE.source_id],
        "indicators": [i.model_copy(update={"source_ids": [SECOND_SOURCE.source_id]}) for i in analysis.indicators],
    })
    update["sources"] = [SECOND_SOURCE]
    return update


def bindings():
    return NodeBindings(discover=fixture.discover_node, tech=fixture.tech_node, market=market,
                        competitor=fixture.competitor_node, synergy=fixture.synergy_node,
                        report=fixture.report_node)


def initial(tmp_path, **policy):
    return {"run": RunConfig(run_id="test-run", evaluation_date=date(2026, 10, 13),
                             rule_version="1.0.0", document_version="1.0.0",
                             settings={"report_output_path": str(tmp_path / "report.pdf")}),
            "candidates": fixture.candidates(), "policy": SupervisorPolicy(**policy)}


def execute(tmp_path, node_bindings=None, **kwargs):
    return build_supervisor_graph(node_bindings or bindings(), **kwargs).invoke(initial(tmp_path), {"recursion_limit": 200})


def test_dynamic_repair_gate_skip_and_real_pdf(tmp_path):
    result = execute(tmp_path)
    first = result["routing_history"]["candidate-1"]
    second = result["routing_history"]["candidate-2"]
    assert first.attempts["tech"] == 2
    assert first.evidence_sufficient
    assert first.termination_reason == "evidence_sufficient"
    assert second.attempts == {"discover": 1}
    assert second.termination_reason == "ineligible"
    assert result["completion_status"] == "passed"
    assert len(result["draft"].sections) == 8
    assert result["quality"].passed
    with pymupdf.open(result["report"].output_path) as pdf:
        assert 6 <= len(pdf) <= 10
        assert "SUMMARY" in pdf[0].get_text()
        assert "REFERENCE" in pdf[-1].get_text()


def test_choice_changes_with_existing_evidence(tmp_path):
    state = initial(tmp_path)
    state.update(initialize(state))
    state.update(select(state))
    state.update(fixture.discover_node(state))
    assert supervisor_node(state)["supervisor"].next_node == "tech"
    state.update(fixture.tech_node(state))
    state["supervisor"] = SupervisorControl(attempts={"discover": 1, "tech": 1})
    assert supervisor_node(state)["supervisor"].next_node == "synergy"
    state.update(fixture.synergy_node(state))
    state["supervisor"] = SupervisorControl(attempts={"discover": 1, "tech": 1, "synergy": 1})
    assert supervisor_node(state)["supervisor"].next_node == "competitor"


def test_workers_cannot_read_siblings_or_modify_control(tmp_path):
    original = bindings()

    def isolated(state):
        assert state["market_analysis"] is None
        assert state["synergy_analysis"] is None
        assert "supervisor" not in state
        return {**fixture.competitor_node(state), "candidate_index": 100}

    result = execute(tmp_path, replace(original, competitor=isolated))
    control = result["routing_history"]["candidate-1"]
    assert control.attempts["competitor"] == 2
    assert "competitor" in control.failures
    assert control.termination_reason == "evidence_exhausted"
    assert result["evaluations"][0].decision.status.value == "HOLD"
    assert len(result["evaluations"]) == 2


def test_timeout_retries_then_recovers(tmp_path):
    calls = 0

    def flaky(state):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("sensitive request should not appear in state")
        return fixture.tech_node(state)

    result = execute(tmp_path, replace(bindings(), tech=flaky))
    assert calls == 2
    assert not result["routing_history"]["candidate-1"].failures
    assert result["routing_history"]["candidate-1"].evidence_sufficient


def test_permanent_failure_stops_without_fabricating_evidence(tmp_path):
    def broken(state):
        raise RuntimeError("token=not-for-logging")

    result = execute(tmp_path, replace(bindings(), tech=broken))
    first = result["routing_history"]["candidate-1"]
    assert first.attempts["tech"] == 2
    assert first.termination_reason == "evidence_exhausted"
    assert "not-for-logging" not in str(first)
    evaluation = result["evaluations"][0]
    assert evaluation.decision.status.value == "HOLD"
    assert all(i.raw_value is None for i in evaluation.indicators if i.collected_by == "tech")


def test_quality_failure_rewrites_and_rechecks(tmp_path):
    def bad_narrative(state):
        evaluation = state["evaluation"]
        return {"evaluation": evaluation.model_copy(update={"metadata": {
            **evaluation.metadata, "narratives": [{"section": "technology", "text": "최고의 기술이므로 투자를 추천합니다.",
                                                   "source_ids": [fixture.SOURCE.source_id]}],
        }})}

    result = execute(tmp_path, replace(bindings(), narrative=bad_narrative))
    assert result["report_revision"] == 1
    assert len(result["quality_history"]) == 2
    assert not result["quality_history"][0].neutrality.passed
    assert result["quality_history"][1].passed
    assert Path(result["report"].output_path).name == "report.r1.pdf"
    assert (tmp_path / "report.r0.pdf").is_file()


def test_persistent_quality_failure_is_not_reported_as_success(tmp_path):
    result = execute(tmp_path, replace(bindings(), market=fixture.market_node))
    assert result["completion_status"] == "quality_failed"
    assert result["report_revision"] == 2
    assert len(result["quality_history"]) == 3
    assert not result["quality"].bias_control.passed


def test_artifact_tampering_is_detected(tmp_path):
    result = execute(tmp_path)
    path = Path(result["report"].output_path)
    path.write_bytes(path.read_bytes() + b"modified")
    assert not report_quality_node(result)["quality"].artifact.passed


def test_missing_perspective_and_unknown_citation_are_detected(tmp_path):
    result = execute(tmp_path)
    sections = result["draft"].sections[1:]
    sections[0] = sections[0].model_copy(update={"source_ids": ["invented"]})
    result["draft"] = result["draft"].model_copy(update={"sections": sections})
    quality = report_quality_node(result)["quality"]
    assert not quality.perspective_coverage.passed
    assert not quality.groundedness.passed


def test_sqlite_resume_does_not_repeat_completed_workers(tmp_path):
    calls = []

    def discover(state):
        calls.append(state["current_candidate"].candidate_id)
        return fixture.discover_node(state)

    config = {"configurable": {"thread_id": "resume-test"}, "recursion_limit": 200}
    nodes = replace(bindings(), discover=discover)
    with sqlite_checkpointer(tmp_path / "checkpoint.sqlite") as saver:
        graph = build_supervisor_graph(nodes, checkpointer=saver, interrupt_after=["discover"])
        graph.invoke(initial(tmp_path), config)
        assert graph.get_state(config).next == ("supervisor",)
    with sqlite_checkpointer(tmp_path / "checkpoint.sqlite") as saver:
        graph = build_supervisor_graph(nodes, checkpointer=saver)
        result = graph.invoke(None, config)
    assert calls == ["candidate-1", "candidate-2"]
    assert result["completion_status"] == "passed"


def test_dispatch_limit_produces_bounded_hold(tmp_path):
    result = build_supervisor_graph(bindings()).invoke(
        initial(tmp_path, max_dispatches_per_candidate=5), {"recursion_limit": 200})
    first = result["routing_history"]["candidate-1"]
    assert first.dispatch_count == 5
    assert first.termination_reason == "evidence_exhausted"
    assert result["evaluations"][0].decision.status.value == "HOLD"


def test_repository_agents_obey_adapter_contract(tmp_path):
    from app import load_bindings, load_candidates
    from agents.tech import make_tech_node
    from agents.synergy import make_synergy_node

    nodes = replace(load_bindings(), tech=make_tech_node(search=lambda **kw: []),
                    synergy=make_synergy_node(search=lambda **kw: []))
    state = initial(tmp_path)
    state["candidates"] = load_candidates(Path(__file__).resolve().parents[1] / "data/candidates.json")
    result = build_supervisor_graph(nodes).invoke(state, {"recursion_limit": 200})
    assert len(result["evaluations"]) == 3
    assert all(not control.failures for control in result["routing_history"].values())
    assert result["routing_history"]["arobot"].attempts["tech"] == 2
    assert result["routing_history"]["figure_ai"].termination_reason == "ineligible"
    assert result["completion_status"] == "passed"
