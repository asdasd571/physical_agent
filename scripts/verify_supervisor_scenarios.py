"""통제된 결함을 주입하여 보고서 재작성과 담당자 재시도를 실증한다."""

import argparse
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.tracers.langchain import wait_for_all_tracers

from app import load_bindings, load_candidates
from agents.tech import make_tech_node
from agents.synergy import make_synergy_node
from graph.supervisor import build_supervisor_graph
from schemas import RunConfig
from schemas.supervisor import SupervisorPolicy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["quality-repair", "worker-retry"])
    parser.add_argument("--output", default="artifacts/scenarios")
    args = parser.parse_args()
    load_dotenv(override=True)
    directory = Path(args.output) / args.scenario
    directory.mkdir(parents=True, exist_ok=False)
    nodes = replace(load_bindings(), tech=make_tech_node(search=lambda **kw: []),
                    synergy=make_synergy_node(search=lambda **kw: []))
    if args.scenario == "quality-repair":
        def narrative(state):
            evaluation = state["evaluation"]
            refs = sorted({s for i in evaluation.indicators for s in i.source_ids})
            return {"evaluation": evaluation.model_copy(update={"metadata": {
                **evaluation.metadata, "controlled_fault": True,
                "narratives": [{"section": "technology", "text": "최고의 기술이므로 투자를 추천합니다.",
                                "source_ids": refs[:1]}],
            }})}
        nodes = replace(nodes, narrative=narrative)
    else:
        original, calls = nodes.tech, set()

        def tech(state):
            candidate = state["current_candidate"].candidate_id
            if candidate not in calls:
                calls.add(candidate)
                raise TimeoutError("통제된 최초 호출 장애입니다.")
            return original(state)
        nodes = replace(nodes, tech=tech)
    trace_id = uuid4()
    run_id = f"controlled-{args.scenario}"
    initial = {"run": RunConfig(run_id=run_id, evaluation_date=date(2026, 10, 13), rule_version="1.0.0",
                                document_version="1.0.0", settings={"report_output_path": str(directory / "report.pdf")}),
               "candidates": load_candidates("data/candidates.json"), "policy": SupervisorPolicy()}
    result = build_supervisor_graph(nodes).invoke(initial, {
        "run_id": trace_id, "run_name": run_id, "recursion_limit": 200,
        "metadata": {"controlled_fault": True, "scenario": args.scenario, "llm_enabled": False},
        "tags": ["supervisor", "controlled-validation"],
    })
    if args.scenario == "quality-repair":
        assert result["report_revision"] == 1
        assert not result["quality_history"][0].neutrality.passed
        assert result["quality_history"][-1].passed
    else:
        assert result["routing_history"]["arobot"].attempts["tech"] == 2
        assert "tech" not in result["routing_history"]["arobot"].failures
    payload = {"scenario": args.scenario, "controlled_fault": True, "run_id": run_id, "trace_id": str(trace_id),
               "status": result["completion_status"], "report": result["report"].output_path,
               "routing": {k: v.model_dump(mode="json") for k, v in result["routing_history"].items()},
               "quality_history": [q.model_dump(mode="json") for q in result["quality_history"]]}
    (directory / "run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    wait_for_all_tracers()
    print(json.dumps({"scenario": args.scenario, "trace_id": str(trace_id), "status": payload["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
