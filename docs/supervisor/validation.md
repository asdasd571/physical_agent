# 검증 기록

2026년 10월 13일에 실행한 결과입니다. 운영 실행과 의도적으로 오류를 넣은 검증 시나리오를 구분했습니다.

## 자동 테스트

`LANGSMITH_TRACING=false python -m pytest -q --junitxml=artifacts/pytest.xml`을 실행하여 223개 테스트가 통과했습니다. 기존 테스트 190개와 Supervisor 및 채점·문서·적격성 회귀 테스트 33개입니다. PyMuPDF 바인딩의 사용 중단 예정 경고 5건이 있으며 테스트 실패는 없습니다. 원본 결과는 [pytest.xml](evidence/pytest.xml)에 있습니다.

신규 테스트는 State에 따른 담당자 선택 변경, 기술 근거 재조사, 적격성 탈락, 담당자의 다른 결과 접근 차단, 제어 필드 수정 거부, 예외 후 복구, 영구 실패 종료, 보고서 재작성, 지속적인 품질 실패, 인용·관점 누락, 파일 변조, SQLite 재개와 기존 에이전트 통합을 확인합니다.

## 실제 RAG·LLM 실행

- 실행 명령은 `python app.py --run-id supervisor-corpus200-verified-20261013 --evaluation-date 2026-10-13`입니다.
- 원문 17개, 사용 페이지 200개, 청크 255개로 BGE-M3·Kiwi BM25·RRF 인덱스를 다시 만들었습니다.
- Tech·Synergy는 실제 검색 및 LLM 근거 추출을 실행했습니다. 후보 해설도 실제 LLM 응답을 사용했습니다.
- 담당 에이전트의 최종 오류 기록은 없습니다. 본문에 사용할 수 없는 근거는 수치로 추정하지 않았습니다.
- 최초 보고서의 품질 평가가 통과하여 운영 실행에서는 보고서 재작성 루프가 발생하지 않았습니다. 재작성 경로는 아래 별도 시나리오로 검증했습니다.

| 후보 | 담당자 호출 | 종료 | 투자 규칙 결과 |
|---|---|---|---|
| 에이로봇 | Discover 1회, Tech 2회, Synergy 2회, Competitor 1회, Market 1회입니다. | 근거 부족 상태에서 조사 한도에 도달했습니다. | HOLD, 42.0점입니다. |
| 에이딘로보틱스 | Discover 1회, Tech 2회, Synergy 2회, Competitor 1회, Market 1회입니다. | 근거 부족 상태에서 조사 한도에 도달했습니다. | HOLD, 45.3점입니다. |
| Figure AI | Discover 1회, Tech 2회, Synergy 2회, Competitor 1회, Market 2회입니다. | Series C이므로 투자 대상은 제외하되 비교 분석을 진행했습니다. | HOLD, 비교 점수 33.3점입니다. |

보고서의 품질 통과와 후보의 근거 충분성은 서로 다른 판정입니다. 미확인 항목과 출처의 한계를 명시한 보고서는 형식상 품질 기준을 통과할 수 있습니다. 이를 해당 후보의 투자 근거가 충분하다는 뜻으로 해석하지 않습니다.

운영 실행의 원본은 [LangSmith 실행](https://smith.langchain.com/o/e4414c93-2ee4-4f39-9fa6-0a03aaddc4c3/projects/p/ef520cd3-1898-45ff-bc9f-19afd6b901ff/r/de10b31f-89c7-46a1-84c4-7632ee41515a)입니다. 해당 LangSmith 프로젝트 접근 권한이 필요합니다. 공개 공유는 설정하지 않았습니다.

- [최종 실행 기록](evidence/live/run.json)과 [노드 실행 순서](evidence/live/events.jsonl)입니다.
- [품질 평가 결과](evidence/live/quality.json)입니다.
- [후보 평가 PDF](evidence/live/report.r0.pdf)와 [원값·출처 JSON](evidence/live/report.r0.json)입니다.
- [LangSmith 원본 조회 결과](evidence/live/langsmith-trace.json)와 같은 폴더의 `tracing-1.png`부터 이어지는 이미지입니다.

## 통제된 결함 주입

### 보고서 품질 미달과 재작성

`python -m scripts.verify_supervisor_scenarios quality-repair`를 실행했습니다. 테스트용으로 기술 추천 표현을 해설에 넣었습니다. 첫 평가에서 중립성 미달을 판정한 뒤 원값 중심으로 재작성했고, 두 번째 평가에서 통과했습니다. 실제 운영 LLM이 이 문장을 생성했다는 뜻은 아닙니다.

[LangSmith 실행](https://smith.langchain.com/o/e4414c93-2ee4-4f39-9fa6-0a03aaddc4c3/projects/p/ef520cd3-1898-45ff-bc9f-19afd6b901ff/r/70274d27-8262-4962-b8e2-1559ad8bc89f), [평가 이력](evidence/quality-repair/quality.json), [실행 기록](evidence/quality-repair/run.json)에 근거를 남겼습니다.

### 담당자 작업 실패 후 재시도

`python -m scripts.verify_supervisor_scenarios worker-retry`를 실행했습니다. 후보별 첫 Tech 호출에 TimeoutError를 주입했습니다. Supervisor가 다시 Tech를 호출했고 후속 호출은 정상 종료했습니다. 기술 근거가 충분해졌다는 뜻은 아니며, 최종 판정에서는 남은 근거 부족을 그대로 반영했습니다.

[LangSmith 실행](https://smith.langchain.com/o/e4414c93-2ee4-4f39-9fa6-0a03aaddc4c3/projects/p/ef520cd3-1898-45ff-bc9f-19afd6b901ff/r/033d5cf0-c705-49fb-8404-419eea1cacdc), [실행 기록](evidence/worker-retry/run.json)에 근거를 남겼습니다.

## 제출 자료와 남은 확인

[평가 보고서](evidence/evaluation_report.pdf)는 설계·검증 설명 2페이지와 운영 결과 7페이지로 구성한 총 9페이지 문서입니다. 과제의 최대 10페이지 조건에 맞췄습니다. 초기 단계 비교 점수는 에이로봇 44.7점, 에이딘로보틱스 46.7점입니다. Figure의 33.3점은 투자 점수가 아닌 비교 분석 값입니다.

첨부 PNG는 LangSmith API에 저장된 실제 실행 기록을 렌더링한 자료입니다. LangSmith 웹 UI를 촬영한 이미지가 아닙니다. 웹 화면 캡처를 위한 Chrome 자동화는 macOS 권한에서 거부되었습니다. 따라서 과제 안내의 웹 화면 캡처는 위 LangSmith 링크를 열어 별도로 확보해야 합니다. 긴 실행은 순서에 따라 `tracing-1.png`, `tracing-2.png`와 같이 저장하면 됩니다.

제출 전에는 실제 팀원별 추가 수행 역할을 확인하고, 반별 안내에 맞춰 `Agent_{캠퍼스}_{X반}_{이름1+이름2+...}.zip`으로 묶어야 합니다. Slack 제출은 이 작업에 포함하지 않았습니다.

## 20점 고정 결과의 수정

기존 채점기는 에이전트가 반환한 qualified_count, cagr_percent, unique_priority_families 등의 필드를 읽지 못했습니다. 개별 투자 라운드와 이전·최근 고용 인원을 채점용 값으로 계산하는 처리도 빠져 있었습니다. 따라서 실제 값이 있어도 기본 1점으로 처리되었고 두 후보 모두 20점이 나왔습니다.

이 계약 불일치를 수정한 후 같은 저장 근거와 실제 RAG·LLM으로 다시 실행했습니다. 에이로봇은 T1 3점, P1 4점, R1 3점, R3 4점, M1 3점이며, 에이딘로보틱스는 M1이 4점입니다. 기존 가중치를 적용한 총점은 각각 42점과 44점입니다. 점수 기준이나 원천 수치를 올려서 결과를 변경하지 않았습니다. 이 값은 저장 근거를 적용한 계산 결과이며 외부 원천의 최신성을 새로 검증했다는 뜻은 아닙니다.

검색에서 확보한 정성적 기술 설명은 AnalysisResult.findings에 보존하여 보고서에 전달했습니다. 논문 DOI·시험 분모·독립 현장 확인이 없어 정량 점수를 낼 수 없는 상황과, 제품·기술 설명 자체가 없는 상황을 구분했습니다. 후보별 기술 설명 2개가 실제 보고서에 표시되는 것을 확인했습니다.

## 200페이지 확장 이후의 변화

논문 원문에서 에이딘 소속 저자·DOI·발행일을 확인하여 K1 논문 1편을 인정했습니다. 이에 따라 기존 기준 점수는 44점에서 45.3점으로 바뀌었습니다. 에이로봇은 공개 사양과 시연을 새로 반영했지만 원래 논문·성공률·제조 실증의 요건을 충족하지 않아 기존 기준은 42점을 유지했습니다.

초기 단계 비교에서는 공개 정량 사양과 공개 실물 시연을 에이로봇의 K1·K3에서 각 2/5점으로 인정했습니다. 에이딘의 실물 센서 시험은 K2에서 2/5점으로 인정했습니다. 비교 점수는 각각 44.7점과 46.7점이며 투자 판정은 변경하지 않았습니다.

Figure는 G1 미통과 상태를 유지하며 benchmark_score에 33.3점을 기록했습니다. BMW 고객 확인을 기반으로 완료 제조 현장 1개와 수행 작업군 1개를 확인했습니다. 지표·출처·조회 완결성을 별도로 검증하여 LLM의 부분 검색을 전체 조회로 간주하지 않았고, 고객 확인 기록을 조회 완결성 설명 때문에 자체 주장으로 낮추지 않도록 수정했습니다.

원문별 추가 정보와 인정 범위는 [문서 확장 기록](corpus_expansion.md), 세 가지 검색 점검은 [조회 결과](evidence/expanded-retrieval-check.json)에 있습니다.

## 평가표 기준 재점검

최신 코드 기준으로 품질 재작성과 작업 실패 복구 시나리오를 다시 실행했습니다. 별도 체크아웃에서 원문 다운로드·테스트·API 없이 보고서 생성도 재현했습니다. 일곱 평가 항목의 근거와 제출 보완 사항은 [평가표 점검](rubric_audit.md)에 정리했습니다.
