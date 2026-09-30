"""Offline report smoke test using explicitly fictional, already-scored State.

Run: python -m reporting.demo --output /tmp/physical-agent-demo.pdf
The values below test rendering only; they do not implement the judge's rules.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from schemas import (
    Candidate, Decision, EvaluationRecord, GateResult, IndicatorEvidence,
    RunConfig, SourceRecord,
)
from reporting.renderer import render_investment_report


def demo_state(count=2):
    source = SourceRecord(
        source_id="demo_fixture", kind="MANUAL", publisher="테스트 작성자",
        title="가상 데이터 · 실제 기업 사실 아님", url="https://example.invalid/demo",
        collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
        evidence_excerpt="PDF 렌더링을 검증하기 위한 가상 수치와 시험 조건.")
    candidates, evaluations = [], []
    for number in range(1, count + 1):
        cid = f"가상후보{number}"
        candidates.append(Candidate(candidate_id=cid, legal_name=cid, country="KR",
            legal_id=f"DEMO-{number}", founded_at=date(2020, 1, 1), primary_segment="정밀 조작 그리퍼",
            latest_round="Seed", listing_sources=["가상 조회"], registry_sources=["가상 조회"]))
        k2 = IndicatorEvidence(id="K2", raw_value={"successful_trials": 28,
            "total_trials": 30, "success_rate_percent": 93.33}, unit="%", period="2026-03-01",
            condition={"task": "배터리 셀 집기", "environment": "실험실 실제 로봇",
                       "success_definition": "손상 없이 지정 위치 이동", "independent_reproduction": False},
            evidence_status="COMPANY_CLAIM", source_ids=["demo_fixture"], collected_by="tech", query_status="SUCCESS")
        unknown = IndicatorEvidence(id="F4", raw_value=None, evidence_status="NO_EVIDENCE",
            collected_by="synergy", query_status="NO_DATA", missing_reason="방폭 공정 및 장비 인증 미확인")
        raw_values = {"T1": 1, "T2": {"paper_count": 1, "founder_count": 2, "papers_per_founder": "0.5"},
            "K1": 2, "K3": 1, "S1": {"performed_task_count": 1, "task_ids": ["TASK3"]},
            "S2": {"matched_task_count": 0, "matches": []},
            "P1": {"base_year": 2022, "latest_year": 2025, "base_revenue": 100, "latest_revenue": 120},
            "R1": 10, "R2": {"amount_krw": "100000000", "amount_100m_krw": "1"},
            "R3": {"baseline_employees": 10, "latest_employees": 12}, "M1": 1}
        units = {"T1": "명", "K1": "편", "K3": "현장", "P1": "억 원", "R1": "억 원", "R3": "명", "M1": "패밀리"}
        raw_indicators = [IndicatorEvidence(id=key, raw_value=value, unit=units.get(key), evidence_status="THIRD_PARTY_VERIFIED",
            source_ids=["demo_fixture"], collected_by="demo", query_status="SUCCESS")
            for key, value in raw_values.items()]
        risks = [unknown.model_copy(update={"id": key, "missing_reason": "가상 데이터에 재무·공식 조회 자료 없음"})
                 for key in ("F1", "F2", "F3")]
        evaluations.append(EvaluationRecord(candidate_id=cid, country="KR", primary_segment="정밀 조작 그리퍼",
            rule_version="demo-only", indicators=[k2, *raw_indicators, *risks, unknown],
            indicator_scores={"T1": 3, "T2": 2, "K1": 3, "K2": 3, "K3": 2, "S1": 2,
                              "S2": 1, "P1": 3, "R1": 2, "R2": 2, "R3": 3, "M1": 2},
            category_scores={"team": Decimal("2.50"), "tech": Decimal("2.67"), "synergy": Decimal("1.50"),
                             "market": Decimal("3.00"), "traction": Decimal("2.33"), "moat": Decimal("2.00")},
            gates={g: GateResult(passed=g != "G2", reasons=["가상 게이트 결과"], source_ids=["demo_fixture"],
                unknown_items=["현장 인증 확인 필요"] if g == "G3" else []) for g in ("G1", "G2", "G3")},
            total_score=Decimal("46.7"), decision=Decision(status="HOLD", reasons=["모기업 작업 연결 근거 부족"]),
            evidence_coverage=Decimal("0.75"), unknown_items=["모기업 연결", "현장 인증"],
            due_diligence_items=["고객 확인 시험과 공정별 인증 원문 확보"],
            metadata={"review_completed": True, "scoring_completed": True, "synthetic": True}))
    return {"run": RunConfig(run_id="demo", evaluation_date=date(2026, 9, 30), rule_version="demo-only",
                             document_version="synthetic"),
            "current_candidate": candidates[0], "candidates": candidates, "evaluations": evaluations,
            "sources": [source]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = demo_state()
    path = render_investment_report(state["evaluations"], state["sources"], args.output,
        evaluation_date=state["run"].evaluation_date, demo=True)
    print(f"가상 데이터 검증용 PDF: {path}\n원본 State JSON: {path.with_suffix('.json')}")


if __name__ == "__main__":
    main()
