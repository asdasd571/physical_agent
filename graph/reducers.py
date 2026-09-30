"""Reducers used by concurrent LangGraph State updates."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from schemas.evaluation import EvaluationRecord
    from schemas.evidence import SourceRecord


T = TypeVar("T")


def _stable_unique(values: Sequence[T]) -> list[T]:
    """Return values in first-seen order without duplicates."""

    result: list[T] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def merge_sources(
    current: list[SourceRecord],
    update: list[SourceRecord],
) -> list[SourceRecord]:
    """Merge sources by ``source_id`` and reject conflicting provenance.

    A retry may emit the same source again. Identical records are idempotent,
    but two different records must never silently share one canonical ID.
    """

    merged = list(current)
    positions = {source.source_id: index for index, source in enumerate(merged)}
    for source in update:
        index = positions.get(source.source_id)
        if index is None:
            positions[source.source_id] = len(merged)
            merged.append(source)
        elif merged[index] != source:
            raise ValueError(f"conflicting SourceRecord for source_id={source.source_id}")
    return merged


def merge_evaluations(
    current: list[EvaluationRecord],
    update: list[EvaluationRecord],
) -> list[EvaluationRecord]:
    """Keep one evaluation per candidate, replacing it on a later repair."""

    merged = list(current)
    positions = {
        evaluation.candidate_id: index
        for index, evaluation in enumerate(merged)
    }
    for evaluation in update:
        index = positions.get(evaluation.candidate_id)
        if index is None:
            positions[evaluation.candidate_id] = len(merged)
            merged.append(evaluation)
        else:
            merged[index] = evaluation
    return merged


def merge_errors(current: list[str], update: list[str]) -> list[str]:
    """Accumulate error messages idempotently in first-seen order."""

    return _stable_unique([*current, *update])
