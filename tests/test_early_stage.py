from datetime import date

from nodes.early_stage import compare_early_stage
from nodes.judge import SCORE_INDICATOR_IDS
from schemas import IndicatorEvidence


def compare(key, row, source_ids=None):
    indicator = IndicatorEvidence(id=key, collected_by="tech", raw_value=None,
                                  evidence_status="NO_EVIDENCE", query_status="NO_DATA", missing_reason="정량 근거 미확보",
                                  source_ids=source_ids or ["reviewed"], condition={"early_stage_evidence": [row]})
    return compare_early_stage([indicator], {key: 1 for key in SCORE_INDICATOR_IDS}, date(2026, 10, 13))


def test_documented_specs_are_limited_to_two_and_not_investment_score():
    row = {"kind": "specification", "model": "sample", "metrics": {"dof": 41}, "source_ids": ["reviewed"]}
    result = compare("K1", row)
    assert result["indicator_scores"]["K1"] == 2
    assert not result["used_for_investment_decision"]
    assert compare("K1", {**row, "source_ids": ["invented"]})["indicator_scores"]["K1"] == 1
    assert compare("K1", {**row, "metrics": {"quality": "최고", "tested": True}})["indicator_scores"]["K1"] == 1


def test_sensor_measurement_does_not_invent_a_manipulation_success_rate():
    row = {"kind": "validation", "physical": True, "setup": "reference sensor",
           "metrics": {"relative_error_percent_fso": 0.16}, "source_ids": ["reviewed"]}
    assert compare("K2", row)["indicator_scores"]["K2"] == 2
    assert compare("K2", {**row, "physical": False})["indicator_scores"]["K2"] == 1


def test_planned_and_future_demonstrations_do_not_receive_credit():
    row = {"kind": "demonstration", "completed": True, "physical": True, "event": "exhibition",
           "performed_year": 2025, "source_ids": ["reviewed"]}
    assert compare("K3", row)["indicator_scores"]["K3"] == 2
    assert compare("K3", {**row, "completed": False})["indicator_scores"]["K3"] == 1
    assert compare("K3", {**row, "performed_year": 2027})["indicator_scores"]["K3"] == 1
