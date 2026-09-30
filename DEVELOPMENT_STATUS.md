# Development Status

## 현재 상태

- 담당자: 박세진
- 브랜치: feature/discover-market-competitor
- 현재 단계: STEP 4 세진 님 담당 3개 에이전트(discover, market, competitor) 및 원천 데이터·단위 테스트 전원 구현 및 검증 완료
- 마지막 업데이트: 2026-09-30 11:50

## 완료된 작업

- [x] 담당 영역 기본 디렉터리 구조 생성
- [x] `data/candidates.json` 평가 대상 후보 2개사(에이로봇, 에이딘로보틱스) 확정
- [x] `prompts/discover.md`, `market.md`, `competitor.md` 프롬프트 3종 작성
- [x] `data/evidence/company/arobot.json`, `aidin_robotics.json` 기업별 원천 팩트 데이터 구축
- [x] `agents/discover.py` 후보 정보 확인, G1 팩트 및 T1/R1/R3/F1~F3 원값 수집 노드 구현
- [x] `tests/test_discover.py` 단위 테스트 5종 작성 및 통과
- [x] `data/evidence/market/robot_parts_sales_2022_2025.json`, `manufacturing_robot_sales_2022_2025.json` 공식 통계 원천 데이터 구축
- [x] `agents/market.py` 한국 도입 시장 기준 P1 3개년 CAGR 계산용 원값 수집 노드 `market_node` 구현
- [x] `tests/test_market.py` 단위 테스트 7종 작성 및 통과
- [x] `data/evidence/patent/arobot_patents.json`, `aidin_robotics_patents.json` KIPRIS/USPTO 공식 특허 권리자 및 고유 패밀리 데이터 구축
- [x] `agents/competitor.py` 경쟁 제품 비교 및 M1 유효 등록 특허 고유 패밀리 수집 노드 `competitor_node` 구현
  - 조회 실패(ACCESS_FAILED 등) 시 summary에 "0개 패밀리"로 왜곡되지 않고 실패 상태 명시
  - `query_status`, `evidence_status` 누락 시 기본값 SUCCESS 허용하지 않고 검증 에러 발생
  - 원천 파일 미존재 시 조용한 1점 fallback 대신 명시적 `FileNotFoundError` 발생
  - KIPRIS, USPTO 등 복수 출처(`sources`) 및 패밀리/제품별 `source_ids` 유효성 검증
  - 벤치마크 기업과 투자 평가 대상 후보군(`candidates`) 충돌 방지 로직 적용
  - Q(정밀조작/센서) 키워드 기반 유효 등록 특허 검증
- [x] `tests/test_competitor.py` 단위 테스트 7종 작성 및 통과
- [x] `tests/test_integration_agents.py` 3대 노드 E2E 파이프라인 및 Repair 통합 테스트 4종 작성 및 통과
- [x] 세진 님 담당 에이전트 단위/통합 테스트 27종 전원 통과 (27/27 passed)

## 진행 중인 작업

- [x] 3대 에이전트 통합 E2E 테스트 및 repair 호환성 강화, 작업 이력 갱신 완료

## 다음 작업

1. 김진형 님 브랜치(tech, synergy) 및 김도현 님 브랜치(graph, judge) 연계를 위한 인터페이스 점검 및 통합 테스트
2. 메인 브랜치 머지 준비

## 변경된 파일

- `agents/discover.py`
  - ControlState, dict, repair_targets 객체를 유연하게 파싱하는 `_extract_repair_indicator_ids` 적용
- `agents/market.py`
  - ControlState, dict, repair_targets 객체를 유연하게 파싱하는 `_extract_repair_indicator_ids` 적용
- `agents/competitor.py`
  - KIPRIS/USPTO 공식 권리자 기준 Q 유효 등록 특허 파싱, 고유 패밀리 중복 제거, 벤치마크 제품 비교 생성 `competitor_node`, `competitor_candidate` 구현 및 검증 로직 강화
- `data/evidence/patent/arobot_patents.json`
  - 에이로봇 KIPRIS 특허 검색식, 유효 등록 특허 3건, 고유 우선권 패밀리 3건, 벤치마크 제품(Shadow Robot, Wonik) 데이터
- `data/evidence/patent/aidin_robotics_patents.json`
  - 에이딘로보틱스 KIPRIS 및 USPTO 특허 검색식, 유효 등록 특허 5건, 고유 우선권 패밀리 4건, 벤치마크 제품(ATI, Robotiq) 데이터
- `tests/test_competitor.py`
  - 에이로봇/에이딘로보틱스 검증, ACCESS_FAILED 시 summary 상태 표기 검증, 파일 부재 검증, raw_value 정합성 검증, 후보군 충돌 방지 검증, repair 검증 등 7종
- `tests/test_integration_agents.py`
  - 3대 에이전트(Discover -> Market -> Competitor) 파이프라인 E2E 시뮬레이션 및 State 누적, 출처 연결 정합성, Repair Loop 검증 4종 신규 추가
- `DEVELOPMENT_STATUS.md`
  - 개발 현황 갱신

## 현재 인터페이스

```python
from schemas import AgentNodeUpdate, AnalysisResult, Candidate, GraphState, IndicatorEvidence, SourceRecord

def competitor_candidate(
    candidate: Candidate,
    evidence_dir: Path | str | None = None,
    candidate_pool: list[Candidate] | None = None,
    indicator_ids: list[str] | None = None,
) -> tuple[AnalysisResult, list[SourceRecord], list[dict[str, Any]]]:
    """공식 권리정보 기준 M1 유효 등록 특허 고유 패밀리 수집 및 벤치마크 비교."""
    ...

def competitor_node(state: GraphState) -> AgentNodeUpdate:
    """LangGraph node: current_candidate 대상 competitor 분석 및 competitor_analysis, comparison_products 부분 반환."""
    ...
```

## 테스트 결과

실행 명령:

```bash
python3 -m pytest tests/test_schemas.py tests/test_discover.py tests/test_market.py tests/test_competitor.py tests/test_integration_agents.py
```

결과:

PASS (27 passed in 0.08s)

확인한 항목:
- 에이로봇 / 에이딘로보틱스 2개사 전체 Discover ➔ Market ➔ Competitor 연속 실행 파이프라인 검증 완료.
- State에 `company_profile`, `market_analysis`, `competitor_analysis`, `comparison_products`, `sources` 정상 누적 확인.
- 전체 수집된 9개 지표(G1, T1, R1, R3, F1, F2, F3, P1, M1) 및 벤치마크 제품의 모든 `source_id`가 누적된 `sources`에 1:1로 결측 없이 연결됨을 검증.
- ControlState (Pydantic 객체) 및 EvidenceReview (dict 형태) 양쪽 모두에서 Repair Loop(지표 개별 재수집)가 정상 작동함을 검증.
- 세진 님 담당 3대 노드 및 통합 테스트 27개 테스트 전원 통과.

## 작업 이력 (Work History)

| 일시 | 커밋 해시 | 커밋 구분 | 주요 작업 내용 |
| :--- | :--- | :--- | :--- |
| 2026-09-30 | `96006e3` | `:sparkles:[FEAT]` | 담당 영역 디렉터리 구조(`agents/`, `prompts/`, `data/evidence/`) 초기화 |
| 2026-09-30 | `8ce0ea9` | `:sparkles:[FEAT]` | 평가 대상 후보 2개사(에이로봇, 에이딘로보틱스) 확정 데이터(`candidates.json`) 생성 |
| 2026-09-30 | `7395959` | `:sparkles:[FEAT]` | 후보 탐색, 시장 분석, 경쟁사 분석 프롬프트 3종 작성(`prompts/*.md`) |
| 2026-09-30 | `fca8ad1` | `:sparkles:[FEAT]` | Discover 에이전트(`agents/discover.py`), 기업별 원천 팩트 데이터(`data/evidence/company/`), 단위 테스트(`tests/test_discover.py`) 구현 |
| 2026-09-30 | `701b1f2` | `:sparkles:[FEAT]` | Market 에이전트(`agents/market.py`), 한국 로봇 시장 공식 통계 데이터(`data/evidence/market/`), 단위 테스트(`tests/test_market.py`) 구현 |
| 2026-09-30 | `0ad5a3e` | `:sparkles:[FEAT]` | Competitor 에이전트(`agents/competitor.py`), KIPRIS/USPTO 특허 원천 데이터(`data/evidence/patent/`), 단위 테스트(`tests/test_competitor.py`) 구현 및 실패 상태/출처 유효성 검증 로직 반영 |
| 2026-09-30 | `87aec07` | `:recycle:[REF]` | 개발 현황 문서(`DEVELOPMENT_STATUS.md`) 최신 진행 상황 갱신 |
| 2026-09-30 | (현재) | `:white_check_mark:[TEST]` | 3대 에이전트 통합 E2E 파이프라인 테스트(`tests/test_integration_agents.py`) 추가 및 `discover.py`/`market.py` 보정(repair) 인터페이스 호환성 강화 |

## 미해결 문제

- 없음.

## 다른 팀원에게 영향을 주는 변경

- API 변경 여부: 없음.
- State/Schema 변경 여부: 없음 (`AgentNodeUpdate` 부분 반환 규격 준수).
- requirements 변경 여부: 없음.
- 다른 브랜치에서 대응이 필요한 내용: 없음.

## Git 상태

원격 브랜치(`origin/feature/discover-market-competitor`)로 커밋 및 푸시 완료.
모든 단위/통합 테스트(27/27 PASS) 통과 확인.

