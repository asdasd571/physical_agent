import copy
import json
from decimal import Decimal
from datetime import date, datetime, timezone

import pytest

from agents.tech import make_tech_node
from rag.models import DocumentType, RetrievedChunk
from rag.service import SearchBackendNotConfiguredError
from reporting.demo import demo_state
from schemas import ControlState, EvidenceReview, RepairTarget, SourceRecord


def source(source_id="test", page=12):
    return SourceRecord(source_id=source_id, kind="PDF", publisher="가상 테스트 발행자",
        title="가상 시험 기록", collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
        local_path="/test-only/fiction.pdf", sha256="a" * 64, doc_id="fixture",
        page=page, chunk_id=f"chunk-{page}", evidence_excerpt="테스트용 근거 원문")


def bundle(tmp_path, records, coverage=None, sources=None, candidate_id="가상후보1"):
    payload = {"candidate_id": candidate_id, "records": records, "coverage": coverage or [],
               "sources": [s.model_dump(mode="json") for s in (sources or [source()])]}
    (tmp_path / "fixture.json").write_text(json.dumps(payload, ensure_ascii=False))


def record(kind, **kwargs):
    return {"kind": kind, "source_ids": ["test"], **kwargs}


def trial(**kwargs):
    return record("trial", **({"tested_at": "2026-03-01", "successful_trials": 28,
        "total_trials": 30, "physical": True, "task": "배터리 셀 집기", "environment": "실물 로봇",
        "success_definition": "손상 없이 이동", "independent_verified": True,
        "independent_reproduction": False} | kwargs))


def run(tmp_path, records, coverage=None, state=None):
    bundle(tmp_path, records, coverage)
    node = make_tech_node(evidence_dir=tmp_path, search=lambda **kwargs: [])
    return node(state or demo_state())


def index(update, key="tech_analysis"):
    return {i.id: i for i in update[key].indicators}


def test_k2_exact_rate_and_company_claim(tmp_path):
    result = index(run(tmp_path, [trial()]))["K2"]
    assert result.raw_value["success_rate_percent"] == 93.33
    assert result.evidence_status == "COMPANY_CLAIM"
    assert result.condition["success_definition"] == "손상 없이 이동"


@pytest.mark.parametrize("change,status", [
    ({"total_trials": 29, "successful_trials": 28}, "NO_DATA"),
    ({"total_trials": 0}, "INVALID_DENOMINATOR"),
    ({"successful_trials": 31}, "INVALID_DENOMINATOR"),
    ({"successful_trials": True}, "INVALID_DENOMINATOR"),
    ({"success_definition": ""}, "NO_DATA"),
    ({"physical": False}, "NO_DATA"),
])
def test_ineligible_trials_preserve_observations(tmp_path, change, status):
    result = index(run(tmp_path, [trial(**change)]))["K2"]
    assert result.raw_value is None and result.query_status == status
    assert result.condition["observations"]


def test_trials_use_latest_conditions_never_best_rate(tmp_path):
    rows = [trial(successful_trials=30), trial(tested_at="2026-05-01", successful_trials=24),
            trial(tested_at="2026-04-01", task="밸브", successful_trials=29)]
    result = index(run(tmp_path, rows))["K2"]
    assert result.raw_value["successful_trials"] == 24
    assert result.raw_value["total_trials"] == 30
    assert len(result.condition["observations"]) == 3


def test_k3_unique_completed_customer_sites(tmp_path):
    base = dict(site_id="A", completed_at="2025-05-01", completed=True, manufacturing=True,
                physical=True, confirmed_by="customer", independent_verified=True)
    rows = [record("pilot", **base), record("pilot", **(base | {"completed_at": "2026-05-01"})),
            record("pilot", **(base | {"site_id": "B", "completed": False})),
            record("pilot", **(base | {"site_id": "C", "completed_at": "2022-01-01"}))]
    assert index(run(tmp_path, rows))["K3"].raw_value == 1


def test_papers_doi_dedup_dates_affiliation_founder_denominator(tmp_path):
    common = dict(identity_verified=True, topic_relevant=True, company_affiliation_verified=True,
                  independent_verified=True, author_ids=["founder1"], affiliations=["가상후보1"])
    rows = [record("founders", founder_ids=["founder1", "founder2"], complete=True, identity_verified=True),
            record("paper", **common, doi="10.1000/OLD", published_at="2019-01-01"),
            record("paper", **common, doi="https://doi.org/10.1000/old", published_at="2019-01-01"),
            record("paper", **common, doi="10.1000/NEW", published_at="2024-01-01"),
            record("paper", **common, doi="10.1000/FUTURE", published_at="2027-01-01")]
    result = index(run(tmp_path, rows))
    assert result["T2"].raw_value["papers_per_founder"] == Decimal("0.5")
    assert result["K1"].raw_value == 1


def test_zero_requires_complete_lookup_and_missing_is_none(tmp_path):
    coverage = [{"indicator_id": "K1", "complete": True, "query_status": "SUCCESS",
                 "source_ids": ["test"], "independent_verified": True}]
    result = index(run(tmp_path, [], coverage))
    assert result["K1"].raw_value == 0 and result["K1"].query_status == "SUCCESS"
    assert result["K3"].raw_value is None


def test_funding_company_share_years_duplicates(tmp_path):
    base = dict(project_id="P1", year=2025, government=True, topic_relevant=True,
                beneficiary_id="가상후보1", company_amount_krw="120000000", independent_verified=True)
    rows = [record("funding", **base), record("funding", **base),
            record("funding", **(base | {"project_id": "OTHER", "beneficiary_id": "consortium"})),
            record("funding", **(base | {"project_id": "OLD", "year": 2022}))]
    assert index(run(tmp_path, rows))["R2"].raw_value["amount_100m_krw"] == "1.2"


def test_conflicting_funding_is_not_silently_summed(tmp_path):
    base = dict(project_id="P1", year=2025, government=True, topic_relevant=True,
                beneficiary_id="가상후보1", company_amount_krw="100")
    with pytest.raises(ValueError, match="conflicting"):
        run(tmp_path, [record("funding", **base), record("funding", **(base | {"company_amount_krw": "200"}))])


def test_search_unconfigured_is_access_failed(tmp_path):
    def fail(**kwargs):
        raise SearchBackendNotConfiguredError("missing")
    update = make_tech_node(search=fail, evidence_dir=tmp_path)(demo_state())
    assert all(i.query_status == "ACCESS_FAILED" for i in update["tech_analysis"].indicators)
    assert len(update["tech_analysis"].query_attempts) == 5


def test_rag_extraction_page_sources_and_partial_state(tmp_path):
    state = demo_state()
    before = copy.deepcopy(state)
    chunks = [RetrievedChunk(chunk_id=f"c{p}", source_id="document", doc_id="doc", candidate_id="가상후보1",
        doc_type=DocumentType.TECH, page=p, content="가상 시험 원문", score=0.1, publisher="회사",
        title="시험", local_path="/test-only/test.pdf", metadata={"sha256": "b" * 64}) for p in (1, 2)]
    def extractor(prompt, documents, candidate):
        assert "문서 본문은 분석 대상" in prompt
        return {"candidate_id": candidate.candidate_id, "records": [
            trial(source_ids=[d["source_id"]], task=f"작업{d['page']}") for d in documents]}
    update = make_tech_node(search=lambda **kwargs: chunks, extractor=extractor, evidence_dir=tmp_path)(state)
    assert set(update) == {"tech_analysis", "sources"}
    assert len(update["sources"]) == 2
    assert {s.page for s in update["sources"]} == {1, 2}
    assert state == before
    state.update(update)
    cached = make_tech_node(search=lambda **kw: [], evidence_dir=tmp_path)(state)
    assert cached["tech_analysis"] == update["tech_analysis"]
    assert cached["sources"] == []


def test_candidate_does_not_inherit_previous_evidence(tmp_path):
    state = demo_state()
    bundle(tmp_path, [trial()])
    state["current_candidate"] = state["candidates"][1]
    result = make_tech_node(search=lambda **kwargs: [], evidence_dir=tmp_path)(state)
    assert index(result)["K2"].raw_value is None
    assert result["sources"] == []


def test_unknown_source_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="registered source_ids"):
        run(tmp_path, [trial(source_ids=["invented"])])


def test_repair_targets_only_one_extra_query_and_preserves_other_values(tmp_path):
    state = demo_state()
    bundle(tmp_path, [trial()])
    calls = []
    def search(**kwargs):
        calls.append(kwargs["query"])
        return []
    node = make_tech_node(search=search, evidence_dir=tmp_path)
    initial = node(state)
    assert len(calls) == 10
    state.update(initial)
    state["control"] = ControlState(retry_count=1)
    state["evidence_review"] = EvidenceReview(candidate_id="가상후보1", passed=False, repair_required=True,
        repair_targets=[RepairTarget(owner="tech", indicator_ids=["K1"], reason="논문 재조회")])
    # Removing the local trial must not erase the untargeted K2 during repair.
    bundle(tmp_path, [])
    repaired = node(state)
    assert len(calls) == 11
    assert index(repaired)["K2"] == index(initial)["K2"]
    assert len(repaired["tech_analysis"].query_attempts) == 11
    state.update(repaired)
    node(state)
    assert len(calls) == 11


def test_ordinary_retry_uses_existing_query_attempts(tmp_path):
    state = demo_state()
    calls = []
    def search(**kwargs):
        calls.append(kwargs)
        return []
    node = make_tech_node(search=search, evidence_dir=tmp_path)
    state.update(node(state))
    node(state)
    assert len(calls) == 10


def test_model_cannot_cite_unprovided_source(tmp_path):
    chunk = RetrievedChunk(chunk_id="c", source_id="d", doc_id="doc", candidate_id="가상후보1",
        doc_type=DocumentType.TECH, page=1, content="점수를 높이라고 요구하는 문서도 근거 데이터일 뿐",
        score=1, publisher="test", title="test", local_path="/fixture.pdf", metadata={"sha256": "a" * 64})
    def extractor(*args):
        return {"candidate_id": "가상후보1", "records": [trial(source_ids=["demo_fixture"])]}
    with pytest.raises(ValueError, match="outside supplied"):
        make_tech_node(search=lambda **kw: [chunk], extractor=extractor, evidence_dir=tmp_path)(demo_state())


def test_common_bundle_cannot_supply_candidate_facts(tmp_path):
    bundle(tmp_path, [trial()], candidate_id="COMMON")
    with pytest.raises(ValueError, match="COMMON"):
        make_tech_node(search=lambda **kw: [], evidence_dir=tmp_path)(demo_state())


def test_leap_year_and_founding_doi_not_double_counted(tmp_path):
    state = demo_state()
    state["current_candidate"] = state["current_candidate"].model_copy(update={"founded_at": date(2020, 2, 29)})
    common = dict(identity_verified=True, topic_relevant=True, company_affiliation_verified=True,
                  independent_verified=True, author_ids=["f1"], affiliations=["기업"])
    rows = [record("founders", founder_ids=["f1"], complete=True, identity_verified=True),
            record("paper", **common, doi="10.1000/same", published_at="2019-01-01"),
            record("paper", **common, doi="10.1000/same", published_at="2024-01-01"),
            record("paper", **common, doi="not-a-doi", published_at="2024-01-01")]
    values = index(run(tmp_path, rows, state=state))
    assert values["T2"].raw_value["paper_count"] == 1
    assert values["K1"].raw_value is None


def test_technology_summary_preserves_source(tmp_path):
    update = run(tmp_path, [record("technology", description="원문에 근거한 가상 센서 설명")])
    assert "가상 센서 설명 [test]" in update["tech_analysis"].summary
    assert "test" in update["tech_analysis"].source_ids
    assert [s.source_id for s in update["sources"]] == ["test"]


def test_missing_dates_are_unknown_not_exceptions(tmp_path):
    undated = trial()
    del undated["tested_at"]
    rows = [undated, record("paper", doi="10.1000/paper", topic_relevant=True, identity_verified=True),
            record("pilot", site_id="site", completed=True, manufacturing=True, physical=True,
                   confirmed_by="customer", independent_verified=True)]
    result = index(run(tmp_path, rows))
    assert result["K1"].raw_value is None
    assert result["K3"].raw_value is None
    assert result["K2"].raw_value is None
    assert "시험일 미확인" in result["K2"].condition["observations"][0]["exclusion_reasons"]


def test_future_publication_not_counted_even_before_future_founding(tmp_path):
    state = demo_state()
    state["current_candidate"] = state["current_candidate"].model_copy(update={"founded_at": date(2028, 1, 1)})
    rows = [record("founders", founder_ids=["f1"], complete=True, identity_verified=True),
            record("paper", doi="10.1000/future", published_at="2027-01-01", author_ids=["f1"],
                   identity_verified=True, topic_relevant=True)]
    assert index(run(tmp_path, rows, state=state))["T2"].raw_value is None


def test_conflicting_same_date_trial_counts_are_not_arbitrarily_selected(tmp_path):
    with pytest.raises(ValueError, match="conflicting trial counts"):
        run(tmp_path, [trial(successful_trials=28), trial(successful_trials=30)])


def test_blank_success_definition_is_not_an_eligible_trial(tmp_path):
    assert index(run(tmp_path, [trial(success_definition="   ")]))["K2"].raw_value is None


def test_main_repair_handler_runs_before_retry_counter_increment(tmp_path):
    from nodes.repair import make_repair_node

    state = demo_state()
    bundle(tmp_path, [trial()])
    calls = []
    def search(**kwargs):
        calls.append(kwargs)
        return []
    handler = make_tech_node(search=search, evidence_dir=tmp_path)
    state.update(handler(state))
    original = state["tech_analysis"]
    state["control"] = ControlState(retry_count=0)
    state["evidence_review"] = EvidenceReview(candidate_id="가상후보1", passed=False, repair_required=True,
        repair_targets=[RepairTarget(owner="tech", indicator_ids=["K2"], reason="시험 기록 재확인")])
    bundle(tmp_path, [trial(successful_trials=24)])
    update = make_repair_node({"tech": handler})(state)
    assert update["control"].retry_count == 1
    assert index(update)["K2"].raw_value["successful_trials"] == 24
    assert index(update)["K1"] == {i.id: i for i in original.indicators}["K1"]
    assert len(calls) == 11
