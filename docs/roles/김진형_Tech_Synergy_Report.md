# 김진형 기술 시너지 보고서

## 목표

후보의 기술, 시험과 실증 근거를 분석하고 제조기업의 공개 작업 수요와 연결한다. 검증과 채점이 끝난 전체 후보 State를 이용해 5쪽 이내 투자보고서 PDF를 생성한다.

## 담당 브랜치

```text
feature/tech-synergy-report
```

## 담당 폴더 구조

```text
agents/
├── tech.py
├── synergy.py
└── report.py

prompts/
├── tech.md
├── synergy.md
└── report.md

reporting/
├── renderer.py
├── formatter.py
├── templates/
│   └── investment_report.html
└── output/

data/evidence/
├── tech/
└── parent/

tests/
├── test_tech.py
├── test_synergy.py
└── test_report.py
```

## `agents/`에 들어갈 파일

### `agents/tech.py`

다음 원값과 근거를 수집한다.

- T2: 창업팀 설립 전 선행 연구
- K1: 설립 후 기업 소속 공개 연구 성과
- K2: 실물 조작 성공률
- K3: 최근 3년 제조 현장 실증
- R2: 최근 3개년 기업 귀속 국가 연구비

K2 반환 예시:

```python
IndicatorEvidence(
    id="K2",
    raw_value={
        "successful_trials": 28,
        "total_trials": 30,
        "success_rate_percent": 93.33,
    },
    unit="%",
    period="2026-03",
    condition={
        "task": "배터리 셀 집기",
        "environment": "실험실 실제 로봇",
        "success_definition": "셀 손상 없이 지정 위치 이동",
        "independent_reproduction": False,
    },
    evidence_status="COMPANY_CLAIM",
    source_ids=["src_tech_test"],
    collected_by="tech",
    query_status="SUCCESS",
)
```

서로 다른 작업이나 시험 조건의 성공률을 합치지 않는다. 실물 시험 30회 미만이거나 성공 정의가 공개되지 않았다면 그 사실을 그대로 남긴다.

K3는 고객사 또는 운영기관이 확인한 서로 다른 제조 현장을 기준으로 중복을 제거한다. 계획, 협약과 투자는 완료된 실증으로 세지 않는다.

### `agents/synergy.py`

다음 원값과 근거를 수집한다.

- S1: 후보가 실제 수행한 고정 작업군 수
- S2: 모기업 문서 근거와 연결된 작업군 수
- F4: 방폭 구역과 필수 인증 확인 상태

고정 작업군:

```text
TASK1 비정형 물체 집기
TASK2 밸브·레버 조작
TASK3 배터리 셀·모듈 핸들링
TASK4 케이블·커넥터·부품 체결
TASK5 시료·용기·위험물 취급
```

S2 예시:

```python
IndicatorEvidence(
    id="S2",
    raw_value={
        "matched_task_count": 1,
        "matches": [
            {
                "task_id": "TASK2",
                "candidate_source_ids": ["src_candidate_demo"],
                "parent_source_ids": ["src_parent_p24"]
            }
        ]
    },
    unit="작업군",
    source_ids=["src_candidate_demo", "src_parent_p24"],
    collected_by="synergy",
    query_status="SUCCESS",
)
```

후보가 작업을 수행했다는 근거와 모기업에 해당 작업 수요가 있다는 근거를 모두 연결해야 한다.

### `agents/report.py`

검증과 채점이 완료된 State를 보고서 모델로 변환한다. 새로운 검색을 수행하거나 State에 없는 사실을 추가하지 않는다.

```python
from agents.report import report_node

# 전체 후보 archive 및 검증·채점 완료 후 호출
update = report_node(state)
output_path = update["report"].output_path
```

## `prompts/`에 들어갈 파일

### `prompts/tech.md`

- 기술 문서에서 원값과 시험 조건 추출
- 논문 DOI, 저자와 소속 확인
- 기업 자체 시험과 독립 재현 구분
- 수치 추정 금지

### `prompts/synergy.md`

- TASK1~TASK5 분류 기준
- 후보 수행 근거와 모기업 수요 근거 분리
- 방폭 구역, 장비 모델, 인증 범위와 유효성 구분

### `prompts/report.md`

- 검증된 State만 사용
- 첫 줄에 추천·보류와 총점
- 자료 없음과 미확인 항목 명시
- source_id가 없는 주장 금지
- 투자 실행이나 현장 사용 승인처럼 표현하지 않기

## `reporting/`에 들어갈 파일

### `reporting/renderer.py`

보고서 데이터와 템플릿을 결합하고 PDF를 생성한다.

```python
def render_investment_report(
    evaluations: list[EvaluationRecord],
    sources: list[SourceRecord],
    output_path: Path,
) -> Path:
    ...
```

### `reporting/formatter.py`

다음을 일관된 형식으로 변환한다.

- 날짜
- 원화·외화 금액
- 백분율
- 자료 없음
- 근거 상태
- source 표기

### `reporting/templates/investment_report.html`

5쪽 보고서 레이아웃을 정의한다.

```text
1쪽 상단: SUMMARY, 반 페이지 이내
1쪽 하단: 평가 대상과 사업 개요
2쪽: 기술과 제조 현장 적용
3쪽: 시장, 경쟁과 평가 종합
4쪽: 위험, 한계와 후속 실사
5쪽: REFERENCE
```

표가 페이지 밖으로 잘리지 않도록 열 수와 글자 크기를 조정한다. SUMMARY에 긴 배경 설명을 넣지 않는다.

### `reporting/output/`

최종 산출물만 둔다.

```text
investment_report_2026-09-30.pdf
investment_report_2026-09-30.json
```

반복 생성되는 임시 HTML, PNG와 테스트 PDF는 Git에 올리지 않는다.

## `data/evidence/`에 들어갈 파일

### `data/evidence/tech/`

```text
company_a_papers.json
company_a_trials.json
company_a_field_pilots.json
company_a_research_funding.json
```

시험 기록 예시:

```json
{
  "candidate_id": "company_a",
  "task": "배터리 셀 집기",
  "successful_trials": 28,
  "total_trials": 30,
  "success_definition": "셀 손상 없이 지정 위치 이동",
  "environment": "실험실 실제 로봇",
  "source_id": "src_tech_test",
  "page": 12
}
```

### `data/evidence/parent/`

모기업의 공개 문서에서 확인한 작업 수요를 저장한다.

```json
{
  "task_id": "TASK3",
  "description": "배터리 셀과 모듈 핸들링 자동화 수요",
  "doc_id": "sk_parent_report_2025",
  "page": 24,
  "source_id": "src_parent_p24"
}
```

내부 수요를 알고 있다고 가정하지 않고 공개 문서에서 확인한 내용만 사용한다.

## 보고서 Reference 예시

```text
[SRC-01] SK Innovation. Sustainability Report 2025. p.24.
[SRC-02] Company A. Robot Hand Technical Report. 2026. p.12.
```

본문과 표에서 실제 사용한 자료만 포함한다. 수집했지만 사용하지 않은 자료는 REFERENCE에 넣지 않는다.

## 보고서 검증

PDF 생성 후 다음을 확인한다.

- 5쪽 이내
- SUMMARY가 반 페이지 이내
- 한글 글꼴 깨짐 없음
- 표와 문장이 페이지 밖으로 잘리지 않음
- 모든 후보의 판정 포함
- 수치가 `EvaluationRecord`의 값과 일치
- 모든 인용이 REFERENCE의 source_id와 연결
- 마지막 페이지가 REFERENCE

## Git에 올리지 않을 파일

```text
폰트 라이선스상 배포할 수 없는 글꼴
임시 렌더링 이미지
브라우저 캐시
비공개 내부 자료
검증되지 않은 보고서 초안
```

## 완료 체크리스트

- [x] tech가 T2, K1, K2, K3, R2 원값을 반환한다.
- [x] K2에 시험 횟수, 성공 정의와 환경이 포함된다.
- [x] synergy가 S1, S2, F4 원값을 반환한다.
- [x] S2에 후보 근거와 모기업 페이지 근거가 함께 연결된다.
- [x] Agent가 점수와 투자 판정을 직접 만들지 않는다.
- [x] 보고서는 완료 표시 또는 공통 judge의 archive 계약을 검증한 State만 사용한다(G1 생략 후보 예외).
- [x] 가상 데이터 검증에서 PDF 5쪽, 한글 출력, SUMMARY 반 페이지, 마지막 REFERENCE를 확인했다.
- [ ] 실제 확정 후보·RAG·review/judge와 통합한 최종 투자보고서를 검증한다.

## 구현 및 팀 전달 사항 (2026-09-30)

실행법, 원값 형식, evidence JSON, LLM 추출기 연결, repair와 archive 계약은
[담당 모듈 안내](../../reporting/README.md)에 정리했다.

- 담당 브랜치: `feature/tech-synergy-report`.
- 검증 결과: main 통합 기준 전체 `pytest` 184개 통과. 가상 후보 3개·각 12개 지표 PDF와 저장소 후보 3개의 전체 Graph → 5쪽 PDF/JSON 생성도 확인했다.
- 추가 의존성: `reporting/requirements.txt`. 공통 requirements와 다른 담당자 파일은 수정하지 않았다.
- 독립 수행 근거만 S1·S2 확정 개수에 포함한다. 자체 발표는 잠정 작업으로 보존한다.
- RAG 호출은 지표별 최초·재작성·repair를 합쳐 최대 3회다.
- PDF의 숫자·판정은 EvaluationRecord를 그대로 사용한다. 사용한 출처만 REFERENCE와 JSON에 포함한다.
- 보고서 Node는 `ReportResult` 모델을 반환한다(현 공통 인터페이스 준수).
- archive는 명시적 완료 표시 또는 main judge의 결측 지표 metadata 계약을 지원한다. 호출자는 실제 review·judge를 거친 평가를 전달한다.
- 공통 repair의 handler 호출 시점과 judge의 T2·R2·S1·F4 필드 형식에 담당 코드만 맞췄다.
- 저장소 후보·로컬 근거·공통 Graph와 연결을 확인했다. 외부 LLM·실제 RAG 인덱스 및 원자료 사실 검증은 별도로 필요하다.

```bash
python -m pip install -r requirements-dev.txt -r reporting/requirements.txt
python -m pytest -q
python -m reporting.demo --output /tmp/physical-agent-demo.pdf
```

데모 파일은 가상 데이터 표시가 있는 출력 검증용이며 제출용 실제 투자보고서가 아니다.
반복 실행할 때는 새 출력 이름을 사용한다. 담당 기능 브랜치의 변경을 사용자 요청에 따라 main에 통합한다.
병합 변경 범위는 김진형 담당 파일 18개이며 다른 담당자의 구현은 수정하지 않는다.
