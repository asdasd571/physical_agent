"""네 관점의 근거와 한계를 함께 기록하는 Supervisor 보고서이다."""

from hashlib import sha256
from html import escape
import json
import re
from pathlib import Path

import pymupdf

from reporting.formatter import indicator_text, format_source, format_number
from schemas import QueryStatus, EvidenceStatus, ReportResult
from schemas.supervisor import ReportDraft, ReportSection


PERSPECTIVES = {
    "technology": ("기술 성숙도", {"T2", "K1", "K2", "K3"}),
    "market": ("시장성", {"P1", "R1", "R2", "R3", "M1"}),
    "stakeholders": ("이해관계자", {"T1", "F1", "F2", "F3"}),
    "application": ("도메인 적용", {"S1", "S2", "F4"}),
}
NEUTRALITY_TERMS = ("투자를 추천", "매수를 추천", "기술이 우월", "최고의 기술", "압도적 우위", "무조건 투자", "반드시 투자")


def make_draft(state):
    sections = []
    for evaluation in state["evaluations"]:
        skipped = evaluation.total_score is None and evaluation.benchmark_score is None
        for perspective, (title, ids) in PERSPECTIVES.items():
            indicators = [i for i in evaluation.indicators if i.id in ids]
            units = {"T1": "명", "T2": "편/명", "K1": "편", "K2": "%", "K3": "현장", "S1": "작업군",
                     "S2": "작업군", "P1": "%", "R1": "억 원", "R2": "억 원", "R3": "%", "M1": "패밀리"}
            values = evaluation.metadata.get("scoring_values", {})
            lines = []
            for item in indicators:
                text = indicator_text(item) if item.raw_value is not None else f"채점 요건 근거 미확보 — {item.missing_reason or '추가 확인이 필요합니다.'}"
                line = f"{item.id}: {text}"
                if values.get(item.id) is not None:
                    line += f" (채점값 {format_number(values[item.id], 2)} {units[item.id]}, {evaluation.indicator_scores[item.id]}/5점)"
                lines.append(line)
            limitations = [f"{i.id}: {i.missing_reason or '근거의 조건을 추가 확인해야 합니다.'}"
                          for i in indicators if i.query_status != QueryStatus.SUCCESS]
            if any(i.evidence_status == EvidenceStatus.COMPANY_CLAIM for i in indicators):
                limitations.append("기업 자체 발표가 포함되어 있으며 독립 검증으로 해석하지 않습니다.")
            if skipped:
                lines = ["적격성 검토에서 심층 평가를 생략했습니다. 이 관점의 결론은 유보합니다."]
                limitations = list(evaluation.decision.reasons)
            if not lines:
                lines = ["확인된 자료가 없습니다. 이 관점의 결론은 유보합니다."]
                limitations.append("해당 관점의 추가 조사가 필요합니다.")
            narrative_section = {"technology": "technology", "market": "market", "stakeholders": "risk", "application": "business"}[perspective]
            refs = {s for i in indicators for s in i.source_ids}
            if perspective == "technology":
                comparison = evaluation.metadata.get("early_stage_comparison", {})
                for key, reasons in comparison.get("changes", {}).items():
                    lines.append(f"초기 단계 {key}: " + " ".join(reasons))
                if comparison.get("changes"):
                    limitations.append("초기 단계 기준은 해당 항목을 최대 2/5점으로 인정하며, 투자 판정에는 사용하지 않습니다.")
                findings = evaluation.metadata.get("technical_findings", [])
                for finding in findings:
                    description = re.sub(r"\s*\(source_ids:\s*\[[^\]]*\]\)", "", finding["description"])
                    lines.append("확인된 제품·기술 설명: " + description)
                    refs.update(finding["source_ids"])
                if findings:
                    limitations.append("제품 설명이 확보되었으나 논문 수·시험 성공률·독립 현장 실증의 정량 근거를 대신하지 않습니다.")
            for n in evaluation.metadata.get("narratives", []):
                if n.get("section") != narrative_section:
                    continue
                # 최초 초안은 해설을 포함하며, 품질 미달 후에는 검증 가능한 원값으로 재작성한다.
                if state["report_revision"] == 0:
                    lines.append(n["text"])
                    refs.update(n["source_ids"])
            if skipped:
                refs.update(s for gate in evaluation.gates.values() for s in gate.source_ids)
            sections.append(ReportSection(
                candidate_id=evaluation.candidate_id, perspective=perspective, title=title,
                text="\n".join(lines), source_ids=sorted(refs),
                indicator_ids=[i.id for i in indicators], limitations=limitations,
            ))
    reference_ids = sorted({s for section in sections for s in section.source_ids})
    return ReportDraft(
        run_id=state["run"].run_id, revision=state["report_revision"], sections=sections,
        reference_ids=reference_ids,
        summary="공개 자료를 바탕으로 기술 성숙도, 시장성, 이해관계자, 도메인 적용을 검토한 보고서입니다. "
                "투자 규칙의 계산 결과와 기술의 우열은 구분합니다. 미확인 자료는 추정하지 않고 후속 확인 항목으로 남깁니다.",
    )


def report_pages(state, draft, font_directory=None):
    esc = lambda text: escape(str(text)).replace("\n", "<br>")
    names = {c.candidate_id: c.legal_name for c in state["candidates"]}
    reasons = {"evidence_sufficient": "근거 검토 완료", "evidence_exhausted": "조사 한도 도달·근거 부족",
               "ineligible": "적격성 기준 미충족", "eligibility_unresolved": "적격성 확인 불가"}
    rows = []
    for evaluation in state["evaluations"]:
        history = state["routing_history"][evaluation.candidate_id]
        score = evaluation.total_score if evaluation.total_score is not None else (
            f"비교 {evaluation.benchmark_score}" if evaluation.benchmark_score is not None else "미산정")
        early = evaluation.metadata.get("early_stage_comparison", {}).get("score", "미산정")
        rows.append(f"<tr><td>{esc(names[evaluation.candidate_id])}</td><td>{esc(evaluation.decision.status.value)}</td>"
                    f"<td>{esc(score)}</td><td>{esc(early)}</td>"
                    f"<td>{esc(reasons.get(history.termination_reason, history.termination_reason))}</td></tr>")
    pages = ["<h1>Physical AI 검토 보고서</h1><h2>SUMMARY</h2>"
             f"<p>{esc(draft.summary)}</p><p>평가일: {state['run'].evaluation_date} / 개정: {draft.revision}</p>"
             f"<p>Run ID: {esc(draft.run_id)}</p><table><tr><th>후보</th><th>규칙 판정</th><th>기존 기준</th><th>초기 단계 기준</th><th>조사 종료 사유</th></tr>{''.join(rows)}</table>"
             "<p>초기 단계 기준은 공개 사양·실물 센서 시험·공개 시연에 제한적으로 점수를 인정한 비교 결과입니다. "
             "투자 판정은 기존 기준으로 유지합니다. 투자 단계가 범위 밖인 후보의 점수는 투자 점수가 아닌 비교 분석 값입니다.</p>"
             "<p>HOLD/INVEST는 기존 투자 규칙을 적용한 계산 결과입니다. 기술 추천 또는 실제 투자 권고를 의미하지 않습니다.</p>"
             "<h2>검토 범위와 판단 기준</h2><p>로봇 핸드, 힘·촉각 센서, VLA 기반 조작 지능을 대상으로 합니다. "
             "적격성·문제 적합성·결격 위험의 세 Gate와 창업팀·기술력·전략 시너지·시장성·트랙션·경쟁 우위의 여섯 항목을 적용합니다.</p>"
             "<p>기업의 자체 발표와 독립된 검증을 구분합니다. 원값, 기간, 적용 조건 또는 출처가 부족한 항목은 미확인으로 남깁니다. "
             "한도가 소진된 후보는 점수와 별개로 보수적으로 보류합니다.</p>"
             "<h2>후속 확인 사항</h2>" + "".join(
                 f"<p><b>{esc(names[e.candidate_id])}</b>: {esc(' / '.join(e.decision.reasons))}</p>" for e in state["evaluations"])]
    for perspective, (title, _) in PERSPECTIVES.items():
        parts = [f"<h1>{esc(title)}</h1>"]
        if perspective == "stakeholders":
            parts.append("<p>기술진과 투자자의 근거를 검토합니다. 현장 운영자, 모기업 수요 부서와 인증기관 관련 내용은 도메인 적용 관점에서 함께 검토합니다.</p>")
        for section in draft.sections:
            if section.perspective != perspective:
                continue
            refs = ", ".join(section.source_ids) or "인용할 근거가 없습니다."
            parts.append(f"<h2>{esc(names[section.candidate_id])}</h2><p>{esc(section.text)}</p>"
                         f"<p class='reference'>출처: {esc(refs)}</p>")
            if section.limitations:
                parts.append("<p class='limit'>확인 한계: " + esc(" / ".join(section.limitations)) + "</p>")
        pages.append("".join(parts))
    registry = {s.source_id: s for s in state["sources"]}
    refs = [registry[s] for s in draft.reference_ids if s in registry]
    # 항목별로 측정하여 페이지를 나눈다. 잘라내거나 글씨를 과도하게 줄이지 않는다.
    current = "<h1>REFERENCE</h1>"
    for source in refs:
        entry = f"<p>{esc(format_source(source, source.source_id))}<br>{esc(source.url or source.local_path or '원문 위치 미등록')}</p>"
        if not fits(current + entry, font_directory=font_directory):
            pages.append(current)
            current = "<h1>REFERENCE (계속)</h1>"
        current += entry
    pages.append(current if refs else current + "<p>인용 가능한 출처가 없습니다.</p>")
    return pages


CSS = "body {font-size: 9pt; line-height: 1.35;} h1 {font-size: 17pt; color: #18364d;} h2 {font-size: 12pt;} table {width:100%;} td,th {padding:5pt;} .reference {font-size:7pt;} .limit {color:#655036;}"
PAGE = pymupdf.Rect(0, 0, 595, 842)
BODY = pymupdf.Rect(36, 36, 559, 800)


def pdf_style(font_directory=None):
    if font_directory is None:
        return CSS, None
    directory = Path(font_directory)
    for weight in ("Regular", "Bold"):
        if not (directory / f"Pretendard-{weight}.ttf").is_file():
            raise FileNotFoundError(f"Pretendard-{weight}.ttf 글꼴이 없습니다.")
    style = "@font-face {font-family:Pretendard; src:url(Pretendard-Regular.ttf); font-weight:400;} "
    style += "@font-face {font-family:Pretendard; src:url(Pretendard-Bold.ttf); font-weight:700;} "
    style += CSS + " body {font-family:Pretendard;} "
    return style, pymupdf.Archive(str(directory))


def fits(html, font_directory=None):
    style, archive = pdf_style(font_directory)
    story = pymupdf.Story(html=html, user_css=style, archive=archive)
    more, _ = story.place(BODY)
    return not more


def write_pdf(pages, path, font_directory=None):
    if len(pages) > 10:
        raise ValueError("보고서가 10페이지 상한을 초과합니다.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pending.pdf")
    style, archive = pdf_style(font_directory)
    try:
        writer = pymupdf.DocumentWriter(str(temporary))
        try:
            for html in pages:
                story = pymupdf.Story(html=html, user_css=style, archive=archive)
                more, _ = story.place(BODY)
                if more:
                    raise ValueError("보고서 내용이 페이지 영역을 초과합니다.")
                device = writer.begin_page(PAGE)
                story.draw(device)
                writer.end_page()
        finally:
            writer.close()
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def supervisor_report_node(state):
    draft = make_draft(state)
    output = state["run"].settings.get("report_output_path")
    base = Path(output) if output else Path("artifacts") / state["run"].run_id / "report.pdf"
    if base.suffix.lower() != ".pdf":
        raise ValueError("보고서 경로는 .pdf로 끝나야 합니다.")
    path = base.with_name(f"{base.stem}.r{draft.revision}.pdf")
    write_pdf(report_pages(state, draft), path)
    payload = {
        "draft": draft.model_dump(mode="json"),
        "evaluations": [e.model_dump(mode="json") for e in state["evaluations"]],
        "sources": [s.model_dump(mode="json") for s in state["sources"] if s.source_id in draft.reference_ids],
        "pdf_sha256": sha256(path.read_bytes()).hexdigest(),
    }
    path.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"draft": draft, "report": ReportResult(output_path=str(path), source_ids=draft.reference_ids)}
