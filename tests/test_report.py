import json
from decimal import Decimal

import pymupdf
import pytest

from agents.report import report_node
from reporting.demo import demo_state
from reporting.formatter import format_money, format_number, format_percent, format_value
from reporting.renderer import ReportLayoutError, ReportValidationError, render_investment_report
from schemas import Decision, EvaluationRecord, GateResult


def test_korean_pdf_five_pages_all_candidates_and_exact_numbers(tmp_path):
    state = demo_state(3)
    result = render_investment_report(state["evaluations"], state["sources"], tmp_path / "report.pdf", demo=True)
    with pymupdf.open(result) as pdf:
        assert len(pdf) == 5
        assert "SUMMARY" in pdf[0].get_text()
        assert "REFERENCE" in pdf[-1].get_text()
        assert all(f"가상후보{i}" in pdf[0].get_text() for i in range(1, 4))
        assert "93.33%" in pdf[1].get_text()
        assert "배터리 셀 집기" in pdf[1].get_text()
        assert "미확인" in pdf[3].get_text()
        assert "demo_fixture" in pdf[-1].get_text()
        assert all(pdf.extract_font(f[0])[3] for page in pdf for f in page.get_fonts())
        # The entire summary region precedes the fixed half-page boundary.
        assert max(w[3] for w in pdf[0].get_text("words") if w[1] < 395) < 421
    payload = json.loads(result.with_suffix(".json").read_text())
    assert payload["evaluations"][0]["total_score"] == "46.7"
    assert payload["demo"] is True


def test_only_used_sources_in_reference_and_json(tmp_path):
    state = demo_state()
    unused = state["sources"][0].model_copy(update={"source_id": "UNUSED", "title": "NEVER_DISPLAY"})
    path = render_investment_report(state["evaluations"], state["sources"] + [unused], tmp_path / "r.pdf")
    with pymupdf.open(path) as pdf:
        assert "NEVER_DISPLAY" not in "".join(p.get_text() for p in pdf)
    assert [s["source_id"] for s in json.loads(path.with_suffix(".json").read_text())["sources"]] == ["demo_fixture"]


def test_all_skipped_hold_candidates_render_without_fake_scores(tmp_path):
    state = demo_state()
    evaluations = [EvaluationRecord(candidate_id=c.candidate_id, country="KR", primary_segment=c.primary_segment,
        rule_version="test", gates={"G1": GateResult(passed=False, unknown_items=["법인 조회 미확인"])},
        decision=Decision(status="HOLD", reasons=["적격성 미확인"])) for c in state["candidates"]]
    path = render_investment_report(evaluations, [], tmp_path / "hold.pdf")
    with pymupdf.open(path) as pdf:
        assert "미산정" in pdf[0].get_text()
        assert "REFERENCE" in pdf[-1].get_text()


@pytest.mark.parametrize("change", ["unreviewed", "unscored", "duplicate", "missing_source", "nested_source"])
def test_invalid_archive_rejected_without_artifact(tmp_path, change):
    state = demo_state()
    e = state["evaluations"][0]
    if change == "unreviewed":
        state["evaluations"][0] = e.model_copy(update={"metadata": {"scoring_completed": True}})
    elif change == "unscored":
        state["evaluations"][0] = e.model_copy(update={"total_score": None})
    elif change == "duplicate":
        state["evaluations"].append(e)
    elif change == "missing_source":
        state["sources"] = []
    else:
        i = e.indicators[0].model_copy(update={"condition": {"source_ids": ["invented"]}})
        state["evaluations"][0] = e.model_copy(update={"indicators": [i]})
    with pytest.raises(ReportValidationError):
        render_investment_report(state["evaluations"], state["sources"], tmp_path / "bad.pdf")
    assert not (tmp_path / "bad.pdf").exists()


def test_overflow_is_error_not_clipping(tmp_path):
    state = demo_state()
    e = state["evaluations"][0]
    state["evaluations"][0] = e.model_copy(update={"unknown_items": ["아주 긴 검증 필요 항목 " * 3000]})
    with pytest.raises(ReportLayoutError):
        render_investment_report(state["evaluations"], state["sources"], tmp_path / "overflow.pdf")
    assert not (tmp_path / "overflow.pdf").exists()


def test_report_node_completeness_and_partial_update(tmp_path):
    state = demo_state()
    state["run"] = state["run"].model_copy(update={"settings": {"report_output_path": str(tmp_path / "node.pdf")}})
    result = report_node(state)
    assert set(result) == {"report"}
    assert result["report"].source_ids == ["demo_fixture"]
    state["evaluations"].pop()
    with pytest.raises(ReportValidationError, match="exactly once"):
        report_node(state)


def test_existing_report_is_preserved(tmp_path):
    state = demo_state()
    path = tmp_path / "original.pdf"
    path.write_bytes(b"existing artifact")
    with pytest.raises(FileExistsError):
        render_investment_report(state["evaluations"], state["sources"], path)
    assert path.read_bytes() == b"existing artifact"


def test_formatting_preserves_zero_and_missing():
    assert format_value(None) == "자료 없음"
    assert format_value(0) == "0"
    assert format_money(0) == "0 KRW"
    assert format_percent(Decimal("93.335")) == "93.34%"
    assert format_number(Decimal("70.05"), 1) == "70.1"


def test_cited_narrative_is_rendered_and_unsourced_narrative_rejected(tmp_path):
    state = demo_state(1)
    e = state["evaluations"][0]
    narrative = {"section": "technology", "text": "가상 센서로 접촉 상태를 확인하는 예시.",
                 "source_ids": ["demo_fixture"]}
    state["evaluations"][0] = e.model_copy(update={"metadata": e.metadata | {"narratives": [narrative]}})
    path = render_investment_report(state["evaluations"], state["sources"], tmp_path / "narrative.pdf")
    with pymupdf.open(path) as pdf:
        assert "가상 센서" in pdf[1].get_text()
    narrative["source_ids"] = []
    with pytest.raises(ReportValidationError, match="narratives"):
        render_investment_report(state["evaluations"], state["sources"], tmp_path / "invalid.pdf")


@pytest.mark.parametrize("change", ["missing_score", "missing_raw", "missing_category", "invalid_score", "nan_category", "contradictory_invest"])
def test_incomplete_or_inconsistent_scores_cannot_be_published(tmp_path, change):
    state = demo_state(1)
    e = state["evaluations"][0]
    updates = {}
    if change == "missing_score":
        updates["indicator_scores"] = {k: v for k, v in e.indicator_scores.items() if k != "K2"}
    elif change == "missing_raw":
        updates["indicators"] = [i for i in e.indicators if i.id != "K2"]
    elif change == "missing_category":
        updates["category_scores"] = {k: v for k, v in e.category_scores.items() if k != "tech"}
    elif change == "invalid_score":
        updates["indicator_scores"] = e.indicator_scores | {"K2": 6}
    elif change == "nan_category":
        updates["category_scores"] = e.category_scores | {"tech": Decimal("NaN")}
    else:
        updates["decision"] = Decision(status="INVEST", reasons=["잘못된 저장 결과"])
    with pytest.raises(ReportValidationError):
        render_investment_report([e.model_copy(update=updates)], state["sources"], tmp_path / "bad.pdf")
    assert not (tmp_path / "bad.pdf").exists()


def test_synthetic_archive_always_displays_demo_label(tmp_path):
    state = demo_state(1)
    path = render_investment_report(state["evaluations"], state["sources"], tmp_path / "synthetic.pdf")
    with pymupdf.open(path) as pdf:
        assert "테스트용 가상 데이터" in pdf[0].get_text()
    assert json.loads(path.with_suffix(".json").read_text())["demo"] is True
