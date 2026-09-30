import pytest

from agents.synergy import make_synergy_node
from rag.models import DocumentType, RetrievedChunk
from reporting.demo import demo_state
from test_tech import bundle, index, record, source


def task(**kwargs):
    return record("task", **({"task_id": "TASK3", "performed": True, "physical": True,
        "performed_at": "2026-01-01", "confirmed_by": "customer", "independent_verified": True} | kwargs))


def run(tmp_path, rows, coverage=None):
    bundle(tmp_path, rows, coverage, sources=[source(), source("parent", 24)])
    return make_synergy_node(search=lambda **kwargs: [], evidence_dir=tmp_path, parent_dir=tmp_path / "empty")(demo_state())


def test_s2_needs_both_independent_task_and_parent_page(tmp_path):
    demand = record("parent_demand", task_id="TASK3", doc_type="parent", public_document=True,
                    source_ids=["parent"], independent_verified=True)
    result = index(run(tmp_path, [task(), task(), demand]), "synergy_analysis")
    assert result["S1"].raw_value["performed_task_count"] == 1
    s2 = result["S2"].raw_value
    assert s2["matched_task_count"] == 1
    assert s2["matches"][0]["parent_pages"][0]["page"] == 24


def test_company_claims_remain_provisional_even_with_parent_demand(tmp_path):
    demand = record("parent_demand", task_id="TASK3", doc_type="parent", public_document=True, source_ids=["parent"])
    result = index(run(tmp_path, [task(independent_verified=False, confirmed_by="company"), demand]), "synergy_analysis")
    assert result["S1"].raw_value is None
    assert result["S2"].raw_value is None
    assert result["S1"].condition["provisional_tasks"]


def test_unmatched_or_unknown_task_not_counted(tmp_path):
    result = index(run(tmp_path, [task(task_id="TASK99"), task(performed=False)]), "synergy_analysis")
    assert result["S1"].raw_value is None


@pytest.mark.parametrize("change,expected", [
    ({"explosive_zone": None}, "UNKNOWN"),
    ({"explosive_zone": False}, "NOT_APPLICABLE"),
    ({"lookup_status": "ACCESS_FAILED"}, "UNKNOWN"),
    ({}, "NO_VALID_EVIDENCE"),
    ({"in_progress": True, "progress_reference": "application-123"}, "IN_PROGRESS"),
    ({"certification": "IECEx", "certificate_id": "123", "scope_matches": True,
      "valid_from": "2025-01-01", "valid_until": "2027-01-01"}, "CERTIFIED"),
    ({"certification": "IECEx", "certificate_id": "123", "scope_matches": True,
      "valid_from": "2024-01-01", "valid_until": "2025-01-01"}, "NO_VALID_EVIDENCE"),
])
def test_f4_status_is_not_gate_judgment(tmp_path, change, expected):
    base = {"process_id": "P1", "equipment_model": "MODEL1", "checked_at": "2026-09-01",
            "explosive_zone": True, "lookup_status": "SUCCESS", "lookup_complete": True, "progress_checked": True}
    result = index(run(tmp_path, [record("certification", **(base | change))]), "synergy_analysis")["F4"]
    assert result.raw_value["checks"][0]["verification_status"] == expected
    assert "passed" not in result.raw_value


def test_latest_certificate_lookup_supersedes_old_absence(tmp_path):
    base = {"process_id": "P", "equipment_model": "M", "checked_at": "2025-01-01",
            "explosive_zone": True, "lookup_status": "SUCCESS", "lookup_complete": True, "progress_checked": True}
    current = base | {"checked_at": "2026-01-01", "in_progress": True, "progress_reference": "application"}
    value = index(run(tmp_path, [record("certification", **base), record("certification", **current)]), "synergy_analysis")["F4"]
    assert len(value.raw_value["checks"]) == 1
    assert value.raw_value["checks"][0]["verification_status"] == "IN_PROGRESS"


@pytest.mark.parametrize("missing", ["scope_matches", "valid_until", "valid_from", "certificate_id"])
def test_incomplete_certificate_is_unknown_not_absent(tmp_path, missing):
    row = record("certification", process_id="P", equipment_model="M", checked_at="2026-09-01",
        explosive_zone=True, lookup_status="SUCCESS", lookup_complete=True, progress_checked=True,
        certification="IECEx", certificate_id="cert1", scope_matches=True,
        valid_from="2025-01-01", valid_until="2027-01-01")
    del row[missing]
    result = index(run(tmp_path, [row]), "synergy_analysis")["F4"]
    assert result.raw_value["checks"][0]["verification_status"] == "UNKNOWN"


def test_undated_task_and_certificate_are_unknown(tmp_path):
    row = task()
    del row["performed_at"]
    result = index(run(tmp_path, [row, record("certification", process_id="P", equipment_model="M")]), "synergy_analysis")
    assert result["S1"].raw_value is None
    assert result["F4"].raw_value is None


@pytest.mark.parametrize("kind,doc_type", [("parent_demand", DocumentType.TECH), ("task", DocumentType.PARENT)])
def test_extractor_cannot_relabel_retrieved_source_type(tmp_path, kind, doc_type):
    chunk = RetrievedChunk(chunk_id="c", source_id="d", doc_id="doc",
        candidate_id=None if doc_type == DocumentType.PARENT else "가상후보1",
        doc_type=doc_type, page=1, content="시험용 원문", score=1, publisher="test",
        title="test", local_path="/fixture.pdf", metadata={"sha256": "a" * 64})
    def extractor(prompt, documents, candidate):
        refs = [documents[0]["source_id"]]
        row = (record("parent_demand", task_id="TASK3", doc_type="parent", public_document=True, source_ids=refs)
               if kind == "parent_demand" else task(source_ids=refs))
        return {"candidate_id": candidate.candidate_id, "records": [row]}
    with pytest.raises(ValueError, match="parent"):
        make_synergy_node(search=lambda **kw: [chunk], extractor=extractor,
            evidence_dir=tmp_path, parent_dir=tmp_path)(demo_state())
