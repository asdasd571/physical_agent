"""원래 점수와 구분하는 초기 연구·시제품 단계의 비교 점수이다."""

from nodes.judge import calculate_category_scores, calculate_total_score
from decimal import Decimal, InvalidOperation


def has_numeric_measurement(metrics):
    if not isinstance(metrics, dict):
        return False
    for value in metrics.values():
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, bool) or not isinstance(item, (int, float, Decimal, str)):
                continue
            try:
                if Decimal(str(item)).is_finite():
                    return True
            except InvalidOperation:
                continue
    return False


def compare_early_stage(indicators, strict_scores, evaluation_date):
    scores, reasons = dict(strict_scores), {}
    for indicator in indicators:
        evidence = indicator.condition.get("early_stage_evidence", [])
        matched = []
        for row in evidence:
            if not row.get("source_ids") or not set(row["source_ids"]) <= set(indicator.source_ids):
                continue
            if (indicator.id == "K1" and row.get("kind") == "specification" and row.get("model")
                    and has_numeric_measurement(row.get("metrics"))):
                matched.append("제품의 정량 사양을 초기 설계 근거로 인정합니다. 논문 수로 환산하지 않습니다.")
            if (indicator.id == "K2" and row.get("kind") == "validation" and row.get("physical") is True
                    and row.get("setup") and has_numeric_measurement(row.get("metrics"))):
                matched.append("실물 센서의 시험 조건과 측정 수치를 초기 성능 근거로 인정합니다. 조작 성공률로 환산하지 않습니다.")
            if (indicator.id == "K3" and row.get("kind") == "demonstration" and row.get("completed") is True
                    and row.get("physical") is True and type(row.get("performed_year")) is int
                    and evaluation_date.year - 3 <= row["performed_year"] <= evaluation_date.year
                    and row.get("event")):
                matched.append("공개된 실물 시연 기록을 초기 실증 근거로 인정합니다. 제조 현장 배치로 간주하지 않습니다.")
        if matched and scores.get(indicator.id, 1) < 2:
            scores[indicator.id] = 2
            reasons[indicator.id] = list(dict.fromkeys(matched))
    return {"profile": "early-stage-v2", "score": calculate_total_score(calculate_category_scores(scores)),
            "indicator_scores": scores, "changes": reasons,
            "used_for_investment_decision": False}
