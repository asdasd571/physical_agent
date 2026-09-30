# 박세진 후보 시장 경쟁사 분석

## 목표

사전에 확정된 후보의 법인·투자·재무·고용 정보를 확인하고 시장과 경쟁 제품·특허 정보를 수집한다. 원값과 출처를 공통 형식으로 반환하며 점수와 최종 판정은 만들지 않는다.

## 담당 브랜치

```text
feature/discover-market-competitor
```

## 담당 폴더 구조

```text
agents/
├── discover.py
├── market.py
└── competitor.py

prompts/
├── discover.md
├── market.md
└── competitor.md

data/
├── candidates.json
└── evidence/
    ├── company/
    ├── market/
    └── patent/

tests/
├── test_discover.py
├── test_market.py
└── test_competitor.py
```

## `agents/`에 들어갈 파일

### `agents/discover.py`

확정 후보의 기본정보와 다음 원값을 수집한다.

- G1: 비상장, Seed~Series C, Exit 미완료, 정상 법인 여부
- T1: 핵심 기술진 경력
- R1: 누적 투자액
- R3: 동일 법인 종업원 증가율
- F1: 현금 런웨이 계산용 원값
- F2: 자본 건전성 계산용 원값
- F3: 공식 결격 이력 조회 결과

반환 예시:

```python
return {
    "company_profile": AnalysisResult(
        candidate_id="company_a",
        summary="한국 소재 비상장 Series A 로봇 기업",
        indicators=[t1, r1, r3, f1, f2, f3],
        source_ids=["src_registry", "src_funding"],
        query_attempts=query_attempts,
    ),
    "sources": source_records,
}
```

후보를 새로 추천하거나 자동 발굴하지 않는다.

### `agents/market.py`

P1 시장 성장률 계산에 필요한 원값을 수집한다.

저장할 값:

- 후보의 주력 제품 세그먼트
- 한국 도입 시장의 대응 통계 세그먼트
- 기준연도 `t`
- 비교연도 `t-3`
- 두 연도의 매출 원값과 단위
- CAGR 계산에 사용한 공식 통계 페이지

예시:

```python
IndicatorEvidence(
    id="P1",
    raw_value={
        "start_revenue": 1200,
        "end_revenue": 1680,
        "start_year": 2022,
        "end_year": 2025,
        "cagr_percent": 11.87,
    },
    unit="억원, %",
    period="2022-2025",
    source_ids=["src_market_2025"],
    collected_by="market",
)
```

VLA 소프트웨어처럼 직접 대응 통계가 없으면 제조 로봇 시장에 임의 배정하지 않고 자료 없음으로 남긴다.

### `agents/competitor.py`

경쟁 제품, 기업과 M1 특허 원값을 수집한다.

특허 처리 규칙:

- 공식 권리정보 사용
- 현재 기업이 권리자인 특허
- Q 관련 기술 여부 확인
- 등록 상태와 유효성 확인
- 우선권 기준 패밀리 중복 제거
- 검색 실패와 정상 조회 0건 구분

반환 예시:

```python
IndicatorEvidence(
    id="M1",
    raw_value={
        "valid_registered_patents": 5,
        "unique_priority_families": 3,
        "family_ids": ["FAM-001", "FAM-002", "FAM-003"],
    },
    unit="특허 패밀리",
    as_of=date(2026, 9, 30),
    source_ids=["src_patent_search"],
    collected_by="competitor",
)
```

## `prompts/`에 들어갈 파일

### `prompts/discover.md`

- 입력 후보만 조사하도록 제한
- 법인명과 동명이인 구분
- 원값을 추정하지 않는 규칙
- 모든 주장에 source 연결 요구

### `prompts/market.md`

- 한국 도입 시장으로 범위 고정
- 후보 제품과 통계 세그먼트 대응 확인
- 기간, 단위와 계산 원값 반환

### `prompts/competitor.md`

- 경쟁 제품 비교 항목
- 특허 등록·유효 상태 확인
- 우선권 패밀리 중복 제거
- 자체 발표와 공식 자료 구분

프롬프트에는 API Key, 특정 후보의 실제 답이나 검증되지 않은 숫자를 넣지 않는다.

## `data/candidates.json`

후보 2~3개를 사람이 확정해 저장한다.

```json
[
  {
    "candidate_id": "company_a",
    "legal_name": "Company A Inc.",
    "country": "KR",
    "legal_id": "법인 식별자",
    "founded_at": "2021-04-01",
    "primary_segment": "robot_hand",
    "latest_round": "Series A",
    "listing_sources": ["https://example.com/exchange-search"],
    "registry_sources": ["https://example.com/registry"],
    "evidence_urls": ["https://example.com/funding-news"]
  }
]
```

실제 후보 값이 확인되지 않았으면 예시 데이터를 확정 후보처럼 커밋하지 않는다.

## `data/evidence/`에 들어갈 파일

### `data/evidence/company/`

법인, 투자, 재무, 고용과 제재 조회 결과를 저장한다.

```text
company_a_registry_2026-09-30.json
company_a_funding_rounds_2026-09-30.json
company_a_financials_2025.json
company_a_employment_2025_2026.json
company_a_risk_search_2026-09-30.json
```

### `data/evidence/market/`

시장 통계 원값, 표 번호와 출처 URL을 저장한다.

```text
robot_parts_sales_2022_2025.json
kosis_query_2026-09-30.json
```

### `data/evidence/patent/`

특허 검색 조건과 결과를 저장한다.

```json
{
  "candidate_id": "company_a",
  "searched_at": "2026-09-30T11:20:00+09:00",
  "query": "권리자=(Company A) AND 로봇핸드",
  "query_status": "SUCCESS",
  "result_count": 4,
  "family_count": 3,
  "records": []
}
```

자동 접근이 어려워 수동으로 확인한 경우에도 조회일, 검색식, 결과와 확인자를 남긴다.

## 조회 상태 예시

자료 없음:

```python
raw_value = None
query_status = "NO_DATA"
missing_reason = "공개된 동일 법인 종업원 수를 찾지 못함"
```

정상 조회 결과 0건:

```python
raw_value = 0
query_status = "SUCCESS"
missing_reason = None
```

접근 실패:

```python
raw_value = None
query_status = "ACCESS_FAILED"
missing_reason = "공식 검색 서비스 응답 실패"
```

## 김진형에게 전달할 자료

후보 기본정보 조사 중 발견한 다음 URL을 함께 전달한다.

- 창업자와 CTO의 공개 이력
- 창업자의 설립 전 논문과 DOI 후보
- 정부 연구개발 과제와 기업 귀속 연구비
- 제품 시험이나 제조 현장 실증 자료

자료 수집은 지원하되 T2, K1, K2, K3, R2의 정의 적용은 김진형이 담당한다.

## Git에 올리지 않을 파일

```text
개인정보가 포함된 비공개 자료
로그인 세션과 쿠키
API Key
출처가 불분명한 임의 숫자
라이선스상 재배포할 수 없는 원문
```

## 완료 체크리스트

- [ ] 후보 2~3개의 필수 입력값이 작성됐다.
- [ ] G1 판단용 URL과 조회일이 기록됐다.
- [ ] discover가 T1, R1, R3, F1~F3 원값을 반환한다.
- [ ] market이 P1의 기간, 단위, 세그먼트를 반환한다.
- [ ] competitor가 M1의 유효 특허 패밀리를 반환한다.
- [ ] 자료 없음, 실제 0건, 접근 실패를 구분한다.
- [ ] 모든 `source_ids`가 실제 SourceRecord를 가리킨다.
- [ ] 점수와 투자 판정을 Agent 내부에서 계산하지 않는다.
