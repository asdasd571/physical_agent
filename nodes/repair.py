from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from schemas import ControlState, GraphState


RepairHandler = Callable[[GraphState], dict[str, Any]]


def make_repair_node(
    handlers: Mapping[str, RepairHandler],
) -> RepairHandler:
    def repair_node(state: GraphState) -> dict[str, Any]:
        review = state["evidence_review"]

        if review is None:
            raise ValueError("근거 검증 결과가 없습니다")

        if not review.repair_required:
            raise ValueError("보완이 필요한 항목이 없습니다")

        if state["control"].retry_count >= 1:
            raise ValueError("후보별 보완 횟수를 초과했습니다")

        owners = list(dict.fromkeys(target.owner for target in review.repair_targets))
        repaired_indicator_ids = list(
            dict.fromkeys(
                indicator_id
                for target in review.repair_targets
                for indicator_id in target.indicator_ids
            )
        )
        update: dict[str, Any] = {}
        sources: list[Any] = []

        for owner in owners:
            handler = handlers.get(owner)

            if handler is None:
                raise ValueError(f"보완 처리 함수를 찾을 수 없습니다: {owner}")

            handler_update = handler(state)

            for key, value in handler_update.items():
                if key == "sources":
                    sources.extend(value)
                    continue

                if key in update and update[key] != value:
                    raise ValueError(f"보완 결과 필드가 충돌했습니다: {key}")

                update[key] = value

        if sources:
            update["sources"] = sources

        update["control"] = ControlState(
            retry_count=state["control"].retry_count + 1,
            repaired_indicator_ids=repaired_indicator_ids,
        )
        return update

    return repair_node
