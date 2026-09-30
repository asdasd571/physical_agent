from __future__ import annotations

from datetime import datetime, timezone
from typing import get_args, get_type_hints

import pytest

from graph.reducers import merge_errors, merge_evaluations, merge_sources
from schemas import (
    Decision,
    DecisionStatus,
    EvaluationRecord,
    GraphState,
    SourceKind,
    SourceRecord,
)


def make_source(source_id: str, *, title: str = "source") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        kind=SourceKind.WEB,
        publisher="publisher",
        title=title,
        url="https://example.com",
        collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )


def make_evaluation(candidate_id: str, *, reason: str) -> EvaluationRecord:
    return EvaluationRecord(
        candidate_id=candidate_id,
        country="KR",
        primary_segment="robotics",
        rule_version="1.0",
        decision=Decision(status=DecisionStatus.HOLD, reasons=[reason]),
    )


def test_sources_merge_parallel_results_and_ignore_identical_retry() -> None:
    first = make_source("src-a")
    second = make_source("src-b")

    merged = merge_sources([first], [second, first])

    assert [source.source_id for source in merged] == ["src-a", "src-b"]


def test_sources_reject_conflicting_record_for_same_id() -> None:
    with pytest.raises(ValueError, match="source_id=src-a"):
        merge_sources([make_source("src-a")], [make_source("src-a", title="changed")])


def test_evaluations_keep_one_record_per_candidate_and_replace_repair() -> None:
    old = make_evaluation("company-a", reason="before repair")
    repaired = make_evaluation("company-a", reason="after repair")
    other = make_evaluation("company-b", reason="first result")

    merged = merge_evaluations([old], [other, repaired])

    assert [item.candidate_id for item in merged] == ["company-a", "company-b"]
    assert merged[0].decision.reasons == ["after repair"]


def test_errors_accumulate_without_retry_duplicates() -> None:
    assert merge_errors(["timeout"], ["invalid unit", "timeout"]) == [
        "timeout",
        "invalid unit",
    ]


def test_graph_state_fields_are_wired_to_reducers() -> None:
    hints = get_type_hints(GraphState, include_extras=True)

    assert get_args(hints["sources"])[1] is merge_sources
    assert get_args(hints["evaluations"])[1] is merge_evaluations

    errors_annotated = get_args(hints["errors"])[0]
    assert get_args(errors_annotated)[1] is merge_errors
