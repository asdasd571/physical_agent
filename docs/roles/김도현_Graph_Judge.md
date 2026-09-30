# 김도현 LangGraph와 투자 판단

## 목표

공통 State와 분석 결과 스키마를 정의하고, 후보 선택부터 적격성 분기, 병렬 분석, 근거 검증, 보완, 채점, 결과 누적과 보고서 호출까지 전체 LangGraph를 완성한다.

## 담당 브랜치

```text
feature/graph-judge
```

## 담당 폴더 구조

```text
schemas/
├── __init__.py
├── state.py
├── analysis.py
├── evidence.py
└── evaluation.py

graph/
├── __init__.py
├── builder.py
├── reducers.py
└── routers.py

nodes/
├── __init__.py
├── init.py
├── select_candidate.py
├── eligibility.py
├── review.py
├── repair.py
├── judge.py
├── skip.py
└── archive.py

tests/
├── test_reducers.py
├── test_routers.py
├── test_judge.py
└── test_graph_flow.py

app.py
requirements.txt
.env.example
README.md
```

## `schemas/`에 들어갈 파일

### `schemas/state.py`

전체 Graph가 공유하는 `GraphState`를 정의한다.

```python
class GraphState(TypedDict):
    run: RunConfig
    candidates: list[Candidate]
    candidate_index: int
    current_candidate: Candidate | None
    company_profile: AnalysisResult | None
    tech_analysis: AnalysisResult | None
    market_analysis: AnalysisResult | None
    competitor_analysis: AnalysisResult | None
    synergy_analysis: AnalysisResult | None
    evidence_review: EvidenceReview | None
    control: ControlState
    evaluation: EvaluationRecord | None
    decision: Decision | None
    evaluations: list[EvaluationRecord]
    sources: list[SourceRecord]
    report: ReportResult | None
```

후보가 바뀔 때 현재 후보 전용 분석 필드는 반드시 초기화한다.

### `schemas/analysis.py`

모든 분석 Agent가 반환할 공통 형식을 정의한다.

```python
class AnalysisResult(BaseModel):
    candidate_id: str
    summary: str
    indicators: list[IndicatorEvidence]
    source_ids: list[str]
    query_attempts: list[QueryAttempt]
```

### `schemas/evidence.py`

원값, 조회 상태와 출처를 정의한다.

```python
class IndicatorEvidence(BaseModel):
    id: str
    raw_value: int | float | str | list[str] | None
    unit: str | None
    period: str | None
    as_of: date | None
    condition: dict[str, object]
    evidence_status: EvidenceStatus
    source_ids: list[str]
    collected_by: str
    query_status: QueryStatus
    missing_reason: str | None
```

`SourceRecord`도 이 파일에서 관리한다. RAG의 `RetrievedChunk`를 다시 정의하지 말고 필요한 값을 `SourceRecord`로 변환한다.

### `schemas/evaluation.py`

게이트, 지표 점수, 총점과 최종 판단 결과를 정의한다.

```python
class GateResult(BaseModel):
    passed: bool
    reasons: list[str]
    source_ids: list[str]
    unknown_items: list[str]
```

```python
class EvaluationRecord(BaseModel):
    candidate_id: str
    gates: dict[str, GateResult]
    indicator_scores: dict[str, int]
    category_scores: dict[str, Decimal]
    total_score: Decimal | None
    decision: str
    due_diligence_items: list[str]
```

## `graph/`에 들어갈 파일

### `graph/reducers.py`

병렬 Node 결과를 안전하게 합친다.

- `sources`: `source_id` 기준 중복 제거
- `evaluations`: `candidate_id` 기준 중복 방지
- 분석 필드: 담당 Node의 전체 분석 객체로 교체

### `graph/routers.py`

State를 변경하지 않고 다음 경로만 선택한다.

```python
def route_after_eligibility(state: GraphState) -> Literal["tech", "skip"]:
    return "tech" if state["eligibility"].status == "PASS" else "skip"
```

필요한 Router:

- 적격성 이후
- review 이후 repair 여부
- archive 이후 다음 후보 또는 report

### `graph/builder.py`

Node, Edge, Router를 연결하고 Graph를 compile한다.

예상 흐름:

```text
init
  -> select_candidate
  -> discover
  -> eligibility_check
     -> FAIL/UNKNOWN -> skip -> archive
     -> PASS -> tech
             -> market + competitor + synergy
             -> review
             -> repair 또는 judge
             -> archive
  -> 다음 후보 또는 report
```

## `nodes/`에 들어갈 파일

### `nodes/init.py`

- 실행 ID와 기준일 생성
- 평가 규칙 버전 저장
- 후보 2~3개 입력 검증
- 중복 `candidate_id` 검사

### `nodes/select_candidate.py`

- 현재 후보 선택
- `candidate_index` 갱신
- 이전 후보의 임시 분석, 검증, 판단 결과 초기화

### `nodes/eligibility.py`

discover 결과를 이용해 G1을 PASS, FAIL, UNKNOWN으로 구분한다.

### `nodes/review.py`

다음을 검사한다.

- 원문과 원값 일치
- 단위와 기간
- 분모와 계산 조건
- 기업 귀속
- 중복 실증과 특허 패밀리
- 모든 `source_ids`의 실제 존재 여부

### `nodes/repair.py`

review가 지정한 담당 함수만 다시 호출한다. 후보당 한 번만 실행하고 `retry_count`를 증가시킨다.

### `nodes/judge.py`

LLM이 아니라 Python 코드로 채점한다.

```python
total = sum(category_score / Decimal("5") * weight)
total = total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
```

필수 규칙:

- G1, G2, G3 모두 통과해야 INVEST 가능
- 총점 70점 이상
- 자체 발표 최대 3점
- 자료 없음 기본 1점
- F1~F3은 100점 총점에 포함하지 않음
- 결측 6개 이상이면 정보 부족 경고

### `nodes/skip.py`

적격성 FAIL 또는 UNKNOWN 후보를 HOLD로 기록하고 총점을 `None`으로 둔다.

### `nodes/archive.py`

현재 후보의 확정 결과를 `evaluations`에 한 번만 추가한다.

## 루트 파일

### `app.py`

전체 실행 진입점이다.

```bash
python app.py --candidates data/candidates.json
```

실행 결과 예시:

```text
[1/2] company_a: HOLD (68.5)
[2/2] company_b: INVEST (74.2)
Report: reporting/output/investment_report.pdf
```

### `requirements.txt`

팀원이 전달한 실제 사용 패키지만 취합한다. 사용하지 않는 패키지를 미리 추가하지 않는다.

### `.env.example`

변수명과 설명만 작성하고 실제 Key는 넣지 않는다.

```dotenv
LLM_API_KEY=
LLM_MODEL=
```

### `README.md`

- 프로젝트 목적
- 담당자별 실제 구현 내용
- 설치 및 환경변수
- 문서 준비와 인덱싱
- 실행 명령
- 검색 평가 결과
- 보고서 위치
- 차별점과 Lessons Learned

## 테스트 예시

```python
def test_total_score_uses_round_half_up(): ...
def test_score_70_is_invest_when_all_gates_pass(): ...
def test_failed_gate_forces_hold(): ...
def test_unknown_eligibility_has_no_total_score(): ...
def test_repair_runs_once_per_candidate(): ...
def test_archive_does_not_duplicate_candidate(): ...
def test_next_candidate_starts_with_empty_analysis(): ...
```

## Git에 올리지 않을 파일

```text
.env
실제 API Key
개인 실행 checkpoint DB
임시 디버그 출력
__pycache__/
```

## 완료 체크리스트

- [ ] 공통 스키마를 다른 세 담당자에게 공유했다.
- [ ] Mock Node로 전체 Graph가 종료까지 실행된다.
- [ ] PASS, FAIL, UNKNOWN 분기가 모두 테스트됐다.
- [ ] 병렬 분석이 모두 끝난 뒤 review가 한 번 실행된다.
- [ ] repair가 후보당 최대 한 번 실행된다.
- [ ] Decimal `ROUND_HALF_UP` 채점 테스트가 통과한다.
- [ ] 후보가 바뀔 때 이전 분석값이 초기화된다.
- [ ] 전체 후보 처리 후 report로 이동한다.
