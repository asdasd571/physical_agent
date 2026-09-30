"""Presentation only: never calculate scores or replace missing values with zero."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

FIELD_LABELS = {
    "base_year": "기준 연도", "latest_year": "최근 연도",
    "base_revenue": "기준 매출", "latest_revenue": "최근 매출",
    "baseline_employees": "기준 종업원 수", "latest_employees": "최근 종업원 수",
    "growth_rate_percent": "성장률(%)", "cagr_percent": "연평균 성장률(%)",
    "currency": "통화", "amount": "금액", "segment": "세그먼트", "period": "기간",
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
        return "; ".join(f"{r['process_id']} / {r['equipment_model']}: {r['verification_status']}"
                         for r in raw.get("checks", []))
    return format_value(raw) + (f" {indicator.unit}" if indicator.unit else "")
