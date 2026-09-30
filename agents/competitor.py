"""Competitor Agent: Benchmarking products comparison and M1 valid registered patent family collection."""

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

DEFAULT_PATENT_EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "evidence" / "patent"

# Keywords Q defined by Design Spec Section 5-6
Q_KEYWORDS = [
    "그리퍼", "로봇핸드", "로봇 핸드", "robot hand", "gripper", "dexterous", "정밀조작",
    "촉각", "tactile", "힘센서", "force sensor", "force", "torque", "토크", "sensor", "센서",
    "vla", "vision-language-action", "actuator", "액추에이터", "artificial muscle",
    "섬유 구동기", "인공근육", "구동기", "조작", "manipulat"
]



def _map_evidence_status(val: str | None) -> EvidenceStatus:
    if not val:
        raise ValueError("evidence_status is required in patent evidence file")
    mapping = {
        "THIRD_PARTY": EvidenceStatus.THIRD_PARTY_VERIFIED,
        "THIRD_PARTY_VERIFIED": EvidenceStatus.THIRD_PARTY_VERIFIED,
        "SELF_REPORTED": EvidenceStatus.COMPANY_CLAIM,
        "COMPANY_CLAIM": EvidenceStatus.COMPANY_CLAIM,
        "NO_DATA": EvidenceStatus.NO_EVIDENCE,
        "NO_EVIDENCE": EvidenceStatus.NO_EVIDENCE,
    }
    if val not in mapping:
        raise ValueError(f"Unrecognized evidence_status: '{val}'")
    return mapping[val]


def _map_query_status(val: str | None) -> QueryStatus:
    if not val:
        raise ValueError("query_status is required in patent evidence file")
    mapping = {
        "DENOMINATOR_ERROR": QueryStatus.INVALID_DENOMINATOR,
        "INVALID_DENOMINATOR": QueryStatus.INVALID_DENOMINATOR,
        "SUCCESS": QueryStatus.SUCCESS,
        "NO_DATA": QueryStatus.NO_DATA,
        "ACCESS_FAILED": QueryStatus.ACCESS_FAILED,
        "TARGET_MISMATCH": QueryStatus.TARGET_MISMATCH,
    }
    if val not in mapping:
        raise ValueError(f"Unrecognized query_status: '{val}'")
    return mapping[val]


def _extract_repair_indicator_ids(control: Any, agent_owner: str = "competitor") -> list[str]:
    """Safely extract target indicator IDs from ControlState (Pydantic), dict, or EvidenceReview."""
    if not control:
        return []
    if isinstance(control, dict):
        if "repaired_indicator_ids" in control:
            return list(control["repaired_indicator_ids"])
        if "repair_targets" in control:
            result = []
            for t in control["repair_targets"]:
                if isinstance(t, dict) and t.get("owner") in (agent_owner, "*"):
                    result.extend(t.get("indicator_ids", []))
                elif hasattr(t, "owner") and getattr(t, "owner") in (agent_owner, "*"):
                    result.extend(getattr(t, "indicator_ids", []))
            return result
    if hasattr(control, "repaired_indicator_ids"):
        return list(control.repaired_indicator_ids)
    if hasattr(control, "repair_targets"):
        result = []
        for t in control.repair_targets:
            if getattr(t, "owner", "") in (agent_owner, "*"):
                result.extend(getattr(t, "indicator_ids", []))
        return result
    return []


def validate_patent_raw_value(raw_val: dict[str, Any], searched_offices: list[dict[str, Any]] | None = None) -> None:
    """Validate structural mathematical consistency of M1 patent raw values."""
    valid_count = raw_val.get("valid_registered_patents")
    unique_families = raw_val.get("unique_priority_families")
    family_ids = raw_val.get("family_ids")
    offices = searched_offices if searched_offices is not None else raw_val.get("searched_offices")

    if valid_count is None or unique_families is None or family_ids is None or offices is None:
        raise ValueError("raw_value must contain valid_registered_patents, unique_priority_families, family_ids, searched_offices")

    if len(family_ids) != unique_families:
        raise ValueError(f"len(family_ids) ({len(family_ids)}) != unique_priority_families ({unique_families})")

    if unique_families > valid_count:
        raise ValueError(f"unique_priority_families ({unique_families}) cannot exceed valid_registered_patents ({valid_count})")

    if len(offices) == 0:
        raise ValueError("searched_offices must contain at least one searched patent office record")

    # Validate Q keywords relevance in registered patents
    for pat in raw_val.get("patents", []):
        q_basis = pat.get("q_basis", "").lower().replace(" ", "")
        title = pat.get("title", "").lower().replace(" ", "")
        has_q = any(k.lower().replace(" ", "") in q_basis or k.lower().replace(" ", "") in title for k in Q_KEYWORDS)
        if not has_q:
            raise ValueError(f"Patent '{pat.get('number')}' lacks physical AI Q keyword basis in '{pat.get('q_basis')}' or '{pat.get('title')}'")


def competitor_candidate(
    candidate: Candidate,
    evidence_dir: Path | str | None = None,
    candidate_pool: list[Candidate] | None = None,
    indicator_ids: list[str] | None = None,
) -> tuple[AnalysisResult, list[SourceRecord], list[dict[str, Any]]]:
    """Collect M1 valid registered patent family count and competitor benchmarking comparison products."""
    ev_dir = Path(evidence_dir) if evidence_dir else DEFAULT_PATENT_EVIDENCE_DIR
    attempt_time = datetime.now().astimezone()

    query_attempts: list[QueryAttempt] = []
    sources: list[SourceRecord] = []

    evidence_path = ev_dir / f"{candidate.candidate_id}_patents.json"
    if not evidence_path.exists():
        # Do not silently turn uncollected files into 1-point NO_DATA; raise execution error
        raise FileNotFoundError(f"특허 원천 근거 파일 부재: {evidence_path.name} (조회 미수행)")

    with open(evidence_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Parse official Sources (fail if empty on SUCCESS)
    query_status = _map_query_status(data.get("query_status"))
    raw_sources = data.get("sources", [])
    if query_status == QueryStatus.SUCCESS and not raw_sources:
        raise ValueError(f"query_status is SUCCESS in {evidence_path.name} but sources list is empty")

    for src_raw in raw_sources:
        try:
            kind_enum = SourceKind(src_raw["kind"])
        except (KeyError, ValueError) as err:
            raise ValueError(f"Invalid SourceKind in patent source: {src_raw}") from err

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
            page=src_raw.get("page"),
            evidence_excerpt=src_raw.get("evidence_excerpt"),
        )
        sources.append(src)

    source_ids_set = {s.source_id for s in sources}

    # 2. Parse query status & raw value strictly
    raw_val = data.get("raw_value")
    missing_reason = data.get("missing_reason")

    if query_status != QueryStatus.SUCCESS:
        raw_val = None
        ev_status = EvidenceStatus.NO_EVIDENCE
        if not missing_reason:
            missing_reason = f"특허 조회 실패 ({query_status.value})"
    else:
        if raw_val is None:
            raise ValueError(f"M1: query_status is SUCCESS in {evidence_path.name} but raw_value is None")
        searched_offices_data = data.get("searched_offices") or (raw_val.get("searched_offices") if isinstance(raw_val, dict) else None)
        validate_patent_raw_value(raw_val, searched_offices=searched_offices_data)
        ev_status = _map_evidence_status(data.get("evidence_status"))
        missing_reason = None

    as_of_val = date.fromisoformat(data["as_of"]) if data.get("as_of") else date.today()

    # Determine source_ids strictly from registered patents or top sources
    m1_source_ids: list[str] = []
    if raw_val and isinstance(raw_val, dict):
        for pat in raw_val.get("patents", []):
            m1_source_ids.extend(pat.get("source_ids", []))
    if not m1_source_ids and sources:
        m1_source_ids = [sources[0].source_id]

    m1_source_ids = sorted(list(set(m1_source_ids)))

    # Verify all m1_source_ids exist in sources
    missing_srcs = set(m1_source_ids) - source_ids_set
    if missing_srcs:
        raise ValueError(f"Indicator M1 references source_ids not found in sources: {missing_srcs}")

    m1_evidence = IndicatorEvidence(
        id="M1",
        raw_value=raw_val,
        unit=data.get("unit", "특허 패밀리"),
        period=None,
        as_of=as_of_val,
        evidence_status=ev_status,
        source_ids=m1_source_ids,
        collected_by="competitor",
        query_status=query_status,
        missing_reason=missing_reason,
    )

    # 3. Parse comparison products (benchmarks)
    comparison_products = data.get("comparison_products", [])

    # Verify that comparison companies are strictly disjoint from investment candidate pool
    if candidate_pool:
        candidate_identifiers = {c.legal_name for c in candidate_pool} | {c.candidate_id for c in candidate_pool}
        for cp in comparison_products:
            comp_name = cp.get("company", "")
            if comp_name in candidate_identifiers:
                raise ValueError(
                    f"비교 기업 '{comp_name}'은(는) 투자 평가 대상 후보군에 포함되어 있어 벤치마크 기업으로 사용할 수 없습니다."
                )

    # Verify that all comparison_product source_ids exist in sources
    for cp in comparison_products:
        cp_sources = cp.get("attributes", {}).get("source_ids", [])
        missing_cp_srcs = set(cp_sources) - source_ids_set
        if missing_cp_srcs:
            raise ValueError(f"comparison_product '{cp.get('company')}' references unknown source_ids: {missing_cp_srcs}")

    # Build authentic query attempt from evidence metadata
    searched_queries = []
    offices_list = data.get("searched_offices") or (raw_val.get("searched_offices", []) if raw_val and isinstance(raw_val, dict) else [])
    for off in offices_list:
        searched_queries.append(f"{off.get('office')}: {off.get('query')}")
    query_str = " | ".join(searched_queries) if searched_queries else f"assignee={candidate.legal_name}"

    checked_by = data.get("checked_by", "담당자")
    searched_at_str = data.get("searched_at")
    attempt_dt = datetime.fromisoformat(searched_at_str) if searched_at_str else attempt_time

    attempt_note = (
        f"KIPRIS 특허 조회 완료 (확인자: {checked_by})"
        if query_status == QueryStatus.SUCCESS
        else f"특허 조회 상태 {query_status.value}: {missing_reason} (확인자: {checked_by})"
    )

    attempt = QueryAttempt(
        query=query_str,
        status=query_status,
        attempted_at=attempt_dt,
        result_count=raw_val.get("valid_registered_patents", 0) if isinstance(raw_val, dict) else 0,
        note=attempt_note,
    )
    query_attempts.append(attempt)

    # Summary: Must NOT say "0개 패밀리" when query failed!
    comp_count = len(comparison_products)
    if query_status != QueryStatus.SUCCESS:
        summary = (
            f"{candidate.legal_name}(소재국: {candidate.country})의 특허 공식 권리정보 조회 상태: "
            f"{query_status.value} (사유: {missing_reason}). 벤치마크 비교 제품 {comp_count}개 수집."
        )
    else:
        pat_count = raw_val["unique_priority_families"]
        summary = (
            f"{candidate.legal_name}(소재국: {candidate.country})의 특허청 공식 권리자 기준 Q 유효 등록 특허 "
            f"{pat_count}개 패밀리 및 {comp_count}개 벤치마크 제품 비교 기록."
        )

    all_source_ids = sorted(list(source_ids_set))

    analysis = AnalysisResult(
        candidate_id=candidate.candidate_id,
        summary=summary,
        indicators=[m1_evidence],
        source_ids=all_source_ids,
        query_attempts=query_attempts,
    )

    return analysis, sources, comparison_products


def competitor_node(state: GraphState) -> AgentNodeUpdate:
    """LangGraph node: Collects competitor benchmark and M1 patent family count, updating competitor_analysis."""
    candidate = state.get("current_candidate")
    if candidate is None:
        raise ValueError("current_candidate is required in GraphState for competitor_node")

    candidate_pool = state.get("candidates")

    # Support repair targeting
    control = state.get("control")
    target_ids = _extract_repair_indicator_ids(control, agent_owner="competitor")

    analysis, sources, comp_products = competitor_candidate(
        candidate=candidate,
        candidate_pool=candidate_pool,
        indicator_ids=target_ids if "M1" in target_ids else None,
    )

    update: AgentNodeUpdate = {
        "competitor_analysis": analysis,
        "sources": sources,
    }

    if comp_products:
        update["comparison_products"] = comp_products

    return update
