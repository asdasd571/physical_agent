"""Small OpenAI Responses API adapter with a LangChain-like invoke contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str
    response_id: str | None = None


class OpenAIResponsesModel:
    """Expose ``invoke(messages)`` while keeping provider setup in one place."""

    def __init__(self, model: str | None = None, *, client: Any | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if client is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError(
                    "OPENAI_API_KEY가 없습니다. 환경변수에 반별 API 키를 설정하거나 "
                    "오프라인 실행에는 --skip-llm을 사용하세요."
                )
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:
                raise RuntimeError("openai 패키지가 없습니다: pip install -r requirements.txt") from exc
            client = OpenAI()
        self._client = client

    def invoke(self, messages: Sequence[dict[str, str]]) -> ModelResponse:
        response = self._client.responses.create(
            model=self.model,
            input=list(messages),
        )
        text = getattr(response, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("OpenAI Responses API가 텍스트 결과를 반환하지 않았습니다")
        return ModelResponse(content=text.strip(), response_id=getattr(response, "id", None))

    def invoke_json(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]:
        """Request JSON mode and return a decoded object without exposing raw output."""
        response = self._client.responses.create(
            model=self.model,
            input=list(messages),
            text={"format": {"type": "json_object"}},
        )
        text = getattr(response, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("OpenAI Responses API가 JSON 결과를 반환하지 않았습니다")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI JSON 응답을 해석할 수 없습니다") from exc
        if not isinstance(payload, dict):
            raise ValueError("OpenAI JSON 응답은 객체여야 합니다")
        return payload
