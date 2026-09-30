from datetime import date, datetime, timezone
from typing import Any

from graph.builder import NodeBindings, build_graph
from schemas import (
    AnalysisResult,
    Candidate,
    EvidenceStatus,
    IndicatorEvidence,
    QueryStatus,
    ReportResult,
    RunConfig,
    SourceKind,
    SourceRecord,
)


SOURCE = SourceRecord(
    source_id="source-1",
    kind=SourceKind.WEB,
    publisher="Publisher",
    title="Evidence",
    url="https://example.com/evidence",
    collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
)


def indicator(
    indicator_id: str,
    raw_value: Any,
    owner: str,
    condition: dict[str, Any] | None = None,
    period: str | None = None,
) -> IndicatorEvidence:
    missing = raw_value is None
    return IndicatorEvidence(
        id=indicator_id,
        raw_value=raw_value,
        unit="test",
        period=period,
        condition=condition or {},
        evidence_status=(
            EvidenceStatus.NO_EVIDENCE
            if missing
            else EvidenceStatus.THIRD_PARTY_VERIFIED
        ),
        source_ids=[] if missing else [SOURCE.source_id],
        collected_by=owner,
        query_status=QueryStatus.NO_DATA if missing else QueryStatus.SUCCESS,
        missing_reason="자료 없음" if missing else None,
    )


def analysis(candidate_id: str, values: list[IndicatorEvidence]) -> AnalysisResult:
    source_ids = list(
        dict.fromkeys(
            source_id
            for item in values
            for source_id in item.source_ids
        )
    )
    return AnalysisResult(
        candidate_id=candidate_id,
        summary="분석 결과",
        indicators=values,
        source_ids=source_ids,
    )


def g1_raw(unlisted: bool) -> dict[str, Any]:
    return {
        "unlisted": {"value": unlisted, "source_id": SOURCE.source_id},
        "latest_round": {"value": "Series A", "source_id": SOURCE.source_id},
        "exit_completed": {"value": False, "source_id": SOURCE.source_id},
        "operating_status": {"value": "정상", "source_id": SOURCE.source_id},
    }


def discover_node(state):
    candidate = state["current_candidate"]
    is_first = candidate.candidate_id == "candidate-1"
    values = [
        indicator("G1", g1_raw(is_first), "discover"),
        indicator("T1", 3, "discover"),
        indicator("R1", 150, "discover"),
        indicator("R3", 60, "discover", period="2025-2026"),
        indicator("F1", 24, "discover"),
        indicator("F2", {"impairment_rate": 0, "debt_ratio": 50}, "discover"),
        indicator("F3", 0, "discover", period="2021-2026"),
    ]
    return {
        "company_profile": analysis(candidate.candidate_id, values),
        "sources": [SOURCE],
    }


def tech_node(state):
    candidate_id = state["current_candidate"].candidate_id
    repaired = state.get("evidence_review") is not None
    values = [
        indicator("T2", 4, "tech", period="2021-2026"),
        indicator("K1", 5, "tech", period="2021-2026"),
        indicator(
            "K2",
            95 if repaired else None,
            "tech",
            condition={"total_attempts": 30} if repaired else {},
        ),
        indicator("K3", 5, "tech", period="2023-2026"),
        indicator("R2", 30, "tech", period="2023-2026"),
    ]
    return {"tech_analysis": analysis(candidate_id, values)}


def market_node(state):
    candidate_id = state["current_candidate"].candidate_id
    return {
        "market_analysis": analysis(
            candidate_id,
            [indicator("P1", 20, "market", period="2023-2026")],
        )
    }


def competitor_node(state):
    candidate_id = state["current_candidate"].candidate_id
    return {
        "competitor_analysis": analysis(
            candidate_id,
            [indicator("M1", 7, "competitor")],
        )
    }


def synergy_node(state):
    candidate_id = state["current_candidate"].candidate_id
    return {
        "synergy_analysis": analysis(
            candidate_id,
            [
                indicator("S1", 4, "synergy", condition={"tasks": ["TASK1"]}),
                indicator("S2", 4, "synergy", condition={"tasks": ["TASK1"]}),
                indicator(
                    "F4",
                    {"explosive_area": False},
                    "synergy",
                    condition={"process": "test"},
                ),
            ],
        )
    }


def report_node(state):
    return {
        "report": ReportResult(
            output_path="reporting/output/investment_report.pdf",
            source_ids=[SOURCE.source_id],
        )
    }


def candidates() -> list[Candidate]:
    return [
        Candidate(
            candidate_id=f"candidate-{index}",
            legal_name=f"Company {index}",
            country="KR",
            legal_id=f"legal-{index}",
            founded_at=date(2020, 1, 1),
            primary_segment="robot-hand",
            latest_round="Series A",
            listing_sources=["listing"],
            registry_sources=["registry"],
        )
        for index in (1, 2)
    ]


def test_graph_repairs_once_and_processes_all_candidates() -> None:
    graph = build_graph(
        NodeBindings(
            discover=discover_node,
            tech=tech_node,
            market=market_node,
            competitor=competitor_node,
            synergy=synergy_node,
            report=report_node,
        )
    )
    result = graph.invoke(
        {
            "run": RunConfig(
                run_id="run-1",
                evaluation_date=date(2026, 9, 30),
                rule_version="1.0.0",
                document_version="1.0.0",
            ),
            "candidates": candidates(),
        }
    )

    assert len(result["evaluations"]) == 2
    assert result["evaluations"][0].decision.status.value == "INVEST"
    assert result["evaluations"][1].decision.status.value == "HOLD"
    assert result["evaluations"][1].total_score is None
    assert result["report"].output_path.endswith("investment_report.pdf")
