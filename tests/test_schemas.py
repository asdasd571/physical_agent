from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas import (
    AnalysisResult,
    EvidenceStatus,
    IndicatorEvidence,
    INTERFACE_VERSION,
    QueryStatus,
)


def test_interface_version_is_fixed() -> None:
    assert INTERFACE_VERSION == "1.0.0"


def test_verified_zero_is_distinct_from_missing_data() -> None:
    evidence = IndicatorEvidence(
        id="M1",
        raw_value=0,
        unit="특허 패밀리",
        evidence_status=EvidenceStatus.THIRD_PARTY_VERIFIED,
        collected_by="competitor",
        query_status=QueryStatus.SUCCESS,
    )

    assert evidence.raw_value == 0
    assert evidence.missing_reason is None


def test_missing_data_requires_reason() -> None:
    with pytest.raises(ValidationError, match="missing_reason"):
        IndicatorEvidence(
            id="K2",
            raw_value=None,
            evidence_status=EvidenceStatus.NO_EVIDENCE,
            collected_by="tech",
            query_status=QueryStatus.NO_DATA,
        )


def test_analysis_includes_all_indicator_sources() -> None:
    evidence = IndicatorEvidence(
        id="K2",
        raw_value=93.3,
        unit="%",
        evidence_status=EvidenceStatus.COMPANY_CLAIM,
        source_ids=["src_test"],
        collected_by="tech",
        query_status=QueryStatus.SUCCESS,
    )

    with pytest.raises(ValidationError, match="src_test"):
        AnalysisResult(
            candidate_id="company_a",
            summary="시험 결과",
            indicators=[evidence],
            source_ids=[],
            query_attempts=[],
        )
