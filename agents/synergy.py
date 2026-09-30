"""Link independently demonstrated tasks to public parent-company demand."""
from __future__ import annotations

from agents.tech import (
    ROOT, _cached_update, _collect, _complete, _date, _finish, _ids, _missing, _value,
)
from rag import search_documents
from schemas import AgentNodeUpdate, GraphState, QueryStatus, SourceKind

TASKS = {
    "TASK1": "비정형 물체 집기", "TASK2": "밸브·레버 조작",
    "TASK3": "배터리 셀·모듈 핸들링", "TASK4": "케이블·커넥터·부품 체결",
    "TASK5": "시료·용기·위험물 취급",
}
QUERIES = {
    "S1": "제조 작업 실제 수행 고객 정부 독립 확인 TASK1 TASK2 TASK3 TASK4 TASK5",
    "S2": "모기업 공개 보고서 작업 수요 공정 페이지 비정형 집기 밸브 배터리 체결 시료",
    "F4": "파일럿 공정 방폭 구역 장비 모델 KCs IECEx 인증 범위 유효기간 취득 진행",
}


def make_synergy_node(*, search=None, extractor=None, evidence_dir=None, parent_dir=None):
    def node(state: GraphState) -> AgentNodeUpdate:
        cached = _cached_update(state, "synergy")
        if cached is not None:
            return cached
        c, today, records, coverage, sources, attempts = _collect(
            state, "synergy", QUERIES, ["tech", "parent", "risk"],
            [evidence_dir or ROOT / "data/evidence/tech", parent_dir or ROOT / "data/evidence/parent"],
            search or search_documents, extractor)
        tasks = [r for r in records if r.get("kind") == "task" and r.get("task_id") in TASKS
                 and r.get("performed") is True and r.get("physical") is True
                 and r.get("performed_at")
                 and _date(r["performed_at"]) <= today]
        confirmed = [r for r in tasks if r.get("independent_verified") is True
                     and r.get("confirmed_by") in ("customer", "operator", "government")]
        provisional = [r for r in tasks if r not in confirmed]
        demand = [r for r in records if r.get("kind") == "parent_demand"
                  and r.get("task_id") in TASKS and r.get("public_document") is True
                  and r.get("doc_type") == "parent"
                  and all(sources[s].kind == SourceKind.PDF and sources[s].page is not None for s in r["source_ids"])]
        matches, matched_records = [], []
        for task_id in TASKS:
            candidate_records = [r for r in confirmed if r["task_id"] == task_id]
            parent_records = [r for r in demand if r["task_id"] == task_id]
            if candidate_records and parent_records:
                matches.append({"task_id": task_id, "candidate_source_ids": _ids(candidate_records),
                    "parent_source_ids": _ids(parent_records), "parent_pages": [
                        {"source_id": s, "doc_id": sources[s].doc_id, "page": sources[s].page}
                        for s in _ids(parent_records)]})
                matched_records += candidate_records + parent_records
        indicators = []
        for indicator_id in ("S1", "S2"):
            common = {"indicator_id": indicator_id, "owner": "synergy", "as_of": today}
            complete = _complete(coverage, indicator_id)
            selected = confirmed if indicator_id == "S1" else matched_records
            condition = {"provisional_tasks": provisional, "fixed_task_groups": TASKS}
            if selected or complete:
                raw = ({"performed_task_count": len({r["task_id"] for r in confirmed}),
                        "task_count": len({r["task_id"] for r in confirmed}),
                        "task_ids": sorted({r["task_id"] for r in confirmed})} if indicator_id == "S1" else
                       {"matched_task_count": len(matches), "matches": matches})
                result = _value(**common, value=raw, records=selected + complete,
                                unit="작업군", condition=condition)
                # Parent publications confirm demand, never candidate performance.
            else:
                failed = any(a.status == QueryStatus.ACCESS_FAILED and indicator_id in (a.note or "") for a in attempts)
                result = _missing(**common, reason="독립 수행 근거 또는 모기업 원문 페이지 미확인",
                    status=QueryStatus.ACCESS_FAILED if failed else QueryStatus.NO_DATA, condition=condition)
            result = result.model_copy(update={"source_ids": sorted(set(result.source_ids + _ids(provisional)))})
            indicators.append(result)

        checks = [r for r in records if r.get("kind") == "certification"
                  and r.get("equipment_model") and r.get("process_id")
                  and r.get("checked_at")
                  and _date(r["checked_at"]) <= today]
        latest = {}
        for row in sorted(checks, key=lambda r: r["checked_at"], reverse=True):
            key = (row["process_id"], row["equipment_model"])
            if key in latest and row["checked_at"] == latest[key]["checked_at"] and row != latest[key]:
                raise ValueError("conflicting certification checks on the same date")
            latest.setdefault(key, row)
        checks = list(latest.values())
        statuses = []
        for row in checks:
            zone = row.get("explosive_zone")
            state_name = "UNKNOWN"
            if zone is False:
                state_name = "NOT_APPLICABLE"
            elif zone is True and row.get("lookup_status") == "SUCCESS":
                has_certificate = bool(row.get("certificate_id") or row.get("certification"))
                certificate_details_known = (
                    row.get("certification") and row.get("certificate_id")
                    and type(row.get("scope_matches")) is bool
                    and row.get("valid_from") and row.get("valid_until"))
                valid = (row.get("certification") in ("KCs", "IECEx")
                    and row.get("certificate_id") and row.get("scope_matches") is True
                    and row.get("valid_from") and row.get("valid_until")
                    and _date(row["valid_from"]) <= today <= _date(row["valid_until"]))
                if valid:
                    state_name = "CERTIFIED"
                elif row.get("in_progress") is True and row.get("progress_reference"):
                    state_name = "IN_PROGRESS"
                elif (row.get("lookup_complete") is True and row.get("progress_checked") is True
                      and (not has_certificate or certificate_details_known)):
                    state_name = "NO_VALID_EVIDENCE"
            statuses.append({**row, "verification_status": state_name})
        if statuses:
            # These aggregate observed process/certificate states; judge owns G3.
            explosive = (True if any(r.get("explosive_zone") is True for r in statuses)
                         else None if any(r.get("explosive_zone") is None for r in statuses) else False)
            certificate_evidence = (
                False if any(r["verification_status"] == "NO_VALID_EVIDENCE" for r in statuses)
                else None if any(r["verification_status"] == "UNKNOWN" for r in statuses)
                else True if explosive is True else None)
            indicators.append(_value("F4", "synergy", today, {"checks": statuses,
                "explosive_area": explosive, "certified_or_in_progress": certificate_evidence}, checks,
                unit="확인 상태",
                condition={"limitation": "인증 진행은 현장 사용 승인이 아님; Gate 판정은 judge 담당"}))
        else:
            failed = any(a.status == QueryStatus.ACCESS_FAILED and "F4" in (a.note or "") for a in attempts)
            indicators.append(_missing("F4", "synergy", today, "공정 방폭 구역·장비·인증 조회 미확인",
                status=QueryStatus.ACCESS_FAILED if failed else QueryStatus.NO_DATA))
        return _finish(state, "synergy", indicators, sources, attempts)
    return node


def synergy_node(state: GraphState) -> AgentNodeUpdate:
    return make_synergy_node()(state)
