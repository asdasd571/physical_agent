"""LLM evidence synthesis after deterministic scoring and before archival."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemas import EvaluationRecord, GraphState


ROOT = Path(__file__).resolve().parents[1]


def make_narrative_node(model: Any | None):
    def node(state: GraphState) -> dict[str, EvaluationRecord]:
        evaluation = state.get("evaluation")
        candidate = state.get("current_candidate")
        if evaluation is None or candidate is None:
            raise ValueError("narrative requires current_candidate and evaluation")
        if model is None:
            return {"evaluation": evaluation}

        used_ids = {
            source_id
            for indicator in evaluation.indicators
            for source_id in indicator.source_ids
        } | {
            source_id
            for gate in evaluation.gates.values()
            for source_id in gate.source_ids
        }
        sources = [
            {
                "source_id": source.source_id,
                "title": source.title,
                "page": source.page,
                "excerpt": source.evidence_excerpt,
            }
            for source in state.get("sources", [])
            if source.source_id in used_ids
        ]
        prompt = (ROOT / "prompts" / "report.md").read_text(encoding="utf-8")
        prompt += (
            "\nJSON만 반환한다. 형식: {\"narratives\":["
            "{\"section\":\"business|technology|market|risk\",\"text\":\"...\","
            "\"source_ids\":[\"...\"]}]}. 후보별 핵심 해설 1개만, text는 240자 이내로 작성하며 입력 source_id만 인용한다. "
            "점수, Gate, INVEST/HOLD를 변경하지 않는다. 자료 없음은 추정하지 않는다."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps({
                "candidate": candidate.model_dump(mode="json"),
                "evaluation": evaluation.model_dump(mode="json"),
                "sources": sources,
            }, ensure_ascii=False)},
        ]
        if hasattr(model, "invoke_json"):
            payload = model.invoke_json(messages)
        else:
            response = model.invoke(messages)
            content = response.content if hasattr(response, "content") else response
            try:
                payload = json.loads(content)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("narrative LLM output must be a JSON object") from exc
        narratives = payload.get("narratives") if isinstance(payload, dict) else None
        if not isinstance(narratives, list):
            narratives = []
        valid_narratives = []
        section_aliases = {
            "핵심 판단": "business", "사업": "business", "강점": "technology",
            "기술": "technology", "시장": "market", "위험": "risk",
            "위험 및 실사": "risk",
        }
        for item in narratives[:1]:
            if not isinstance(item, dict) or not isinstance(item.get("section"), str) or not isinstance(item.get("text"), str):
                continue
            refs = item.get("source_ids")
            if not isinstance(refs, list) or not refs or not set(refs) <= used_ids:
                continue
            section = section_aliases.get(item["section"], item["section"])
            if section not in {"business", "technology", "market", "risk"}:
                continue
            valid_narratives.append({**item, "section": section, "text": item["text"][:240]})
        narratives = valid_narratives
        metadata = {**evaluation.metadata, "narratives": narratives, "llm_model": getattr(model, "model", "configured")}
        return {"evaluation": evaluation.model_copy(update={"metadata": metadata})}

    return node
