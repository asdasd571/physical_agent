# Development Status

## 현재 상태

- 담당자: 박세진
- 브랜치: feature/discover-market-competitor
- 현재 단계: STEP 2 `agents/discover.py` 코드 리뷰 지적사항 100% 반영 및 전면 리팩토링 완료
- 마지막 업데이트: 2026-09-30 11:13

## 완료된 작업

- [x] 담당 영역 기본 디렉터리 구조 생성
- [x] `data/candidates.json` 평가 대상 후보 2개사(에이로봇, 에이딘로보틱스) 확정
- [x] `prompts/discover.md`, `market.md`, `competitor.md` 프롬프트 3종 작성
- [x] `data/evidence/company/arobot.json`, `aidin_robotics.json` 지표별(G1~F3) 섹션화 및 원값 단위 규격화
- [x] `agents/discover.py` 출처 ID 하드코딩 버그 제거 (섹션별 `source_ids` 직접 파싱)
- [x] `agents/discover.py` 근거 상태(`evidence_status`) 세분화 (T1/R1 자체 발표 `COMPANY_CLAIM` 분리, 3점 상한 보장)
- [x] `agents/discover.py` `build_indicator()` 구현을 통한 섹션 부재(NO_DATA), 분모 오류(DENOMINATOR_ERROR), 대상 불일치(TARGET_MISMATCH) 정밀 판별
- [x] `agents/discover.py` 원값 단위(`unit`) 일치화 (`명`, `원`, `건`, `4개 요건 사실`)
- [x] `agents/discover.py` summary 내 주관적 평가 제거 및 순수 팩트 메타데이터 기록
- [x] `agents/discover.py` `handoff_urls` 후속 에이전트(김진형 님) 인계 누락 방지
- [x] `agents/discover.py` repair 시 `indicator_ids` 기반 지정 지표 선택 재수집 및 `query_attempts` 누적 병합
- [x] `agents/discover.py` `SourceKind` 오류 및 `current_candidate` 부재 시 조용한 기본값 대체 대신 명시적 예외 발생
- [x] `tests/test_discover.py` 신규 검증 테스트 5종 작성 및 전원 통과 (9/9 passed)

## 진행 중인 작업

- [ ] `agents/market.py` 한국 도입 시장 기준 P1 3개년 CAGR 계산용 원값 수집 로직 구현
- [ ] `agents/competitor.py` 경쟁사 비교 및 M1 유효 등록 특허 고유 패밀리 중복 제거 로직 구현

## 다음 작업

1. `agents/market.py` 구현 및 `data/evidence/market/` 통계 원천 데이터 구성
2. `tests/test_market.py` 단위 테스트 작성 및 로컬 검증
3. `agents/competitor.py` 구현 및 KIPRIS 특허 패밀리 중복 제거 로직 테스트

## 변경된 파일

- `agents/discover.py`
  - `build_indicator()` 신설, 하드코딩 제거, repair 지표 선택 지원, handoff_urls 반환
- `data/evidence/company/arobot.json`
  - 지표별 섹션화, 원값 단위(`원`, `명`), 회사 발표(`COMPANY_CLAIM`) 정확 반영
- `data/evidence/company/aidin_robotics.json`
  - 지표별 섹션화, 원값 단위(`원`, `명`), 회사 발표(`COMPANY_CLAIM`) 정확 반영
- `tests/test_discover.py`
  - 하드코딩 제거 검증, 단위 및 상태 판별, 예외 상황 명시적 오류 검증, repair 및 handoff_urls 검증 테스트 추가
- `DEVELOPMENT_STATUS.md`
  - 개발 현황 갱신

## 현재 인터페이스

```python
from schemas import AgentNodeUpdate, AnalysisResult, Candidate, GraphState, IndicatorEvidence, SourceRecord

def build_indicator(
    ind_id: str,
    section: dict[str, Any] | None,
    default_unit: str | None = None,
) -> IndicatorEvidence:
    """섹션 딕셔너리에서 지표를 읽고, 부재 시 NO_DATA 및 missing_reason 기록."""
    ...

def discover_candidate(
    candidate: Candidate,
    evidence_dir: Path | str | None = None,
    indicator_ids: list[str] | None = None,
) -> tuple[AnalysisResult, list[SourceRecord], list[dict[str, Any]]]:
    """후보 정보 및 지표 수집 (지정 indicator_ids 선택 재수집 지원)."""
    ...

def discover_node(state: GraphState) -> AgentNodeUpdate:
    """LangGraph node: current_candidate 대상 분석 및 company_profile, sources, handoff_urls 반환."""
    ...
```

## 테스트 결과

실행 명령:

```bash
python3 -m pytest tests/test_schemas.py tests/test_discover.py
```

결과:

PASS

확인한 항목:

- F1/F2/F3 출처 ID가 후보별 evidence 파일의 섹션에서 고유하게 추출됨 확인.
- R1/T1의 evidence_status가 COMPANY_CLAIM으로 지정되어 자체 발표 3점 상한 요건 충족 확인.
- 섹션 누락 시 NO_DATA 및 missing_reason 정상 생성, DENOMINATOR_ERROR, TARGET_MISMATCH 상태 매핑 정상 확인.
- 단위가 원값 규격(`명`, `원`, `건`)과 정확히 일치함 확인.
- summary 내 비상장/전문기업 등 주관적 평가 표현 배제 확인.
- current_candidate 누락 시 조용히 넘기지 않고 ValueError 발생 확인.
- repair 요청 시 indicator_ids 선택 재수집 및 query_attempts 병합 정상 확인.
- handoff_urls가 버려지지 않고 discover_node 반환값에 정상 포함됨 확인.

## 미해결 문제

- 없음.

## 다른 팀원에게 영향을 주는 변경

- API 변경 여부: 없음.
- State/Schema 변경 여부: 없음 (`discover_node` 반환 딕셔너리에 `handoff_urls` 추가되어 downstream 노드 전달 지원).
- requirements 변경 여부: 없음.
- 다른 브랜치에서 대응이 필요한 내용: 없음.

## Git 상태

현재는 로컬 개발 완료 상태이며 아직 commit/push 하지 않음.
다음 commit 후보 메시지:
:recycle:[REF] discover 에이전트 출처 하드코딩 제거, 원값 단위 및 섹션별 상태 판별 정밀화
