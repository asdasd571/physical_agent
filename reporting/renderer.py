"""Five-page Korean PDF from archived results, with bounded HTML layout.

PyMuPDF embeds its bundled CJK fallback font. No system font is copied and no
network resource is fetched. Oversized content fails instead of being clipped.
"""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import tempfile

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
import pymupdf

from schemas import DecisionStatus, EvaluationRecord, QueryStatus, SourceRecord
from reporting.formatter import (
    format_number, format_percent, format_source, format_status, format_value, indicator_text,
)


class ReportValidationError(ValueError):
    pass


class ReportLayoutError(ReportValidationError):
    pass


SCORED_INDICATORS = {"T1", "T2", "K1", "K2", "K3", "S1", "S2", "P1", "R1", "R2", "R3", "M1"}
SCORED_CATEGORIES = {"team", "tech", "synergy", "market", "traction", "moat"}


def _nested_sources(value):
    result = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("source_ids") and isinstance(item, list):
                result.update(item)
            elif key == "source_id" and isinstance(item, str):
                result.add(item)
            else:
                result.update(_nested_sources(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_nested_sources(item))
    return result


def validate_report_inputs(evaluations, sources):
    evaluations = [EvaluationRecord.model_validate(e) for e in evaluations]
    sources = [SourceRecord.model_validate(s) for s in sources]
    if not evaluations:
        raise ReportValidationError("no archived evaluations")
    if len({e.candidate_id for e in evaluations}) != len(evaluations):
        raise ReportValidationError("duplicate candidate evaluation")
    if len({e.rule_version for e in evaluations}) != 1:
        raise ReportValidationError("candidates must share a rule_version")
    registry = {}
    for source in sources:
        if source.source_id in registry and registry[source.source_id] != source:
            raise ReportValidationError(f"conflicting source: {source.source_id}")
        registry[source.source_id] = source
    used = set()
    for evaluation in evaluations:
        g1 = evaluation.gates.get("G1")
        skipped = g1 is not None and not g1.passed and evaluation.total_score is None
        if skipped:
            if evaluation.decision.status != DecisionStatus.HOLD:
                raise ReportValidationError("skipped candidate must be HOLD")
        else:
            if evaluation.metadata.get("review_completed") is not True:
                raise ReportValidationError("archive must set metadata.review_completed=True")
            if evaluation.metadata.get("scoring_completed") is not True or evaluation.total_score is None:
                raise ReportValidationError("archive must complete scoring before rendering")
            if not {"G1", "G2", "G3"} <= set(evaluation.gates):
                raise ReportValidationError("scored evaluation requires all gates")
            if not SCORED_INDICATORS <= {i.id for i in evaluation.indicators}:
                raise ReportValidationError("scored evaluation requires all 12 raw indicators")
            if set(evaluation.indicator_scores) != SCORED_INDICATORS or any(
                    type(score) is not int or not 1 <= score <= 5 for score in evaluation.indicator_scores.values()):
                raise ReportValidationError("all 12 indicator scores must be integers in 1..5")
            if set(evaluation.category_scores) != SCORED_CATEGORIES or any(
                    not score.is_finite() or not 1 <= score <= 5 for score in evaluation.category_scores.values()):
                raise ReportValidationError("all six category scores must be finite values in 1..5")
            if not evaluation.total_score.is_finite() or not 0 <= evaluation.total_score <= 100:
                raise ReportValidationError("total_score must be finite and in 0..100")
            if evaluation.decision.status == DecisionStatus.INVEST and (
                    not all(evaluation.gates[g].passed for g in ("G1", "G2", "G3")) or evaluation.total_score < 70):
                raise ReportValidationError("INVEST contradicts archived gates or threshold")
        if len({i.id for i in evaluation.indicators}) != len(evaluation.indicators):
            raise ReportValidationError("duplicate indicator ID")
        for indicator in evaluation.indicators:
            if indicator.query_status == QueryStatus.SUCCESS and not indicator.source_ids:
                raise ReportValidationError(f"unsourced value: {indicator.id}")
            nested = _nested_sources(indicator.raw_value) | _nested_sources(indicator.condition)
            if not nested <= set(indicator.source_ids):
                raise ReportValidationError(f"undeclared nested source: {indicator.id}")
            used.update(indicator.source_ids)
        for gate in evaluation.gates.values():
            used.update(gate.source_ids)
        for narrative in evaluation.metadata.get("narratives", []):
            if (not isinstance(narrative, dict) or narrative.get("section") not in
                    {"business", "technology", "market", "risk"} or not narrative.get("text")
                    or not narrative.get("source_ids")):
                raise ReportValidationError("report narratives need section, text and source_ids")
            used.update(narrative["source_ids"])
    if used - registry.keys():
        raise ReportValidationError(f"unknown source_ids: {sorted(used - registry.keys())}")
    return evaluations, [registry[s] for s in sorted(used)]


def _conditions(indicator):
    c = indicator.condition
    details = []
    if indicator.period:
        details.append(f"기간: {indicator.period}")
    if indicator.id == "K2":
        for key, title in (("task", "작업"), ("environment", "환경"), ("success_definition", "성공 정의"),
                           ("equipment_model", "장비"), ("conditions", "조건"), ("independent_reproduction", "독립 재현")):
            if key in c:
                details.append(f"{title}: {format_value(c[key])}")
        for trial in c.get("observations", []):
            details.append(f"시험 {trial.get('tested_at', '미확인')}: {trial.get('task', '미확인')}, "
                f"{trial.get('successful_trials', '?')}/{trial.get('total_trials', '?')}, "
                f"{trial.get('environment', '미확인')}, 정의: {trial.get('success_definition', '미확인')}; "
                + ", ".join(trial.get("exclusion_reasons", [])))
    if c.get("provisional_tasks"):
        details.append("자체 발표 잠정 작업(확정 개수 제외): " + ", ".join(
            r["task_id"] for r in c["provisional_tasks"]))
    if c.get("site_ids"):
        details.append("현장: " + ", ".join(c["site_ids"]))
    if c.get("limitation"):
        details.append(c["limitation"])
    if indicator.id == "F4" and isinstance(indicator.raw_value, dict):
        for r in indicator.raw_value.get("checks", []):
            details.append(" / ".join(f"{k}: {format_value(r.get(k))}" for k in (
                "explosive_zone", "lookup_status", "certification", "certificate_id", "scope_matches",
                "valid_from", "valid_until", "in_progress")))
    return " | ".join(details)


def _view(evaluations, sources):
    labels = {s.source_id: f"SRC-{index:02d}" for index, s in enumerate(sources, 1)}
    cite = lambda ids: " ".join(f"[{labels[s]}]" for s in sorted(set(ids)))
    rows = []
    category_labels = {"team": "창업자·팀", "tech": "기술력", "synergy": "전략 시너지",
                       "market": "시장성", "traction": "실적", "moat": "경쟁 우위"}
    for e in evaluations:
        rows.append({
            "id": e.candidate_id, "country": e.country, "segment": e.primary_segment,
            "decision": "추천 (INVEST)" if e.decision.status == DecisionStatus.INVEST else "보류 (HOLD)",
            "score": "미산정" if e.total_score is None else format_number(e.total_score),
            "reasons": e.decision.reasons, "unknown": e.unknown_items,
            "diligence": e.due_diligence_items,
            "coverage": "자료 없음" if e.evidence_coverage is None else format_percent(e.evidence_coverage * 100),
            "scores": e.indicator_scores,
            "categories": {category_labels.get(k, k): str(v) for k, v in e.category_scores.items()},
            "narratives": [{"section": n["section"], "text": n["text"], "citation": cite(n["source_ids"])}
                           for n in e.metadata.get("narratives", [])],
            "citation": cite({s for i in e.indicators for s in i.source_ids}
                             | {s for g in e.gates.values() for s in g.source_ids}),
            "gates": [{"id": k, "passed": g.passed, "reasons": g.reasons,
                       "unknown": g.unknown_items, "citation": cite(g.source_ids)} for k, g in e.gates.items()],
            "indicators": [{"id": i.id, "text": indicator_text(i), "details": _conditions(i),
                "evidence": format_status(i.evidence_status), "query": format_status(i.query_status),
                "citation": cite(i.source_ids)} for i in e.indicators],
        })
    return {"candidates": rows, "references": [
        {"text": format_source(s, labels[s.source_id]), "source_id": s.source_id, "url": s.url or "원문 URL 미등록",
         "chunk": s.chunk_id or s.response_id or "", "collected_at": s.collected_at.isoformat()}
        for s in sources]}


def render_investment_report(evaluations, sources, output_path: Path, *, evaluation_date: date | None = None,
                             demo: bool = False) -> Path:
    evaluations, sources = validate_report_inputs(evaluations, sources)
    demo = demo or any(e.metadata.get("synthetic") is True for e in evaluations)
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".pdf":
        raise ReportValidationError("output_path must end with .pdf")
    json_path = output_path.with_suffix(".json")
    if output_path.exists() or json_path.exists():
        raise FileExistsError("report output already exists; choose a new filename")
    environment = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html"]), undefined=StrictUndefined)
    template = environment.get_template("investment_report.html")
    context = _view(evaluations, sources)
    context.update(date=evaluation_date.isoformat() if evaluation_date else "실행일 미등록", demo=demo)
    # Each section is measured before any output is published. No overflow hidden.
    page_rect = pymupdf.Rect(0, 0, 595, 842)
    body = pymupdf.Rect(36, 36, 559, 800)
    sections = [(1, "summary", pymupdf.Rect(36, 36, 559, 395)),
                (1, "profile", pymupdf.Rect(36, 413, 559, 800))]
    sections.extend((p, "body", body) for p in range(2, 6))
    layouts = []
    for page, part, rect in sections:
        html = template.render(**context, page=page, part=part)
        for size in (10, 9, 8):
            story = pymupdf.Story(html=html, user_css=f"body {{ font-size: {size}pt; }}", em=size)
            more, filled = story.place(rect)
            if not more and pymupdf.Rect(filled).x1 <= rect.x1 + 0.1:
                layouts.append((page, story))
                break
        else:
            raise ReportLayoutError(f"page {page} ({part}) exceeds readable page budget; shorten input summaries")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".report-", dir=output_path.parent) as tmp:
        pdf = Path(tmp) / "report.pdf"
        writer = pymupdf.DocumentWriter(str(pdf))
        try:
            for page_number in range(1, 6):
                device = writer.begin_page(page_rect)
                for page, story in layouts:
                    if page == page_number:
                        story.draw(device)
                writer.end_page()
        finally:
            writer.close()
        with pymupdf.open(pdf) as document:
            if len(document) != 5 or "REFERENCE" not in document[-1].get_text():
                raise ReportValidationError("invalid PDF pagination")
            for page in document:
                for word in page.get_text("words"):
                    if not (0 <= word[0] <= word[2] <= 595 and 0 <= word[1] <= word[3] <= 842):
                        raise ReportLayoutError("text extends outside page")
        payload = {"demo": demo, "evaluation_date": context["date"], "page_count": 5,
            "evaluations": [e.model_dump(mode="json") for e in evaluations],
            "sources": [s.model_dump(mode="json") for s in sources]}
        sidecar = Path(tmp) / "report.json"
        sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Do not overwrite an artifact created by another run during layout.
        os.link(pdf, output_path)
        try:
            os.link(sidecar, json_path)
        except OSError:
            output_path.unlink()
            raise
    return output_path
