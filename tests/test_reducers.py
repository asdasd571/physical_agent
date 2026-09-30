from datetime import datetime, timezone

import pytest

from graph.reducers import merge_evaluations, merge_sources
from schemas import (
    Decision,
    DecisionStatus,
    EvaluationRecord,
    SourceKind,
    SourceRecord,
)


def make_source(
    source_id: str = "source-1",
    title: str = "Test source",
) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        kind=SourceKind.WEB,
        publisher="Test publisher",
        title=title,
        url="https://example.com/source",
        collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )


def make_evaluation(
    candidate_id: str = "candidate-1",
    status: DecisionStatus = DecisionStatus.HOLD,
) -> EvaluationRecord:
    return EvaluationRecord(
        candidate_id=candidate_id,
        country="KR",
        primary_segment="robot-hand",
        rule_version="1.0.0",
        decision=Decision(
            status=status,
            reasons=["Test decision"],
        ),
    )


def test_merge_sources_preserves_order_and_removes_identical_duplicates() -> None:
    first = make_source("source-1")
    second = make_source("source-2")

    result = merge_sources([first], [first, second])

    assert result == [first, second]


def test_merge_sources_rejects_conflicting_duplicate_ids() -> None:
    current = make_source("source-1", "Original title")
    incoming = make_source("source-1", "Changed title")

    with pytest.raises(ValueError, match="source-1"):
        merge_sources([current], [incoming])


def test_merge_evaluations_removes_identical_duplicates() -> None:
    evaluation = make_evaluation()

    result = merge_evaluations([evaluation], [evaluation])

    assert result == [evaluation]


def test_merge_evaluations_rejects_conflicting_candidate_results() -> None:
    current = make_evaluation(status=DecisionStatus.HOLD)
    incoming = make_evaluation(status=DecisionStatus.INVEST)

    with pytest.raises(ValueError, match="candidate-1"):
        merge_evaluations([current], [incoming])


def test_reducers_accept_empty_values() -> None:
    assert merge_sources(None, None) == []
    assert merge_evaluations(None, None) == []
