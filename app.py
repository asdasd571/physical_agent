from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from graph.builder import NodeBindings, build_graph
from agents.narrative import make_narrative_node
from agents.synergy import make_synergy_node
from agents.tech import make_llm_extractor, make_tech_node
from llm import OpenAIResponsesModel
from rag import (
    BgeM3Embedder,
    KiwiTechnicalTokenizer,
    configure_search_backend,
    load_hybrid_retriever,
)
from schemas import Candidate, RunConfig
from schemas.supervisor import SupervisorPolicy
from graph.supervisor import build_supervisor_graph
from graph.checkpoints import sqlite_checkpointer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="data/candidates.json")
    parser.add_argument("--index", default="data/rag/index")
    parser.add_argument("--rule-version", default="1.0.0")
    parser.add_argument("--document-version", default="1.0.0")
    parser.add_argument("--skip-rag", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--report-output", default=None)
    parser.add_argument("--workflow", choices=["supervisor", "legacy"], default="supervisor")
    parser.add_argument("--evaluation-date", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Asia/Seoul")).date())
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--max-report-revisions", type=int, default=2)
    return parser.parse_args()


def load_candidates(path: str | Path) -> list[Candidate]:
    candidate_path = Path(path)

    if not candidate_path.is_file():
        raise FileNotFoundError(f"후보 파일을 찾을 수 없습니다: {candidate_path}")

    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    records = payload.get("candidates") if isinstance(payload, dict) else payload

    if not isinstance(records, list):
        raise ValueError("후보 파일은 배열 또는 candidates 배열을 포함한 객체여야 합니다")

    return [Candidate.model_validate(record) for record in records]


def load_node(module_name: str, function_name: str):
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as error:
        raise RuntimeError(f"Agent 모듈을 찾을 수 없습니다: {module_name}") from error

    try:
        return getattr(module, function_name)
    except AttributeError as error:
        raise RuntimeError(
            f"Agent 함수를 찾을 수 없습니다: {module_name}.{function_name}"
        ) from error


def load_bindings(model=None) -> NodeBindings:
    extractor = make_llm_extractor(model) if model is not None else None
    return NodeBindings(
        discover=load_node("agents.discover", "discover_node"),
        tech=make_tech_node(extractor=extractor),
        market=load_node("agents.market", "market_node"),
        competitor=load_node("agents.competitor", "competitor_node"),
        synergy=make_synergy_node(extractor=extractor),
        report=load_node("agents.report", "report_node"),
        narrative=make_narrative_node(model),
    )


def configure_rag(index_directory: str) -> None:
    embedder = BgeM3Embedder()
    tokenizer = KiwiTechnicalTokenizer()
    retriever = load_hybrid_retriever(
        index_directory,
        embedder=embedder,
        sparse_tokenizer=tokenizer,
    )
    configure_search_backend(retriever)


def run(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(override=True)
    candidates = load_candidates(args.candidates)

    if not args.skip_rag:
        configure_rag(args.index)

    model = None if args.skip_llm else OpenAIResponsesModel(model=args.llm_model)
    run_id = args.run_id or str(uuid4())
    # 실행 ID는 로컬 경로에도 사용한다.
    if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
        raise ValueError("run-id에는 영문, 숫자, 하이픈, 밑줄만 사용할 수 있습니다.")
    settings = {"report_output_path": args.report_output} if args.report_output else {}
    settings.update(skip_rag=args.skip_rag, skip_llm=args.skip_llm)
    initial_state = {
        "run": RunConfig(
            run_id=run_id,
            evaluation_date=args.evaluation_date,
            rule_version=args.rule_version,
            document_version=args.document_version,
            settings=settings,
        ),
        "candidates": candidates,
    }
    if args.workflow == "legacy":
        return build_graph(load_bindings(model)).invoke(initial_state, {"recursion_limit": 200})
    if args.resume and not args.run_id:
        raise ValueError("재개할 때는 --run-id가 필요합니다.")
    directory = Path(args.artifacts) / run_id
    if not args.resume and directory.exists():
        raise FileExistsError("같은 run-id의 실행이 있습니다. --resume 또는 새 run-id를 사용하십시오.")
    directory.mkdir(parents=True, exist_ok=True)
    if not args.report_output:
        settings["report_output_path"] = str(directory / "report.pdf")
    initial_state["run"] = initial_state["run"].model_copy(update={"settings": settings})
    initial_state["policy"] = SupervisorPolicy(max_attempts_per_agent=args.max_attempts,
                                               max_report_revisions=args.max_report_revisions)
    trace_id = uuid4()
    config = {"configurable": {"thread_id": run_id}, "run_id": trace_id,
              "run_name": "physical-agent-supervisor", "recursion_limit": 400,
              "metadata": {"run_id": run_id, "workflow": "supervisor", "offline": args.skip_llm,
                           "rag_enabled": not args.skip_rag}, "tags": ["supervisor", "course-assignment"]}
    with sqlite_checkpointer(directory / "checkpoints.sqlite") as saver:
        graph = build_supervisor_graph(load_bindings(model), checkpointer=saver)
        previous = graph.get_state(config) if args.resume else None
        if args.resume and not previous.values:
            raise ValueError("저장된 실행을 찾을 수 없습니다.")
        if previous and previous.values:
            old_run = previous.values["run"]
            for key in ("skip_rag", "skip_llm"):
                if old_run.settings.get(key) != settings[key]:
                    raise ValueError("재개 시 RAG/LLM 실행 모드를 기존 실행과 동일하게 지정해야 합니다.")
            if not previous.next:
                return previous.values
        with (directory / "events.jsonl").open("a", encoding="utf-8") as log:
            for event in graph.stream(None if args.resume else initial_state, config, stream_mode="updates"):
                for name, update in event.items():
                    record = {"run_id": run_id, "trace_id": str(trace_id), "node": name}
                    if name == "supervisor":
                        record["decision"] = update["supervisor"].decisions[-1].model_dump(mode="json")
                    elif name == "quality":
                        record["quality"] = update["quality"].model_dump(mode="json")
                    log.write(json.dumps(record, ensure_ascii=False) + "\n")
                    log.flush()
                    print(f"[{run_id}] {name}", flush=True)
        result = graph.get_state(config).values
    manifest = {"run_id": run_id, "trace_id": str(trace_id), "status": result["completion_status"],
                "report": result["report"].output_path,
                "routing": {k: v.model_dump(mode="json") for k, v in result["routing_history"].items()},
                "quality": result["quality"].model_dump(mode="json")}
    (directory / "run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    from langchain_core.tracers.langchain import wait_for_all_tracers
    wait_for_all_tracers()
    return result


def print_result(result: dict[str, Any]) -> None:
    for index, evaluation in enumerate(result["evaluations"], start=1):
        score = evaluation.total_score if evaluation.total_score is not None else "미평가"
        print(
            f"[{index}/{len(result['evaluations'])}] "
            f"{evaluation.candidate_id}: {evaluation.decision.status.value} ({score})"
        )

    report = result.get("report")
    if report is not None:
        print(f"보고서: {report.output_path}")
    if "completion_status" in result:
        print(f"보고서 품질: {result['completion_status']}")


def main() -> None:
    result = run(parse_args())
    print_result(result)
    if result.get("completion_status") == "quality_failed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
