"""Unscored technology evidence nodes. No network/LLM is configured at import time.

Evidence bundles and extractor contracts are documented in reporting/README.md.
Only a successful, explicitly complete lookup can establish a numeric zero.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
from typing import Callable

from rag import search_documents
from rag.models import RetrievedChunk
from rag.service import SearchBackendNotConfiguredError
from schemas import (
    AgentNodeUpdate, AnalysisResult, EvidenceStatus, GraphState, IndicatorEvidence,
    QueryAttempt, QueryStatus, SourceKind, SourceRecord,
)

ROOT = Path(__file__).resolve().parents[1]
TECH_QUERIES = {
    "T2": "창업자 설립 전 5년 선행 연구 DOI 저자 소속",
    "K1": "설립 이후 최근 5년 기업 소속 논문 DOI 정밀 조작",
    "K2": "실물 조작 시험 성공 횟수 전체 시도 성공 정의 작업 환경",
    "K3": "최근 3년 제조 현장 완료 실증 고객 운영기관 확인",
    "R2": "최근 3개년 국가 연구비 과제별 해당 기업 귀속 정부 지원금",
}


def _shift_year(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def _ids(records: list[dict]) -> list[str]:
    return sorted({s for r in records for s in r.get("source_ids", [])})


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _number(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("non-finite evidence value")
    return number


def _status(records: list[dict]) -> EvidenceStatus:
    return (EvidenceStatus.THIRD_PARTY_VERIFIED if records and all(
        r.get("independent_verified") is True for r in records
    ) else EvidenceStatus.COMPANY_CLAIM)


def _missing(indicator_id, owner, as_of, reason, status=QueryStatus.NO_DATA, **kwargs):
    return IndicatorEvidence(
        id=indicator_id, raw_value=None, as_of=as_of, collected_by=owner,
        evidence_status=EvidenceStatus.NO_EVIDENCE, query_status=status,
        missing_reason=reason, **kwargs,
    )


def _value(indicator_id, owner, as_of, value, records, **kwargs):
    return IndicatorEvidence(
        id=indicator_id, raw_value=value, as_of=as_of, collected_by=owner,
        evidence_status=_status(records), source_ids=_ids(records),
        query_status=QueryStatus.SUCCESS, **kwargs,
    )


def _unique(records: list[dict], key: Callable) -> list[dict]:
    """Merge repeat observations, but never silently pick conflicting amounts."""
    result = {}
    for record in records:
        identity = key(record)
        if identity in result:
            old = result[identity]
            comparable = {k: v for k, v in record.items() if k != "source_ids"}
            previous = {k: v for k, v in old.items() if k != "source_ids"}
            if comparable != previous:
                raise ValueError(f"conflicting records for {identity}")
            result[identity] = {**old, "source_ids": _ids([old, record])}
        else:
            result[identity] = dict(record)
    return list(result.values())


def _source_map(sources):
    result = {}
    for value in sources:
        source = SourceRecord.model_validate(value)
        if source.source_id in result and result[source.source_id] != source:
            raise ValueError(f"conflicting source_id: {source.source_id}")
        result[source.source_id] = source
    return result


def _cached_update(state, owner):
    previous = state.get(f"{owner}_analysis")
    current = state.get("current_candidate")
    if current is None:
        raise ValueError("current_candidate is required")
    if previous is None or previous.candidate_id != current.candidate_id:
        return None
    if any(i.as_of != state["run"].evaluation_date for i in previous.indicators):
        return None
    if _is_repair(state, owner):
        targets = _repair_targets(state, owner)
        completed = {a.note.split(";")[0] for a in previous.query_attempts
                     if a.note and ";phase=repair" in a.note}
        if not targets <= completed:
            return None
    return {f"{owner}_analysis": previous, "sources": []}


def _is_repair(state, owner):
    """Graph calls the handler before incrementing retry_count."""
    review = state.get("evidence_review")
    candidate = state.get("current_candidate")
    return (review is not None and candidate is not None
            and review.candidate_id == candidate.candidate_id and review.repair_required
            and any(target.owner == owner for target in review.repair_targets))


def _chunk_source(chunk: RetrievedChunk, existing: dict) -> SourceRecord:
    """Use page/chunk-specific IDs: the RAG base source ID identifies a document."""
    base = existing.get(chunk.source_id)
    digest = chunk.metadata.get("sha256") or (base.sha256 if base else None)
    path = chunk.local_path or (base.local_path if base else None)
    if not digest and path:
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_file():
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
    suffix = hashlib.sha256(f"{digest}:{chunk.doc_id}:{chunk.page}:{chunk.chunk_id}".encode()).hexdigest()[:16]
    source_id = f"{chunk.source_id}_{suffix}"
    prior = existing.get(source_id)
    result = SourceRecord(
        source_id=source_id, kind=SourceKind.PDF,
        publisher=chunk.publisher or (base.publisher if base else ""),
        title=chunk.title or (base.title if base else ""),
        url=chunk.url or (base.url if base else None),
        published_at=chunk.published_at or (base.published_at if base else None),
        collected_at=prior.collected_at if prior else (base.collected_at if base else datetime.now(timezone.utc)),
        local_path=str(path) if path else None, sha256=digest,
        doc_id=chunk.doc_id, page=chunk.page, chunk_id=chunk.chunk_id,
        evidence_excerpt=chunk.content,
    )
    if prior is not None and prior != result:
        raise ValueError(f"conflicting retrieved source: {source_id}")
    return result


def make_llm_extractor(model):
    """Adapter for an already configured chat model exposing invoke(messages).

    The caller owns provider credentials/model selection. Documents are passed as
    data, and model output must use the record schema in the role prompt.
    """
    def extract(prompt, documents, candidate):
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps({
                "candidate": candidate.model_dump(mode="json"),
                "documents": documents,
            }, ensure_ascii=False)},
        ]
        if hasattr(model, "invoke_json"):
            return model.invoke_json(messages)
        response = model.invoke(messages)
        content = response.content if hasattr(response, "content") else response
        if isinstance(content, str):
            stripped = content.strip()
            if stripped.startswith("```"):
                lines = stripped.splitlines()
                stripped = "\n".join(lines[1:-1]) if len(lines) >= 3 else stripped
            try:
                content = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError("extractor LLM output must be valid JSON") from exc
        if not isinstance(content, dict):
            raise ValueError("extractor must return a JSON object")
        return content
    return extract


def _sanitize_extracted_payload(payload, allowed_sources, candidate_id):
    """Drop unsupported LLM claims instead of failing the whole graph run."""
    if not isinstance(payload, dict):
        return {"candidate_id": candidate_id, "records": [], "coverage": []}
    cleaned = {
        "candidate_id": payload.get("candidate_id", candidate_id),
        "records": [],
        "coverage": [],
    }
    allowed = set(allowed_sources)
    for key in ("records", "coverage"):
        rows = payload.get(key, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            refs = row.get("source_ids")
            if not isinstance(refs, list) or not refs or not set(refs) <= allowed:
                continue
            cleaned[key].append(row)
    return cleaned


def _collect(state, owner, queries, doc_types, evidence_dirs, search, extractor):
    candidate = state.get("current_candidate")
    if candidate is None:
        raise ValueError("current_candidate is required")
    as_of = state["run"].evaluation_date
    sources = _source_map(state.get("sources", []))
    records, coverage, attempts = [], [], []
    previous = state.get(f"{owner}_analysis")
    if (previous is not None and previous.candidate_id == candidate.candidate_id
            and all(i.as_of == as_of for i in previous.indicators)):
        attempts = list(previous.query_attempts)
    repairing = _is_repair(state, owner)
    targets = _repair_targets(state, owner) if repairing else set(queries)

    def accept(payload, allowed_sources=None):
        if not isinstance(payload, dict):
            raise ValueError("evidence bundle must be an object")
        if payload.get("candidate_id") not in (candidate.candidate_id, "COMMON"):
            return
        if allowed_sources is not None and payload.get("sources"):
            raise ValueError("extractors cannot invent source records")
        for source_id, source in _source_map(payload.get("sources", [])).items():
            if source_id in sources and sources[source_id] != source:
                raise ValueError(f"conflicting source_id: {source_id}")
            sources[source_id] = source
        for key, dest in (("records", records), ("coverage", coverage)):
            for row in payload.get(key, []):
                if not isinstance(row, dict):
                    raise ValueError(f"{key} must contain objects")
                target = row.get("candidate_id", payload["candidate_id"])
                if target not in (candidate.candidate_id, "COMMON"):
                    continue
                if target == "COMMON" and (key != "records" or row.get("kind") != "parent_demand"):
                    raise ValueError("COMMON evidence is only permitted for parent demand")
                refs = row.get("source_ids", [])
                if (not isinstance(refs, list) or not refs
                        or any(not isinstance(s, str) or s not in sources for s in refs)):
                    raise ValueError("each evidence record needs registered source_ids")
                if allowed_sources is not None and not set(refs) <= allowed_sources.keys():
                    raise ValueError("extractor cited a source outside supplied documents")
                if allowed_sources is not None and key == "records":
                    types = {allowed_sources[s]["doc_type"] for s in refs}
                    if row.get("kind") == "parent_demand" and types != {"parent"}:
                        raise ValueError("parent demand must cite retrieved parent documents")
                    if row.get("kind") in {"task", "trial", "pilot", "paper", "founders", "funding"} and "parent" in types:
                        raise ValueError("parent demand documents cannot establish candidate performance")
                if any(not sources[s].evidence_excerpt for s in refs):
                    raise ValueError("evidence_excerpt is required for evidence records")
                if any(sources[s].published_at and sources[s].published_at > as_of for s in refs):
                    continue
                # Re-read a bundle independently per invocation, never cache a previous candidate.
                if row not in dest:
                    dest.append(dict(row))

    for directory in evidence_dirs:
        path = Path(directory)
        if path.exists():
            for file in sorted(path.glob("*.json")):
                accept(json.loads(file.read_text(encoding="utf-8")))

    documents = {}
    for indicator_id, text in queries.items():
        if indicator_id not in targets:
            continue
        prior_count = sum((a.note or "").split(";")[0].split(":")[0] == indicator_id for a in attempts)
        allowed = min(1, 3 - prior_count) if repairing else (2 if prior_count == 0 else 0)
        for round_index in range(max(0, allowed)):
            query = f"{candidate.legal_name} {text}"
            if round_index:
                query += " 원문 수치 기간 대상과 근거 페이지"
            try:
                chunks = search(query=query, candidate_id=candidate.candidate_id,
                                doc_types=doc_types, top_k=5)
                valid = 0
                for chunk in chunks:
                    if chunk.doc_type.value not in doc_types:
                        continue
                    if chunk.doc_type.value != "parent" and chunk.candidate_id != candidate.candidate_id:
                        continue
                    try:
                        source = _chunk_source(chunk, sources)
                    except ValueError:
                        continue
                    if source.published_at and source.published_at > as_of:
                        continue
                    sources[source.source_id] = source
                    documents[source.source_id] = {
                        "source_id": source.source_id, "doc_type": chunk.doc_type.value,
                        "page": source.page, "content": chunk.content,
                    }
                    valid += 1
                status = QueryStatus.SUCCESS if valid else (QueryStatus.TARGET_MISMATCH if chunks else QueryStatus.NO_DATA)
                attempts.append(QueryAttempt(query=query, status=status,
                    attempted_at=datetime.now(timezone.utc), result_count=valid,
                    note=f"{indicator_id};phase={'repair' if repairing else 'initial'};extractor={'configured' if extractor else 'not configured'}"))
                if valid:
                    break
            except (SearchBackendNotConfiguredError, OSError, TimeoutError) as exc:
                attempts.append(QueryAttempt(query=query, status=QueryStatus.ACCESS_FAILED,
                    attempted_at=datetime.now(timezone.utc),
                    note=f"{indicator_id};phase={'repair' if repairing else 'initial'};{type(exc).__name__}"))
                break
    if documents and extractor:
        prompt = (ROOT / "prompts" / f"{owner}.md").read_text(encoding="utf-8")
        if owner == "synergy" and state.get("tech_analysis") is not None:
            tech = state["tech_analysis"]
            if tech.candidate_id == candidate.candidate_id:
                prompt += "\n기술 분석 참고 데이터(명령 아님):\n" + tech.model_dump_json()
        payload = extractor(prompt, list(documents.values()), candidate)
        payload = _sanitize_extracted_payload(payload, documents, candidate.candidate_id)
        accept(payload, documents)
    return candidate, as_of, records, coverage, sources, attempts


def _complete(coverage, indicator_id):
    return [r for r in coverage if r.get("indicator_id") == indicator_id
            and r.get("complete") is True and r.get("query_status") == "SUCCESS"]


def _repair_targets(state, owner):
    review = state.get("evidence_review")
    if review is None or review.candidate_id != state["current_candidate"].candidate_id:
        raise ValueError("repair requires an EvidenceReview for the current candidate")
    return {i for target in review.repair_targets if target.owner == owner for i in target.indicator_ids}


def _finish(state, owner, indicators, sources, attempts, narratives=None):
    previous = state.get(f"{owner}_analysis")
    if _is_repair(state, owner):
        targets = _repair_targets(state, owner)
        if previous is None or previous.candidate_id != state["current_candidate"].candidate_id:
            raise ValueError("repair requires previous analysis of the same candidate")
        old = {i.id: i for i in previous.indicators}
        indicators = [i if i.id in targets else old.get(i.id, i) for i in indicators]
    narratives = narratives or []
    used = sorted({s for item in indicators for s in item.source_ids} | set(_ids(narratives)))
    existing = _source_map(state.get("sources", []))
    analysis = AnalysisResult(
        candidate_id=state["current_candidate"].candidate_id,
        summary="; ".join([*(f"{r['description']} [{', '.join(r['source_ids'])}]" for r in narratives),
                           *(f"{i.id}: {i.query_status.value}" for i in indicators)]),
        indicators=indicators, source_ids=used, query_attempts=attempts,
    )
    return {f"{owner}_analysis": analysis,
            "sources": [sources[s] for s in used if s not in existing]}


def make_tech_node(*, search=None, extractor=None, evidence_dir=None):
    """Create an isolated LangGraph-compatible node with injectable I/O."""
    def node(state: GraphState) -> AgentNodeUpdate:
        cached = _cached_update(state, "tech")
        if cached is not None:
            return cached
        c, today, records, coverage, sources, attempts = _collect(
            state, "tech", TECH_QUERIES, ["tech", "risk"],
            [evidence_dir or ROOT / "data/evidence/tech"], search or search_documents, extractor)
        indicators = []
        kinds = lambda kind: [r for r in records if r.get("kind") == kind]
        doi = lambda r: re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", r["doi"].strip().lower())
        papers = [r for r in kinds("paper") if r.get("topic_relevant") is True
                  and r.get("identity_verified") is True and r.get("doi")
                  and r.get("published_at") and _date(r["published_at"]) <= today
                  and re.fullmatch(r"10\.\d{4,9}/\S+", doi(r))]
        pre_founding_dois = {doi(r) for r in papers if _date(r["published_at"]) < c.founded_at}
        for indicator_id in TECH_QUERIES:
            complete = _complete(coverage, indicator_id)
            common = {"indicator_id": indicator_id, "owner": "tech", "as_of": today}
            result = None
            if indicator_id == "T2":
                founders = [r for r in kinds("founders") if r.get("identity_verified") is True
                            and r.get("complete") is True and r.get("founder_ids")]
                if founders:
                    founder_ids = set(founders[0]["founder_ids"])
                    if any(set(r["founder_ids"]) != founder_ids for r in founders):
                        raise ValueError("conflicting founder denominator")
                    selected = [r for r in papers if _shift_year(c.founded_at, -5) <= _date(r["published_at"]) < c.founded_at
                                and founder_ids.intersection(r.get("author_ids", []))]
                    count = len({doi(r) for r in selected})
                    if selected or complete:
                        result = _value(**common, value={"paper_count": count,
                            "founder_count": len(founder_ids), "papers_per_founder": Decimal(count) / len(founder_ids),
                            "dois": sorted({doi(r) for r in selected})},
                            records=selected + founders + complete, unit="편/명",
                            period=f"{_shift_year(c.founded_at, -5)}/{c.founded_at} (설립일 제외)",
                            condition={"founder_ids": sorted(founder_ids), "authors": selected})
            elif indicator_id == "K1":
                selected = [r for r in papers if max(c.founded_at, _shift_year(today, -5)) <= _date(r["published_at"]) <= today
                            and r.get("company_affiliation_verified") is True and r.get("affiliations")
                            and doi(r) not in pre_founding_dois]
                if selected or complete:
                    result = _value(**common, value=len({doi(r) for r in selected}), records=selected + complete,
                                    unit="논문 DOI", period=f"{max(c.founded_at, _shift_year(today, -5))}/{today}",
                                    condition={"papers": selected})
            elif indicator_id == "K2":
                observations, eligible = [], []
                for r in kinds("trial"):
                    if r.get("tested_at") and _date(r["tested_at"]) > today:
                        continue
                    n, success = r.get("total_trials"), r.get("successful_trials")
                    valid = type(n) is int and type(success) is int and n > 0 and 0 <= success <= n
                    reasons = []
                    if not r.get("tested_at"):
                        reasons.append("시험일 미확인")
                    if not valid:
                        reasons.append("유효하지 않은 성공 횟수 또는 분모")
                    elif n < 30:
                        reasons.append("실물 시험 30회 미만")
                    if r.get("physical") is not True:
                        reasons.append("실물 시험 미확인")
                    if not all(isinstance(r.get(k), str) and r[k].strip()
                               for k in ("task", "environment", "success_definition")):
                        reasons.append("시험 조건 또는 성공 정의 미공개")
                    observation = {**r, "exclusion_reasons": reasons}
                    observations.append(observation)
                    if not reasons:
                        eligible.append(r)
                if eligible:
                    # Latest per fully specified condition; never rank by success rate.
                    eligible.sort(key=lambda r: (r["tested_at"], _ids([r])), reverse=True)
                    by_condition = {}
                    observed_counts = {}
                    for r in eligible:
                        key = json.dumps({k: r.get(k) for k in ("task", "environment", "success_definition", "equipment_model", "conditions")}, sort_keys=True)
                        observation_key = (key, r["tested_at"])
                        counts = (r["successful_trials"], r["total_trials"])
                        if observation_key in observed_counts and observed_counts[observation_key] != counts:
                            raise ValueError("conflicting trial counts for the same conditions and date")
                        observed_counts[observation_key] = counts
                        by_condition.setdefault(key, r)
                    eligible = sorted(by_condition.values(), key=lambda r: (
                        r.get("parent_task_match") is True, r["tested_at"], _ids([r])), reverse=True)
                    chosen = dict(eligible[0])
                    chosen["independent_verified"] = chosen.get("independent_reproduction") is True and chosen.get("independent_verified") is True
                    rate = (Decimal(chosen["successful_trials"]) * 100 / chosen["total_trials"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    result = _value(**common, value={"successful_trials": chosen["successful_trials"],
                        "total_trials": chosen["total_trials"], "success_rate_percent": float(rate)},
                        records=[chosen], unit="%", period=chosen["tested_at"], condition={
                            **{k: chosen.get(k) for k in ("task", "environment", "success_definition", "equipment_model", "conditions", "independent_reproduction")},
                            "selection_rule": "모기업 관련 작업 우선, 동일 조건 최신 시험; 성공률 순위 사용 안 함",
                            "observations": observations})
                    result = result.model_copy(update={"source_ids": _ids(observations)})
                elif observations:
                    invalid = any("유효하지 않은 성공 횟수 또는 분모" in r["exclusion_reasons"] for r in observations)
                    result = _missing(**common, reason="채택 가능한 실물 시험 없음; condition.observations 참조",
                        status=QueryStatus.INVALID_DENOMINATOR if invalid else QueryStatus.NO_DATA,
                        source_ids=_ids(observations), condition={"observations": observations})
            elif indicator_id == "K3":
                selected = [r for r in kinds("pilot") if r.get("completed") is True
                    and r.get("manufacturing") is True and r.get("physical") is True
                    and r.get("confirmed_by") in ("customer", "operator") and r.get("independent_verified") is True
                    and r.get("site_id") and r.get("completed_at")
                    and _shift_year(today, -3) <= _date(r["completed_at"]) <= today]
                if selected or complete:
                    result = _value(**common, value=len({r["site_id"] for r in selected}), records=selected + complete,
                        unit="제조 현장", period=f"{_shift_year(today, -3)}/{today}",
                        condition={"site_ids": sorted({r["site_id"] for r in selected}), "pilots": selected,
                                   "limitation": "실증 수는 유상 계약 또는 양산 매출이 아님"})
            elif indicator_id == "R2":
                selected = [r for r in kinds("funding") if r.get("government") is True
                    and r.get("topic_relevant") is True and r.get("beneficiary_id") == c.candidate_id
                    and type(r.get("year")) is int and today.year - 2 <= r["year"] <= today.year
                    and r.get("project_id") and r.get("company_amount_krw") is not None]
                selected = _unique(selected, lambda r: (r["project_id"], r["year"], r["beneficiary_id"]))
                if any(_number(r["company_amount_krw"]) < 0 for r in selected):
                    raise ValueError("government funding must be non-negative")
                if selected or complete:
                    amount = sum((_number(r["company_amount_krw"]) for r in selected), Decimal(0))
                    result = _value(**common, value={"amount_krw": str(amount),
                        "amount_100m_krw": str(amount / Decimal(100_000_000)),
                        "amount_krw_100m": amount / Decimal(100_000_000), "projects": selected},
                        records=selected + complete, unit="억 원", period=f"{today.year - 2}-01-01/{today}",
                        condition={"calendar_years": list(range(today.year - 2, today.year + 1)),
                                   "current_year_partial": True, "consortium_total_excluded": True})
            if result is None:
                failed = any(a.status == QueryStatus.ACCESS_FAILED and indicator_id in (a.note or "") for a in attempts)
                result = _missing(**common, reason="원값·대상·기간·출처가 충족된 자료 없음",
                                  status=QueryStatus.ACCESS_FAILED if failed else QueryStatus.NO_DATA)
            indicators.append(result)
        narratives = [r for r in kinds("technology") if isinstance(r.get("description"), str) and r["description"].strip()]
        return _finish(state, "tech", indicators, sources, attempts, narratives)
    return node


def tech_node(state: GraphState) -> AgentNodeUpdate:
    return make_tech_node()(state)
