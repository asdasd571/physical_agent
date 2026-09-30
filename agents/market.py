"""Market Agent: Korean adoption market statistics and P1 3-year CAGR raw value collection."""

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

DEFAULT_MARKET_EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "evidence" / "market"

# Segment mapping rules strictly according to Design Spec 5-8
PARTS_SEGMENTS = {
    "robot_hand",
    "dexterous_hand",
    "gripper",
    "force_tactile_sensor",
    "tactile_sensor",
    "sensor",
    "actuator",
    "artificial_muscle",
    "robot_parts",
}

MANUFACTURING_ROBOT_SEGMENTS = {
    "humanoid",
    "humanoid_manipulation",
    "manipulator",
    "manufacturing_robot",
    "industrial_robot",
}

VLA_AI_SEGMENTS = {
    "vla",
    "vision_language_action",
    "ai_software",
    "manipulation_ai",
}


def map_segment_to_evidence_key(segment: str) -> str | None:
    """Map candidate primary segment to official Korean statistics category."""
    norm = segment.strip().lower().replace("-", "_").replace(" ", "_")
    if norm in PARTS_SEGMENTS:
        return "robot_parts"
    if norm in MANUFACTURING_ROBOT_SEGMENTS:
        return "manufacturing_robot"
    if norm in VLA_AI_SEGMENTS:
        # VLA software has no direct corresponding KOSIS category -> None (NO_DATA)
        return "VLA_NO_DATA"
    return None


def calculate_cagr(start_val: float, end_val: float, years: int = 3) -> float:
    """Calculate CAGR percentage rounded to two decimal places."""
    if start_val <= 0 or years <= 0:
        raise ValueError("start_val and years must be positive for CAGR calculation")
    cagr = ((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0
    return round(cagr, 2)


def market_candidate(
    candidate: Candidate,
    evidence_dir: Path | str | None = None,
    tech_analysis: AnalysisResult | None = None,
    indicator_ids: list[str] | None = None,
) -> tuple[AnalysisResult, list[SourceRecord], list[dict[str, Any]]]:
    """Collect P1 market statistics strictly based on official Korean adoption market data."""
    ev_dir = Path(evidence_dir) if evidence_dir else DEFAULT_MARKET_EVIDENCE_DIR
    attempt_time = datetime.now().astimezone()

    query_attempts: list[QueryAttempt] = []
    sources: list[SourceRecord] = []
    reference_market_info: list[dict[str, Any]] = []

    seg_key = map_segment_to_evidence_key(candidate.primary_segment)

    # Case 1: VLA software without direct category mapping -> strictly NO_DATA
    if seg_key == "VLA_NO_DATA":
        missing_reason = (
            "VLA 조작 지능 소프트웨어에 직접 대응하는 한국 공식 통계 분류가 확인되지 않아 임의 배정하지 않음 (설계서 5-8 준수)"
        )
        attempt = QueryAttempt(
            query=f"candidate={candidate.candidate_id} segment={candidate.primary_segment} Korean market stats",
            status=QueryStatus.NO_DATA,
            attempted_at=attempt_time,
            result_count=0,
            note=missing_reason,
        )
        query_attempts.append(attempt)

        p1_evidence = IndicatorEvidence(
            id="P1",
            raw_value=None,
            unit=None,
            period=None,
            as_of=date.today(),
            evidence_status=EvidenceStatus.NO_EVIDENCE,
            source_ids=[],
            collected_by="market",
            query_status=QueryStatus.NO_DATA,
            missing_reason=missing_reason,
        )

        summary = (
            f"{candidate.legal_name}의 주력 세그먼트({candidate.primary_segment})에 직접 대응하는 한국 공식 통계 분류가 부재하여 "
            "임의 배정하지 않고 자료 없음으로 처리함."
        )

        analysis = AnalysisResult(
            candidate_id=candidate.candidate_id,
            summary=summary,
            indicators=[p1_evidence],
            source_ids=[],
            query_attempts=query_attempts,
        )
        return analysis, sources, reference_market_info

    # Case 2: Completely unknown segment -> TARGET_MISMATCH
    if seg_key is None:
        missing_reason = f"주력 세그먼트 '{candidate.primary_segment}'에 대응하는 한국 도입 시장 통계 분류를 찾지 못함"
        attempt = QueryAttempt(
            query=f"candidate={candidate.candidate_id} segment={candidate.primary_segment}",
            status=QueryStatus.TARGET_MISMATCH,
            attempted_at=attempt_time,
            result_count=0,
            note=missing_reason,
        )
        query_attempts.append(attempt)

        p1_evidence = IndicatorEvidence(
            id="P1",
            raw_value=None,
            unit=None,
            period=None,
            as_of=date.today(),
            evidence_status=EvidenceStatus.NO_EVIDENCE,
            source_ids=[],
            collected_by="market",
            query_status=QueryStatus.TARGET_MISMATCH,
            missing_reason=missing_reason,
        )

        summary = f"{candidate.legal_name}의 세그먼트({candidate.primary_segment}) 매핑 불일치"
        analysis = AnalysisResult(
            candidate_id=candidate.candidate_id,
            summary=summary,
            indicators=[p1_evidence],
            source_ids=[],
            query_attempts=query_attempts,
        )
        return analysis, sources, reference_market_info

    # Case 3: Official mapped statistics file
    target_file = (
        ev_dir / "robot_parts_sales_2022_2025.json"
        if seg_key == "robot_parts"
        else ev_dir / "manufacturing_robot_sales_2022_2025.json"
    )

    if not target_file.exists():
        missing_reason = f"공식 시장 통계 원천 파일 부재 ({target_file.name})"
        attempt = QueryAttempt(
            query=f"evidence_file={target_file.name}",
            status=QueryStatus.NO_DATA,
            attempted_at=attempt_time,
            result_count=0,
            note=missing_reason,
        )
        query_attempts.append(attempt)

        p1_evidence = IndicatorEvidence(
            id="P1",
            raw_value=None,
            unit=None,
            period=None,
            as_of=date.today(),
            evidence_status=EvidenceStatus.NO_EVIDENCE,
            source_ids=[],
            collected_by="market",
            query_status=QueryStatus.NO_DATA,
            missing_reason=missing_reason,
        )

        analysis = AnalysisResult(
            candidate_id=candidate.candidate_id,
            summary=f"시장 통계 자료 부재 ({candidate.primary_segment})",
            indicators=[p1_evidence],
            source_ids=[],
            query_attempts=query_attempts,
        )
        return analysis, sources, reference_market_info

    with open(target_file, "r", encoding="utf-8") as f:
        stat_data = json.load(f)

    # Parse official SourceRecord
    src_raw = stat_data["source"]
    try:
        kind_enum = SourceKind(src_raw["kind"])
    except (KeyError, ValueError) as err:
        raise ValueError(f"Invalid SourceKind in market source: {src_raw}") from err

    src = SourceRecord(
        source_id=src_raw["source_id"],
        kind=kind_enum,
        publisher=src_raw["publisher"],
        title=src_raw["title"],
        url=src_raw.get("url"),
        published_at=date.fromisoformat(src_raw["published_at"]) if src_raw.get("published_at") else None,
        collected_at=datetime.fromisoformat(src_raw["collected_at"]) if src_raw.get("collected_at") else attempt_time,
        page=src_raw.get("page"),
        evidence_excerpt=src_raw.get("evidence_excerpt"),
    )
    sources.append(src)

    # Validate denominator and calculate CAGR
    start_rev = stat_data.get("start_revenue", 0)
    end_rev = stat_data.get("end_revenue", 0)
    start_yr = stat_data.get("start_year", 2022)
    end_yr = stat_data.get("end_year", 2025)

    if start_rev <= 0:
        p1_evidence = IndicatorEvidence(
            id="P1",
            raw_value=None,
            unit="원",
            period=f"{start_yr}-{end_yr}",
            as_of=date.fromisoformat(stat_data["as_of"]),
            evidence_status=EvidenceStatus.NO_EVIDENCE,
            source_ids=[src.source_id],
            collected_by="market",
            query_status=QueryStatus.INVALID_DENOMINATOR,
            missing_reason=f"시작연도({start_yr}) 매출 원값이 0 이하로 CAGR 분모 오류 발생",
        )
    else:
        cagr = calculate_cagr(start_rev, end_rev, years=end_yr - start_yr)
        raw_val = {
            "product_segment": candidate.primary_segment,
            "stat_segment": stat_data["stat_segment"],
            "stat_table": stat_data["stat_table"],
            "start_year": start_yr,
            "end_year": end_yr,
            "start_revenue": start_rev,
            "end_revenue": end_rev,
            "unit_original": stat_data["unit"],
            "cagr_percent": cagr,
            "mapping_note": None,
        }

        p1_evidence = IndicatorEvidence(
            id="P1",
            raw_value=raw_val,
            unit=stat_data["unit"],
            period=f"{start_yr}-{end_yr}",
            as_of=date.fromisoformat(stat_data["as_of"]),
            evidence_status=EvidenceStatus.THIRD_PARTY_VERIFIED,
            source_ids=[src.source_id],
            collected_by="market",
            query_status=QueryStatus.SUCCESS,
            missing_reason=None,
        )

    # Collect reference market info (global stats)
    reference_market_info = stat_data.get("reference_market_info", [])

    attempt = QueryAttempt(
        query=f"candidate={candidate.candidate_id} segment={candidate.primary_segment} stat_segment={stat_data['stat_segment']}",
        status=QueryStatus.SUCCESS,
        attempted_at=attempt_time,
        result_count=1,
        note=f"Loaded official stats from {target_file.name}",
    )
    query_attempts.append(attempt)

    summary = (
        f"한국로봇산업진흥원 공식 통계의 '{stat_data['stat_segment']}' 부문({start_yr}~{end_yr}) 매출 원값 수집. "
        "이 수치는 세그먼트의 과거 성장세를 나타내는 대리값이며 후보 기업의 미래 매출이나 시장 절대 규모를 뜻하지 않음."
    )

    analysis = AnalysisResult(
        candidate_id=candidate.candidate_id,
        summary=summary,
        indicators=[p1_evidence],
        source_ids=[src.source_id],
        query_attempts=query_attempts,
    )

    return analysis, sources, reference_market_info


def market_node(state: GraphState) -> AgentNodeUpdate:
    """LangGraph node: Collects P1 Korean market growth statistics and updates market_analysis."""
    candidate = state.get("current_candidate")
    if candidate is None:
        raise ValueError("current_candidate is required in GraphState for market_node")

    tech_analysis = state.get("tech_analysis")

    # Check repair targets
    control = state.get("control")
    target_ids = None
    if control and control.repaired_indicator_ids:
        if "P1" in control.repaired_indicator_ids:
            target_ids = ["P1"]

    analysis, sources, ref_info = market_candidate(
        candidate=candidate,
        tech_analysis=tech_analysis,
        indicator_ids=target_ids,
    )

    update: AgentNodeUpdate = {
        "market_analysis": analysis,
        "sources": sources,
    }

    if ref_info:
        update["reference_market_info"] = ref_info

    return update
