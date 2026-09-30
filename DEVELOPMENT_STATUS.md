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
- [x] 전체 통합 단위 테스트 23종 전원 통과 (23/23 passed)

## 진행 중인 작업

- [ ] 세진 님의 검토 및 Git commit/push 승인 대기

## 다음 작업

1. 세진 님의 지시 시 commit & push 수행
2. 김진형 님 브랜치(tech, synergy) 및 김도현 님 브랜치(graph, judge) 연계를 위한 인터페이스 점검

## 변경된 파일

- `agents/competitor.py`
  - KIPRIS/USPTO 공식 권리자 기준 Q 유효 등록 특허 파싱, 고유 패밀리 중복 제거, 벤치마크 제품 비교 생성 `competitor_node`, `competitor_candidate` 구현 및 검증 로직 강화
- `data/evidence/patent/arobot_patents.json`
  - 에이로봇 KIPRIS 특허 검색식, 유효 등록 특허 3건, 고유 우선권 패밀리 3건, 벤치마크 제품(Shadow Robot, Wonik) 데이터
- `data/evidence/patent/aidin_robotics_patents.json`
  - 에이딘로보틱스 KIPRIS 및 USPTO 특허 검색식, 유효 등록 특허 5건, 고유 우선권 패밀리 4건, 벤치마크 제품(ATI, Robotiq) 데이터
- `tests/test_competitor.py`
  - 에이로봇/에이딘로보틱스 검증, ACCESS_FAILED 시 summary 상태 표기 검증, 파일 부재 검증, raw_value 정합성 검증, 후보군 충돌 방지 검증, repair 검증 등 7종
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
python3 -m pytest tests/test_schemas.py tests/test_discover.py tests/test_market.py tests/test_competitor.py
```

결과:

PASS (23 passed in 0.07s)

확인한 항목:
- 에이로봇 등록 특허 3건 ➔ 3개 고유 우선권 패밀리 정상 파싱 확인.
- 에이딘로보틱스 국내외 등록 특허 5건(KR 4건 + US 1건) ➔ 최초 우선권 기준 4개 고유 패밀리 중복 제거 정상 확인.
- 조회 실패(ACCESS_FAILED) 발생 시 summary에 "0개 패밀리"로 찍히지 않고 실패 상태와 사유가 명시되는지 확인.
- query_status/evidence_status 미기재 시 기본 SUCCESS로 간주하지 않고 엄격 검증 확인.
- 미등록(출원) 및 Q 무관 특허 excluded 목록 분리 확인.
- Shadow Robot, Wonik, ATI, Robotiq 등 벤치마크 제품 사양 데이터 comparison_products 정상 반환 확인.
- 벤치마크 대상에 투자 후보 기업이 포함될 경우 충돌 예외 발생 확인.
- GraphState 입력 시 전체 State가 아닌 `{"competitor_analysis": ..., "sources": ..., "comparison_products": ...}` 부분 딕셔너리만 반환 확인.
- 세진 님 담당 3대 노드(discover, market, competitor) 전체 통합 23개 테스트 전원 통과.

## 미해결 문제

- 없음.

## 다른 팀원에게 영향을 주는 변경

- API 변경 여부: 없음.
- State/Schema 변경 여부: 없음 (`AgentNodeUpdate` 부분 반환 규격 준수).
- requirements 변경 여부: 없음.
- 다른 브랜치에서 대응이 필요한 내용: 없음.

## Git 상태

현재는 로컬 개발 완료 상태이며 아직 commit/push 하지 않음.
다음 commit 후보 메시지:
:sparkles:[FEAT] competitor 에이전트 구현 및 M1 특허 패밀리·경쟁사 벤치마크 수집 로직 추가
