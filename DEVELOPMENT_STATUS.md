# Discover / Market / Competitor 개발 현황

- **담당자**: 박세진
- **작업 브랜치**: `feature/discover-market-competitor`
- **진행 상태**: 담당 에이전트 3종(Discover, Market, Competitor), 프롬프트, 원천 증거 데이터, 단위/통합 테스트 구현 완료 (테스트 28/28 PASS)

---

## 1. 구현 모듈 요약

### 1) 후보 기업 관리 (`data/candidates.json`)
- 국내 피지컬 AI 로봇 부품 기업 2곳 확정
  - **에이로봇 (`arobot`)**: 다자유도 로봇 핸드 / Series A
  - **에이딘로보틱스 (`aidin_robotics`)**: 6축 힘·토크 및 촉각 센서 / Series B
- 글로벌 기준점 및 VLA 세그먼트 검증용 해외 기업 1곳 추가
  - **Figure AI (`figure_ai`)**: 미국 법인 / Series C / VLA 조작 지능

### 2) Discover 에이전트 (`agents/discover.py`)
- **담당 지표**: G1(적격성 사실), T1(핵심인력), R1(누적투자), R3(고용증가), F1(유동성/현금흐름), F2(자본건전성), F3(행정처분/제재)
- **주요 구현 사항**:
  - 점수 계산이나 적격 판정 없이 있는 그대로의 원값(`raw_value`)과 단위, 출처(`source_ids`)만 수집.
  - 기업 보도자료, 홈페이지, LinkedIn 등 자체 주장 자료는 `COMPANY_CLAIM`으로 분리하여 향후 평가 노드에서 3점 상한이 적용될 수 있도록 구성.
  - 공시/감사보고서 기반 데이터는 `THIRD_PARTY_VERIFIED` 처리.
  - F1, F2, F3 출처를 evidence 파일에서 동적으로 읽도록 구현 (하드코딩 제거).

### 3) Market 에이전트 (`agents/market.py`)
- **담당 지표**: P1 (한국 도입 시장 기준 3개년 CAGR 계산용 원값)
- **주요 구현 사항**:
  - 후보 기업 소재지와 무관하게 한국 도입 시장 공식 통계(로봇산업실태조사, KOSIS)를 기준으로 고정.
  - 제품군 매핑: 로봇 핸드/센서는 '로봇 부품 및 부분품', 완제품은 '제조업용 로봇' 매핑.
  - VLA 소프트웨어 세그먼트(Figure AI 등)는 제조 통계에 임의 배정하지 않고 `QueryStatus.NO_DATA` 및 누락 사유(`missing_reason`) 처리 (설계서 5-8 준수).
  - 시작연도 매출이 0 이하인 경우 `INVALID_DENOMINATOR` 예외 상태 처리.

### 4) Competitor 에이전트 (`agents/competitor.py`)
- **담당 지표**: M1 (특허청 공식 권리자 기준 Q 유효 등록 특허 및 고유 우선권 패밀리 수), 벤치마크 제품 비교군
- **주요 구현 사항**:
  - KIPRIS 및 USPTO 등록원부 기준 등록(유효) 특허만 집계 (공개 출원 및 비Q 특허는 `excluded`로 제외).
  - 최초 우선권 번호 기준 패밀리 중복 제거 검증 (`len(family_ids) == unique_priority_families`).
  - 물리 AI 관련 기술(Q 키워드: 그리퍼, 로봇핸드, 촉각, 토크, 센서 등) 정합성 확인.
  - 글로벌/국내 벤치마크 비교 제품(Shadow Robot, Wonik, ATI, Robotiq, Tesla, Boston Dynamics) 데이터 구축 및 투자 후보군 충돌 방지 로직 적용.
  - 조회 실패(`ACCESS_FAILED` 등) 시 요약문에 "0개 패밀리"로 왜곡 표기되지 않고 실패 상태 및 사유를 명시하도록 안전장치 보완.
  - `query_status`, `evidence_status` 미기재 시 기본 SUCCESS 간주를 차단하고 검증 에러 발생.

### 5) 보정(Repair) 루프 공통 헬퍼 (`_extract_repair_indicator_ids`)
- `discover.py`, `market.py`, `competitor.py` 전체에 동일 헬퍼 적용.
- `ControlState` (Pydantic 모델), 일반 `dict`, `EvidenceReview.repair_targets` 등 어떤 형태로 재시도 요청이 들어와도 에러 없이 대상 지표만 재수집하도록 호환성 강화.

---

## 2. 테스트 결과

```bash
python3 -m pytest tests/test_schemas.py tests/test_discover.py tests/test_market.py tests/test_competitor.py tests/test_integration_agents.py
```

- **결과**: `28 passed in 0.10s` (100% PASS)
- **주요 검증 항목**:
  - `test_discover.py` (5종): 원값 수집, 출처 매핑, 결측 처리, repair 동작 검증
  - `test_market.py` (7종): 부품/제조로봇 CAGR 계산, VLA 결측 규칙, 분모 0 오류 방어 검증
  - `test_competitor.py` (7종): 패밀리 중복 제거, 비Q/출원 특허 배제, ACCESS_FAILED 요약문 왜곡 방지, 벤치마크 충돌 방지 검증
  - `test_integration_agents.py` (5종): 
    - 에이로봇 / 에이딘로보틱스 Discover ➔ Market ➔ Competitor 순차 실행 및 State 누적 E2E 검증
    - Figure AI 글로벌 VLA 파이프라인(Series C 수집, VLA 시장 통계 결측 규칙, USPTO 특허 수집) 검증
    - 수집된 모든 Indicator 및 벤치마크 제품의 `source_id`가 누적된 `sources`에 1:1로 결측 없이 존재하는지 무결성 검증
    - Pydantic / Dict 양방향 Repair Loop 시뮬레이션 검증

---

## 3. 팀원 공유 사항 (인터페이스 메모)

### 김도현 님 (Graph / Judge) 참고
- **G1 반환 규격**: `company_profile.indicators` 내 `id="G1"`, `unit="4개 요건 사실"`로 단일 IndicatorEvidence 반환.
  ```python
  raw_value = {
      "unlisted": {"value": True, "checked_markets": [...], "source_id": "..."},
      "latest_round": {"value": "Series A", "announced_at": "...", "source_id": "..."},
      "exit_completed": {"value": False, "source_id": "..."},
      "operating_status": {"value": "정상", "as_of": "...", "source_id": "..."}
  }
  ```
  `judge` 노드에서 `ind.id == "G1"` 조회 후 위 키값으로 적격 여부(PASS/FAIL)를 판정하시면 됩니다.
- **Figure AI 특이사항**: 미국 비상장 법인이지만 `latest_round`가 `Series C`입니다. 설계서상 Seed~Series B 기준 적용 시 적격성 분기(FAIL/HOLD) 검증용 케이스로 활용 가능합니다.

### 김진형 님 (Tech / Synergy / Report) 참고
- 후보 기업별 벤치마크 제품 데이터(`comparison_products`)는 `data/evidence/patent/{candidate_id}_patents.json`에 정리되어 있으며, `competitor_analysis.summary`에도 비교 현황이 요약되어 있습니다.
- `discover` 수행 중 수집된 연구진 논문/실증 관련 URL은 필요 시 `data/evidence/company/{candidate_id}.json` 내 출처 링크를 통해 연계 가능합니다.

---

## 4. 커밋 이력

| 일시 | 커밋 | 태그 | 내용 |
| :--- | :--- | :--- | :--- |
| 2026-09-30 | `96006e3` | `:sparkles:[FEAT]` | 담당 영역(agents, prompts, evidence) 디렉터리 구조 생성 |
| 2026-09-30 | `8ce0ea9` | `:sparkles:[FEAT]` | 평가 대상 후보 2개사(에이로봇, 에이딘로보틱스) 확정 데이터 추가 |
| 2026-09-30 | `7395959` | `:sparkles:[FEAT]` | 후보 탐색, 시장 분석, 경쟁사 분석 프롬프트 3종 작성 |
| 2026-09-30 | `fca8ad1` | `:sparkles:[FEAT]` | Discover 에이전트 구현 및 기업별 원천 팩트 데이터 구축 |
| 2026-09-30 | `701b1f2` | `:sparkles:[FEAT]` | Market 에이전트 구현 및 한국 로봇 시장 공식 통계 수집 로직 추가 |
| 2026-09-30 | `0ad5a3e` | `:sparkles:[FEAT]` | Competitor 에이전트 구현 및 특허 패밀리·벤치마크 수집 로직 추가 |
| 2026-09-30 | `87aec07` | `:recycle:[REF]` | 개발 현황 문서 갱신 |
| 2026-09-30 | `93f8b4a` | `:white_check_mark:[TEST]` | 3대 에이전트 통합 E2E 파이프라인 테스트 추가 및 repair 호환성 강화 |
| 2026-09-30 | `08a324a` | `:sparkles:[FEAT]` | 글로벌 VLA 기준점 후보 기업 Figure AI 추가 및 원천 데이터·검증 테스트 구현 |
| 2026-09-30 | (현재) | `:recycle:[REF]` | 개발 현황 문서(DEVELOPMENT_STATUS.md) 가독성 개선 및 팀 공유 인터페이스 명세 정리 |
