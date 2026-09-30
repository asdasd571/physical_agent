from typing import cast

import pytest

from graph import (
    route_after_archive,
    route_after_eligibility,
    route_after_review,
)
from schemas import (
    ControlState,
    EligibilityResult,
    EligibilityStatus,
    EvidenceReview,
    GraphState,
    RepairTarget,
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (EligibilityStatus.PASS, "tech"),
        (EligibilityStatus.FAIL, "skip"),
        (EligibilityStatus.UNKNOWN, "skip"),
    ],
)
def test_route_after_eligibility(
    status: EligibilityStatus,
    expected: str,
) -> None:
    state = cast(
        GraphState,
        {
            "eligibility": EligibilityResult(
                status=status,
                reasons=["Test result"],
            )
        },
    )

    assert route_after_eligibility(state) == expected


def test_route_after_eligibility_requires_result() -> None:
    state = cast(GraphState, {"eligibility": None})

    with pytest.raises(ValueError, match="eligibility"):
        route_after_eligibility(state)


def test_route_after_review_selects_repair() -> None:
    state = cast(
        GraphState,
        {
            "evidence_review": EvidenceReview(
                candidate_id="candidate-1",
                passed=False,
                repair_required=True,
                repair_targets=[
                    RepairTarget(
                        owner="tech",
                        indicator_ids=["K2"],
                        reason="Missing denominator",
                    )
                ],
            ),
            "control": ControlState(),
        },
    )

    assert route_after_review(state) == "repair"


@pytest.mark.parametrize(
    ("repair_required", "retry_count"),
    [(False, 0), (False, 1), (True, 1)],
)
def test_route_after_review_selects_judge(
    repair_required: bool,
    retry_count: int,
) -> None:
    repair_targets = []

    if repair_required:
        repair_targets = [
            RepairTarget(
                owner="tech",
                indicator_ids=["K2"],
                reason="Missing denominator",
            )
        ]

    state = cast(
        GraphState,
        {
            "evidence_review": EvidenceReview(
                candidate_id="candidate-1",
                passed=not repair_required,
                repair_required=repair_required,
                repair_targets=repair_targets,
            ),
            "control": ControlState(retry_count=retry_count),
        },
    )

    assert route_after_review(state) == "judge"


def test_route_after_review_requires_result() -> None:
    state = cast(GraphState, {"evidence_review": None})

    with pytest.raises(ValueError, match="evidence_review"):
        route_after_review(state)


@pytest.mark.parametrize(
    ("completed_count", "candidate_count", "expected"),
    [(0, 2, "select_candidate"), (1, 2, "select_candidate"), (2, 2, "report")],
)
def test_route_after_archive(
    completed_count: int,
    candidate_count: int,
    expected: str,
) -> None:
    state = cast(
        GraphState,
        {
            "evaluations": [object()] * completed_count,
            "candidates": [object()] * candidate_count,
        },
    )

    assert route_after_archive(state) == expected


def test_route_after_archive_rejects_excess_results() -> None:
    state = cast(
        GraphState,
        {
            "evaluations": [object(), object(), object()],
            "candidates": [object(), object()],
        },
    )

    with pytest.raises(ValueError, match="exceed"):
        route_after_archive(state)
