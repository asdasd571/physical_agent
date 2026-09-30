"""Presentation only: never calculate scores or replace missing values with zero."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

FIELD_LABELS = {
    "base_year": "기준 연도", "latest_year": "최근 연도",
    "base_revenue": "기준 매출", "latest_revenue": "최근 매출",
    "baseline_employees": "기준 종업원 수", "latest_employees": "최근 종업원 수",
    "growth_rate_percent": "성장률(%)", "cagr_percent": "연평균 성장률(%)",
    "currency": "통화", "amount": "금액", "segment": "세그먼트", "period": "기간",
    "explosive_area": "방폭 구역", "certified_or_in_progress": "인증 보유 또는 취득 진행",
}

STATUS_LABELS = {
    "THIRD_PARTY_VERIFIED": "제3자 확인", "COMPANY_CLAIM": "자체 발표",
    "NO_EVIDENCE": "자료 없음", "SUCCESS": "조회 성공", "NO_DATA": "자료 부재",
    "ACCESS_FAILED": "접근 실패", "TARGET_MISMATCH": "대상 불일치",
    "INVALID_DENOMINATOR": "분모 오류",
}


def format_date(value):
    if value is None:
        return "자료 없음"
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


def format_number(value, places=None):
    if value is None:
        return "자료 없음"
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("cannot display non-finite number")
    if places is not None:
        number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return format(number, ",f")


def format_money(value, currency="KRW"):
    return "자료 없음" if value is None else f"{format_number(value)} {currency}"


def format_percent(value):
    return "자료 없음" if value is None else f"{format_number(value, 2)}%"


def format_status(value):
    return STATUS_LABELS.get(str(value), str(value))


def format_value(value):
    if value is None:
        return "자료 없음"
    if isinstance(value, dict):
        return "; ".join(f"{FIELD_LABELS.get(k, k)}: {format_value(v)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(format_value(item) for item in value)
    if isinstance(value, bool):
        return "예" if value else "아니오"
    return str(value)


def format_source(source, label):
    page = f" p.{source.page}." if source.page else ""
    return f"[{label}] {source.publisher}. {source.title}. {format_date(source.published_at)}.{page}"


def indicator_text(indicator):
    raw = indicator.raw_value
    if raw is None:
        return f"자료 없음 — {indicator.missing_reason or '미확인'}"
    # Display archived aggregates without recalculating another owner's values.
    # The complete member/round/patent records remain in the JSON sidecar.
    if indicator.id == "T1" and isinstance(raw, dict) and "qualified_count" in raw:
        members = ", ".join(str(m.get("name", "이름 미확인")) for m in raw.get("members", []))
        return f"해당 경력 {raw['qualified_count']}명" + (f" ({members})" if members else "")
    if indicator.id == "P1" and isinstance(raw, dict) and "start_revenue" in raw:
        result = (f"{raw.get('stat_segment', '세그먼트 미확인')}: "
                  f"{raw.get('start_year', '?')}년 {format_number(raw['start_revenue'])} → "
                  f"{raw.get('end_year', '?')}년 {format_number(raw.get('end_revenue'))} "
                  f"{raw.get('unit_original', indicator.unit or '')}")
        if raw.get("cagr_percent") is not None:
            result += f"; 저장된 CAGR {format_percent(raw['cagr_percent'])}"
        return result
    if indicator.id == "R1" and isinstance(raw, dict) and "rounds" in raw:
        return "; ".join(
            f"{r.get('round_name', '라운드 미확인')} ({r.get('announced_at', '날짜 미확인')}): "
            f"{format_money(r.get('amount_original'), r.get('currency', '통화 미확인'))}"
            + (" [누적 발표]" if r.get("is_cumulative_announcement") else "")
            for r in raw["rounds"]) or "공개 투자 라운드 기록 없음"
    if indicator.id == "R3" and isinstance(raw, dict) and "prior" in raw and "latest" in raw:
        return "; ".join(f"{label} {raw[key].get('as_of', '날짜 미확인')}: "
                         f"{raw[key].get('count', '자료 없음')}명"
                         for key, label in (("prior", "이전"), ("latest", "최근")))
    if indicator.id == "M1" and isinstance(raw, dict) and "unique_priority_families" in raw:
        return (f"유효 등록 {raw.get('valid_registered_patents', '미확인')}건; "
                f"우선권 기준 {raw['unique_priority_families']}패밀리")
    if indicator.id == "F1" and isinstance(raw, dict) and "cash_and_equivalents" in raw:
        return "; ".join(f"{label} {format_money(raw.get(key), raw.get('currency', '통화 미확인'))}"
                         for key, label in (("cash_and_equivalents", "현금"),
                             ("short_term_financial_instruments", "단기금융상품"),
                             ("operating_cash_flow", "영업현금흐름")))
    if indicator.id == "F2" and isinstance(raw, dict) and "capital_stock" in raw:
        return ("; ".join(f"{label} {format_money(raw.get(key), raw.get('currency', '통화 미확인'))}"
                         for key, label in (("capital_stock", "자본금"), ("total_equity", "자본총계"),
                                             ("total_liabilities", "부채총계")))
                + f"; 감사의견 {raw.get('audit_opinion', '미확인')}; 계속기업 불확실성 "
                + format_value(raw.get("going_concern_uncertainty")))
    if indicator.id == "F3" and isinstance(raw, dict) and "case_count" in raw:
        agencies = ", ".join(r.get("agency", "기관 미확인") for r in raw.get("jurisdictions_checked", []))
        return f"확인 사건 {raw['case_count']}건; 조회 기관: {agencies or '미확인'}"
    if indicator.id == "K2" and isinstance(raw, dict):
        return (f"{raw['successful_trials']}/{raw['total_trials']}회, "
                f"{format_percent(raw['success_rate_percent'])}")
    if indicator.id == "T2" and isinstance(raw, dict):
        return f"{raw['paper_count']}편 / 창업자 {raw['founder_count']}명 = {raw['papers_per_founder']}편/명"
    if indicator.id == "R2" and isinstance(raw, dict):
        return f"{format_money(raw['amount_krw'])} ({raw['amount_100m_krw']}억 원)"
    if indicator.id == "S1" and isinstance(raw, dict):
        return f"{raw['performed_task_count']}개: {', '.join(raw['task_ids'])}"
    if indicator.id == "S2" and isinstance(raw, dict):
        return f"{raw['matched_task_count']}개: " + "; ".join(
            f"{m['task_id']} (후보 {', '.join(m['candidate_source_ids'])} → 모기업 "
            + ', '.join(f"{p['source_id']} p.{p['page']}" for p in m.get('parent_pages', [])) + ')'
            for m in raw.get("matches", []))
    if indicator.id == "F4" and isinstance(raw, dict):
        if "checks" not in raw:
            return format_value(raw)
        return "; ".join(f"{r['process_id']} / {r['equipment_model']}: {r['verification_status']}"
                         for r in raw.get("checks", []))
    return format_value(raw) + (f" {indicator.unit}" if indicator.unit else "")
