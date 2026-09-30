"""Discover Agent: Candidate corporate facts, G1 qualification items, and T1/R1/R3/F1~F3 raw values."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from schemas import (
    AgentNodeUpdate,
    AnalysisResult,
    Candidate,
    EvidenceStatus,
    GraphState,
    IndicatorEvidence,
    QueryAttempt,
    QueryStatus,
    SourceKind,
    SourceRecord,
)

DEFAULT_COMPANY_EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "evidence" / "company"

ALL_DISCOVER_INDICATORS = ["G1", "T1", "R1", "R3", "F1", "F2", "F3"]

INDICATOR_DEFAULT_UNITS = {
    "G1": "4개 요건 사실",
    "T1": "명",
    "R1": "원",
    "R3": "명",
    "F1": "원",
    "F2": "원",
    "F3": "건",
}


def _map_evidence_status(val: str) -> EvidenceStatus:
    mapping = {
        "THIRD_PARTY": EvidenceStatus.THIRD_PARTY_VERIFIED,
        "THIRD_PARTY_VERIFIED": EvidenceStatus.THIRD_PARTY_VERIFIED,
        "SELF_REPORTED": EvidenceStatus.COMPANY_CLAIM,
        "COMPANY_CLAIM": EvidenceStatus.COMPANY_CLAIM,
        "NO_DATA": EvidenceStatus.NO_EVIDENCE,
        "NO_EVIDENCE": EvidenceStatus.NO_EVIDENCE,
    }
    if val in mapping:
        return mapping[val]
    return EvidenceStatus(val)


def _map_query_status(val: str) -> QueryStatus:
    mapping = {
        "DENOMINATOR_ERROR": QueryStatus.INVALID_DENOMINATOR,
        "INVALID_DENOMINATOR": QueryStatus.INVALID_DENOMINATOR,
        "SUCCESS": QueryStatus.SUCCESS,
        "NO_DATA": QueryStatus.NO_DATA,
        "ACCESS_FAILED": QueryStatus.ACCESS_FAILED,
        "TARGET_MISMATCH": QueryStatus.TARGET_MISMATCH,
    }
    if val in mapping:
        return mapping[val]
    return QueryStatus(val)


def build_indicator(
    ind_id: str,
    section: dict[str, Any] | None,
    default_unit: str | None = None,
) -> IndicatorEvidence:
    """Build an IndicatorEvidence strictly from an evidence section without guessing."""
    if not section:
        return IndicatorEvidence(
            id=ind_id,
            raw_value=None,
            unit=None,
            period=None,
            as_of=None,
            evidence_status=EvidenceStatus.NO_EVIDENCE,
            source_ids=[],
            collected_by="discover",
            query_status=QueryStatus.NO_DATA,
            missing_reason=f"{ind_id} 근거 섹션이 evidence 파일에 없음",
        )

    query_status = _map_query_status(section.get("query_status", "SUCCESS"))
    raw_val = section.get("raw_value")
    missing_reason = section.get("missing_reason")
    unit = section.get("unit", default_unit)

    if query_status != QueryStatus.SUCCESS:
        raw_val = None
        ev_status = EvidenceStatus.NO_EVIDENCE
        if not missing_reason:
            missing_reason = f"{ind_id} 조회 실패 또는 불완전 ({query_status.value})"
    else:
        if raw_val is None:
            raise ValueError(f"{ind_id}: query_status is SUCCESS but raw_value is None")
        ev_status = _map_evidence_status(section.get("evidence_status", "THIRD_PARTY_VERIFIED"))
        missing_reason = None

    as_of_val: date | None = None
    if section.get("as_of"):
        as_of_val = date.fromisoformat(section["as_of"])

    return IndicatorEvidence(
        id=ind_id,
        raw_value=raw_val,
        unit=unit,
        period=section.get("period"),
        as_of=as_of_val,
        evidence_status=ev_status,
        source_ids=list(section.get("source_ids", [])),
        collected_by="discover",
        query_status=query_status,
        missing_reason=missing_reason,
    )


def replace_indicators(
    existing: AnalysisResult,
    repaired_indicators: list[IndicatorEvidence],
    new_query_attempts: list[QueryAttempt] | None = None,
) -> AnalysisResult:
    """Replace specific indicators while preserving other verified indicators and merging query attempts."""
    new_map = {ind.id: ind for ind in repaired_indicators}
    merged_indicators = [
        new_map[ind.id] if ind.id in new_map else ind
        for ind in existing.indicators
    ]
    existing_ids = {ind.id for ind in existing.indicators}
    for ind in repaired_indicators:
        if ind.id not in existing_ids:
            merged_indicators.append(ind)

    all_source_ids = sorted(
        {src_id for ind in merged_indicators for src_id in ind.source_ids}
        | set(existing.source_ids)
    )

    merged_attempts = list(existing.query_attempts)
    if new_query_attempts:
        merged_attempts.extend(new_query_attempts)

    return AnalysisResult(
        candidate_id=existing.candidate_id,
        summary=existing.summary,
        indicators=merged_indicators,
        source_ids=all_source_ids,
        query_attempts=merged_attempts,
    )


def discover_candidate(
    candidate: Candidate,
    evidence_dir: Path | str | None = None,
    indicator_ids: list[str] | None = None,
) -> tuple[AnalysisResult, list[SourceRecord], list[dict[str, Any]]]:
    """Collect candidate facts strictly from verified evidence files without evaluation judgments."""
    target_indicators = indicator_ids or ALL_DISCOVER_INDICATORS

    ev_dir = Path(evidence_dir) if evidence_dir else DEFAULT_COMPANY_EVIDENCE_DIR
    evidence_path = ev_dir / f"{candidate.candidate_id}.json"

    query_attempts: list[QueryAttempt] = []
    sources: list[SourceRecord] = []
    indicators: list[IndicatorEvidence] = []
    handoff_urls: list[dict[str, Any]] = []

    attempt_time = datetime.now().astimezone()

    if not evidence_path.exists():
        attempt = QueryAttempt(
            query=f"candidate_id={candidate.candidate_id} targets={','.join(target_indicators)}",
            status=QueryStatus.NO_DATA,
            attempted_at=attempt_time,
            result_count=0,
            note="No corporate evidence file found in data/evidence/company/",
        )
        query_attempts.append(attempt)

        for ind_id in target_indicators:
            indicators.append(
                IndicatorEvidence(
                    id=ind_id,
                    raw_value=None,
                    unit=None,
                    evidence_status=EvidenceStatus.NO_EVIDENCE,
                    source_ids=[],
                    collected_by="discover",
                    query_status=QueryStatus.NO_DATA,
                    missing_reason="기업 원천 근거 파일(evidence) 부재",
                )
            )

        summary = f"{candidate.legal_name}(식별자: {candidate.legal_id}, 국가: {candidate.country}) 자료 미확인"
        analysis = AnalysisResult(
            candidate_id=candidate.candidate_id,
            summary=summary,
            indicators=indicators,
            source_ids=[],
            query_attempts=query_attempts,
        )
        return analysis, sources, handoff_urls

    with open(evidence_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Parse Sources strictly (fail if kind is invalid)
    for src_raw in data.get("sources", []):
        try:
            kind_enum = SourceKind(src_raw["kind"])
        except (KeyError, ValueError) as err:
            raise ValueError(f"Invalid or missing SourceKind in source: {src_raw}") from err

        col_at = (
            datetime.fromisoformat(src_raw["collected_at"])
            if src_raw.get("collected_at")
            else attempt_time
        )
        pub_at = (
            date.fromisoformat(src_raw["published_at"])
            if src_raw.get("published_at")
            else None
        )

        src = SourceRecord(
            source_id=src_raw["source_id"],
            kind=kind_enum,
            publisher=src_raw["publisher"],
            title=src_raw["title"],
            url=src_raw.get("url"),
            published_at=pub_at,
            collected_at=col_at,
            response_id=src_raw.get("response_id"),
            evidence_excerpt=src_raw.get("evidence_excerpt"),
        )
        sources.append(src)

    # 2. Build indicators from individual sections
    indicator_sections = data.get("indicators", {})
    for ind_id in target_indicators:
        section = indicator_sections.get(ind_id)
        default_unit = INDICATOR_DEFAULT_UNITS.get(ind_id)
        ind_evidence = build_indicator(ind_id, section, default_unit=default_unit)
        indicators.append(ind_evidence)

    # 3. Collect handoff URLs
    handoff_urls = data.get("handoff_urls", [])

    # 4. Record query attempt
    attempt = QueryAttempt(
        query=f"candidate_id={candidate.candidate_id} targets={','.join(target_indicators)}",
        status=QueryStatus.SUCCESS,
        attempted_at=attempt_time,
        result_count=len(sources),
        note=f"Loaded facts for {len(indicators)} indicators from {evidence_path.name}",
    )
    query_attempts.append(attempt)

    all_source_ids = sorted({src_id for ind in indicators for src_id in ind.source_ids})

    # Summary: strictly factual metadata only, no evaluation/qualification adjectives
    summary = f"{candidate.legal_name}(식별자: {candidate.legal_id}, 소재국: {candidate.country})의 법인·투자·고용·재무·제재 수집 기록"

    analysis = AnalysisResult(
        candidate_id=candidate.candidate_id,
        summary=summary,
        indicators=indicators,
        source_ids=all_source_ids,
        query_attempts=query_attempts,
    )

    return analysis, sources, handoff_urls


def discover_node(state: GraphState) -> AgentNodeUpdate:
    """LangGraph node: Collects candidate facts and returns company_profile, sources, and handoff_urls."""
    candidate = state.get("current_candidate")
    if candidate is None:
        raise ValueError("current_candidate is required in GraphState for discover_node")

    # Support repair targets if specified in control
    control = state.get("control")
    target_ids = None
    if control and control.repaired_indicator_ids:
        discover_targets = [ind_id for ind_id in control.repaired_indicator_ids if ind_id in ALL_DISCOVER_INDICATORS]
        if discover_targets:
            target_ids = discover_targets

    analysis, sources, handoff_urls = discover_candidate(candidate, indicator_ids=target_ids)

    # If repairing, merge with existing company_profile
    if target_ids and state.get("company_profile"):
        analysis = replace_indicators(
            existing=state["company_profile"],
            repaired_indicators=analysis.indicators,
            new_query_attempts=analysis.query_attempts,
        )

    update: AgentNodeUpdate = {
        "company_profile": analysis,
        "sources": sources,
    }
    # Pass handoff_urls along in update dictionary for downstream nodes
    if handoff_urls:
        update["handoff_urls"] = handoff_urls

    return update
