"""과제의 1안(규칙 기반)을 적용한다. 출처의 내용상 함의까지 판정하지는 않는다."""

from hashlib import sha256
import json
from pathlib import Path

import pymupdf

from reporting.supervisor_report import PERSPECTIVES, NEUTRALITY_TERMS
from schemas import EvidenceStatus, QueryStatus
from schemas.supervisor import QualityCriterion, ReportQuality


def report_quality_node(state):
    draft = state["draft"]
    registry = {s.source_id: s for s in state["sources"]}
    grounded, neutral, bias, coverage, artifact = [], [], [], [], []
    if draft is None:
        raise ValueError("품질 평가할 보고서 초안이 없습니다.")
    expected = {e.candidate_id: e for e in state["evaluations"]}
    section_keys = [(s.candidate_id, s.perspective) for s in draft.sections]
    required_keys = {(candidate, perspective) for candidate in expected for perspective in PERSPECTIVES}
    if len(section_keys) != len(set(section_keys)) or set(section_keys) != required_keys:
        coverage.append("후보별 네 관점이 누락되었거나 중복되었습니다.")
    used = set()
    for section in draft.sections:
        refs = set(section.source_ids)
        used.update(refs)
        if not refs <= registry.keys():
            grounded.append(f"{section.candidate_id}/{section.perspective}: 미등록 인용입니다.")
        if not section.text.strip():
            coverage.append(f"{section.candidate_id}/{section.perspective}: 본문이 없습니다.")
        if not refs and not section.limitations:
            grounded.append(f"{section.candidate_id}/{section.perspective}: 근거 또는 확인 한계가 없습니다.")
        if any(term in section.text for term in NEUTRALITY_TERMS):
            neutral.append(f"{section.candidate_id}/{section.perspective}: 기술 우열 또는 추천 표현이 있습니다.")
        evaluation = expected.get(section.candidate_id)
        if evaluation is None:
            continue
        indicators = [i for i in evaluation.indicators if i.id in PERSPECTIVES[section.perspective][1]]
        if set(section.indicator_ids) != {i.id for i in indicators}:
            coverage.append(f"{section.candidate_id}/{section.perspective}: 필수 지표의 표현이 누락되었습니다.")
        for indicator in indicators:
            if indicator.query_status == QueryStatus.SUCCESS and (
                not indicator.source_ids or not set(indicator.source_ids) <= refs
            ):
                grounded.append(f"{section.candidate_id}/{indicator.id}: 주장과 인용이 연결되지 않았습니다.")
            if indicator.query_status != QueryStatus.SUCCESS and not any(indicator.id in line for line in section.limitations):
                bias.append(f"{section.candidate_id}/{indicator.id}: 미확인 지표가 한계에 기록되지 않았습니다.")
            if indicator.evidence_status == EvidenceStatus.COMPANY_CLAIM and not any("자체 발표" in line for line in section.limitations):
                bias.append(f"{section.candidate_id}/{indicator.id}: 자체 발표의 한계가 누락되었습니다.")
    if used != set(draft.reference_ids) or used != set(state["report"].source_ids):
        grounded.append("본문 인용과 REFERENCE 목록이 일치하지 않습니다.")
    if any(term in draft.summary for term in NEUTRALITY_TERMS):
        neutral.append("SUMMARY에 기술 추천 또는 우열 표현이 있습니다.")
    for candidate, evaluation in expected.items():
        if evaluation.total_score is None:
            continue
        candidate_refs = {s for section in draft.sections if section.candidate_id == candidate for s in section.source_ids}
        publishers = {registry[s].publisher.casefold().strip() for s in candidate_refs if s in registry}
        if len(publishers) < 2:
            bias.append(f"{candidate}: 독립된 발행기관이 두 곳 미만입니다.")
    try:
        path = Path(state["report"].output_path)
        payload = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if payload["draft"] != draft.model_dump(mode="json") or payload["pdf_sha256"] != sha256(path.read_bytes()).hexdigest():
            artifact.append("State와 저장된 보고서가 일치하지 않습니다.")
        with pymupdf.open(path) as pdf:
            text = "\n".join(page.get_text() for page in pdf)
            if not 1 <= len(pdf) <= 10 or "SUMMARY" not in text or "REFERENCE" not in text:
                artifact.append("필수 목차 또는 페이지 상한을 충족하지 못했습니다.")
            for page in pdf:
                if any(not (0 <= w[0] <= w[2] <= 595 and 0 <= w[1] <= w[3] <= 842) for w in page.get_text("words")):
                    artifact.append("페이지 영역 밖의 텍스트가 있습니다.")
    except (OSError, ValueError, KeyError, RuntimeError):
        artifact.append("생성된 PDF와 JSON을 확인할 수 없습니다.")
    checks = dict(zip(("groundedness", "neutrality", "bias_control", "perspective_coverage", "artifact"),
                      (grounded, neutral, bias, coverage, artifact)))
    quality = ReportQuality(revision=state["report_revision"], passed=not any(checks.values()),
                            **{key: QualityCriterion(passed=not issues, issues=issues) for key, issues in checks.items()})
    return {"quality": quality, "quality_history": [*state["quality_history"], quality]}


def route_quality(state):
    if state["quality"].passed:
        return "finalize"
    if state["report_revision"] < state["policy"].max_report_revisions:
        return "revise_report"
    return "finalize"


def revise_report_node(state):
    return {"report_revision": state["report_revision"] + 1}


def finalize_node(state):
    status = "passed" if state["quality"].passed else "quality_failed"
    path = Path(state["report"].output_path).parent / "quality.json"
    payload = {"run_id": state["run"].run_id, "status": status,
               "report": state["report"].output_path,
               "evaluation_mode": "rules", "semantic_entailment_verified": False,
               "history": [q.model_dump(mode="json") for q in state["quality_history"]]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"completion_status": status}
