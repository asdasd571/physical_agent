from __future__ import annotations

import argparse
import json
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4

from graph.builder import NodeBindings, build_graph
from rag import (
    BgeM3Embedder,
    KiwiTechnicalTokenizer,
    configure_search_backend,
    load_hybrid_retriever,
)
from schemas import Candidate, RunConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="data/candidates.json")
    parser.add_argument("--index", default="data/rag/index")
    parser.add_argument("--rule-version", default="1.0.0")
    parser.add_argument("--document-version", default="1.0.0")
    parser.add_argument("--skip-rag", action="store_true")
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


def load_bindings() -> NodeBindings:
    return NodeBindings(
        discover=load_node("agents.discover", "discover_node"),
        tech=load_node("agents.tech", "tech_node"),
        market=load_node("agents.market", "market_node"),
        competitor=load_node("agents.competitor", "competitor_node"),
        synergy=load_node("agents.synergy", "synergy_node"),
        report=load_node("agents.report", "report_node"),
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
    candidates = load_candidates(args.candidates)

    if not args.skip_rag:
        configure_rag(args.index)

    graph = build_graph(load_bindings())
    initial_state = {
        "run": RunConfig(
            run_id=str(uuid4()),
            evaluation_date=date.today(),
            rule_version=args.rule_version,
            document_version=args.document_version,
        ),
        "candidates": candidates,
    }
    return graph.invoke(initial_state)


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


def main() -> None:
    result = run(parse_args())
    print_result(result)


if __name__ == "__main__":
    main()
