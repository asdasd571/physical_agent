from __future__ import annotations

from schemas import EvaluationRecord, SourceRecord


def merge_sources(
    current: list[SourceRecord] | None,
    incoming: list[SourceRecord] | None,
) -> list[SourceRecord]:

    merged: dict[str, SourceRecord] = {}

    for source in [*(current or []), *(incoming or [])]:
        existing = merged.get(source.source_id)

        if existing is not None and existing != source:
            raise ValueError(
                f"source_id={source.source_id!r}"
            )

        merged[source.source_id] = source

    return list(merged.values())


def merge_evaluations(
    current: list[EvaluationRecord] | None,
    incoming: list[EvaluationRecord] | None,
) -> list[EvaluationRecord]:

    merged: dict[str, EvaluationRecord] = {}

    for evaluation in [*(current or []), *(incoming or [])]:
        existing = merged.get(evaluation.candidate_id)

        if existing is not None and existing != evaluation:
            raise ValueError(
                f"candidate_id={evaluation.candidate_id!r}"
            )

        merged[evaluation.candidate_id] = evaluation

    return list(merged.values())
