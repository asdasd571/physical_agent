from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from agents.narrative import make_narrative_node
from llm import OpenAIResponsesModel
from schemas import (
    Candidate, Decision, DecisionStatus, EvaluationRecord, EvidenceStatus,
    IndicatorEvidence, QueryStatus, RunConfig, SourceKind, SourceRecord,
)


class FakeResponses:
    def __init__(self, output_text: str):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text, id="resp-test")


def test_openai_adapter_uses_responses_api_messages() -> None:
    responses = FakeResponses('{"ok":true}')
    model = OpenAIResponsesModel("test-model", client=SimpleNamespace(responses=responses))
    result = model.invoke([{"role": "user", "content": "JSON"}])
    assert result.content == '{"ok":true}'
    assert responses.calls[0]["model"] == "test-model"


def test_openai_adapter_forces_json_mode() -> None:
    responses = FakeResponses('{"candidate_id":"c1","records":[],"coverage":[]}')
    model = OpenAIResponsesModel("test-model", client=SimpleNamespace(responses=responses))
    payload = model.invoke_json([{"role": "user", "content": "JSON으로 반환"}])
    assert payload["candidate_id"] == "c1"
    assert responses.calls[0]["text"] == {"format": {"type": "json_object"}}


def test_extractor_accepts_fenced_json_from_non_openai_model() -> None:
    from agents.tech import make_llm_extractor
    candidate = Candidate(candidate_id="c", legal_name="C", country="KR", legal_id="1",
        founded_at=date(2020, 1, 1), primary_segment="x", latest_round="Seed",
        listing_sources=["x"], registry_sources=["y"])
    model = SimpleNamespace(invoke=lambda messages: SimpleNamespace(
        content='```json\n{"candidate_id":"c","records":[],"coverage":[]}\n```'))
    assert make_llm_extractor(model)("JSON", [], candidate)["candidate_id"] == "c"


def test_narrative_keeps_score_and_decision_and_only_adds_cited_text() -> None:
    source = SourceRecord(source_id="s1", kind=SourceKind.WEB, publisher="P", title="T",
        url="https://example.com", collected_at=datetime.now(timezone.utc), evidence_excerpt="근거")
    indicator = IndicatorEvidence(id="T1", raw_value=1, evidence_status=EvidenceStatus.THIRD_PARTY_VERIFIED,
        source_ids=["s1"], collected_by="discover", query_status=QueryStatus.SUCCESS)
    evaluation = EvaluationRecord(candidate_id="c1", country="KR", primary_segment="robot_hand",
        rule_version="1", indicators=[indicator], total_score=Decimal("70"),
        decision=Decision(status=DecisionStatus.INVEST, reasons=["규칙 판정"]), metadata={})
    model = SimpleNamespace(model="fake", invoke=lambda messages: SimpleNamespace(content=(
        '{"narratives":[{"section":"핵심 판단","text":"근거 기반 해설","source_ids":["s1"]}]}'
    )))
    state = {"evaluation": evaluation, "current_candidate": Candidate(candidate_id="c1", legal_name="C",
        country="KR", legal_id="1", founded_at=date(2020, 1, 1), primary_segment="robot_hand",
        latest_round="Series A", listing_sources=["x"], registry_sources=["y"]), "sources": [source],
        "run": RunConfig(run_id="r", evaluation_date=date.today(), rule_version="1", document_version="1")}
    updated = make_narrative_node(model)(state)["evaluation"]
    assert updated.total_score == evaluation.total_score
    assert updated.decision == evaluation.decision
    assert updated.metadata["narratives"][0]["source_ids"] == ["s1"]
    assert updated.metadata["narratives"][0]["section"] == "business"


def test_narrative_drops_invented_source_without_changing_evaluation() -> None:
    model = SimpleNamespace(model="fake", invoke=lambda messages: SimpleNamespace(content=(
        '{"narratives":[{"section":"위험","text":"x","source_ids":["invented"]}]}'
    )))
    candidate = Candidate(candidate_id="c", legal_name="C", country="KR", legal_id="1",
        founded_at=date(2020, 1, 1), primary_segment="x", latest_round="Seed",
        listing_sources=["x"], registry_sources=["y"])
    evaluation = EvaluationRecord(candidate_id="c", country="KR", primary_segment="x", rule_version="1",
        decision=Decision(status=DecisionStatus.HOLD, reasons=["자료 없음"]))
    updated = make_narrative_node(model)({"evaluation": evaluation, "current_candidate": candidate, "sources": []})["evaluation"]
    assert updated.metadata["narratives"] == []
    assert updated.decision == evaluation.decision


def test_extractor_sanitizer_drops_records_without_registered_sources() -> None:
    from agents.tech import _sanitize_extracted_payload
    payload = {"candidate_id": "c", "records": [
        {"kind": "trial", "source_ids": []},
        {"kind": "trial", "source_ids": ["invented"]},
        {"kind": "trial", "source_ids": ["valid"]},
    ], "coverage": [{"indicator_id": "K2"}]}
    cleaned = _sanitize_extracted_payload(payload, {"valid": {}}, "c")
    assert cleaned["records"] == [{"kind": "trial", "source_ids": ["valid"]}]
    assert cleaned["coverage"] == []
