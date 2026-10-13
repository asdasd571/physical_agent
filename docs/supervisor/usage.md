# 실행·검증·제출 안내

[프로젝트 개요](../../README.md)

## 최종 보고서와 트레이싱


울산캠퍼스 팀은 조승현·김도현·김진형·박세진·김낙근입니다. 최신 제출 자료는 [submission 폴더](submission/)에서 받을 수 있습니다.

| 자료 | 파일과 구성 |
|---|---|
| PDF 보고서 | [Agent_울산캠퍼스_조승현,김도현,김진형,박세진,김낙근.pdf](submission/Agent_울산캠퍼스_조승현,김도현,김진형,박세진,김낙근.pdf) — Pretendard Regular/Bold를 포함한 9페이지 문서입니다. |
| 편집 가능한 Word 보고서 | [같은 내용의 DOCX](submission/Agent_울산캠퍼스_조승현,김도현,김진형,박세진,김낙근.docx) — 텍스트와 표를 편집할 수 있으며 Pretendard 글꼴을 포함합니다. |
| 실제 LangSmith 웹 캡처 | [원본 PNG 4장](evidence/ui-captures/) — 운영 트레이스, Tech 재조사, 품질 실패, 재작성 후 통과 화면입니다. |
| 제출 ZIP | [Agent_울산캠퍼스_조승현,김도현,김진형,박세진,김낙근.zip](submission/Agent_울산캠퍼스_조승현,김도현,김진형,박세진,김낙근.zip) — PDF 1개와 `tracing/`의 PNG 4개입니다. |

사진은 보고서 PDF·DOCX와 별도 파일로 제출합니다. PDF 안에는 트레이싱 부록이나 사진 첨부파일이 없으며, 제출 ZIP에는 안내 TXT와 GitHub 링크 TXT를 넣지 않았습니다. DOCX는 편집용으로 별도 제공하며 제출 ZIP에는 포함하지 않습니다.

웹 캡처는 새 워크스페이스의 운영 재실행과 통제된 품질 재작성 검증입니다. 본문의 기존 운영 기록과 구분합니다. 첫 품질 평가의 `passed=false / revision=0`, 보고서 수정 루프, 두 번째 평가의 `passed=true / revision=1`을 확인할 수 있습니다. 기존 `evidence/live/` 등의 `tracing-*.png`는 API 기록 렌더링 자료이며, 실제 웹 캡처는 `evidence/ui-captures/`에 있습니다. 실행 링크와 화면별 설명은 [LangSmith 캡처 안내](langsmith_capture.md)에 정리했습니다.

2026-10-13 검증 기록은 전체 테스트 223개 통과, 담당자 호출 22회·재작업 7회입니다. 기존 투자 기준 결과는 에이로봇 HOLD 42.0점, 에이딘로보틱스 HOLD 45.3점, Figure AI HOLD 비교 33.3점입니다. 초기 단계 비교 점수 44.7·46.7·33.3은 투자 판정에 사용하지 않습니다. 자세한 실행 근거는 [검증 기록](validation.md)에서 확인할 수 있습니다.

저장된 평가 결과로 사진 없는 Pretendard PDF를 다시 만들려면 다음 명령을 실행합니다. RAG·LLM을 다시 호출하지 않고 기존 평가 값과 출처를 사용합니다.

```bash
python -m scripts.build_submission_report docs/supervisor/evidence/live \
  --tests docs/supervisor/evidence/pytest.xml \
  --font-directory reporting/fonts
```

생성 경로는 `docs/supervisor/evidence/evaluation_report.pdf`입니다. 최종 제출 파일명으로 저장한 자료는 `docs/supervisor/submission/`에서 관리합니다.

## 설치


Python 3.11 이상과 Git이 필요합니다. 아래 명령은 저장소 루트에서 실행합니다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

`.env`에 `OPENAI_API_KEY`를 설정합니다. LangSmith를 사용하려면 `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `LANGSMITH_PROJECT=physical-agent-supervisor`를 설정합니다. `.env`는 Git에서 제외되며 코드와 문서에 키를 기록하지 않습니다.

### API 없이 전체 흐름 확인

```bash
python app.py --skip-rag --skip-llm --run-id offline-check --evaluation-date 2026-10-13
```

저장된 기업·시장·특허 자료를 사용하여 그래프, 재조사, 보고서 생성과 품질 평가를 실행합니다. 이 실행은 실제 LLM·검색 성능 검증을 대신하지 않습니다. LangSmith가 설정되어 있으면 이 실행도 추적되며, 메타데이터에 오프라인 모드가 표시됩니다.

### RAG와 LLM을 포함한 실행

```bash
python -m scripts.prepare_corpus --manifest data/rag/manifest.expanded.csv
python -m rag.cli index --manifest data/rag/manifest.expanded.csv --index-dir data/rag/index-expanded
python app.py --run-id supervisor-live --evaluation-date 2026-10-13
```

원문은 manifest의 SHA256으로 확인합니다. 웹페이지에서 저장한 PDF는 재다운로드로 동일한 파일을 만들 수 없으므로 누락 시 원본 파일을 복원해야 합니다. `--available-only`는 확인된 자료만 별도 manifest에 기록하는 부분 검증 옵션입니다. 부분 자료로 실행한 결과는 전체 자료 검증으로 표기하지 않습니다.

같은 실행 ID로 결과를 덮어쓰지 않습니다. 새 실행에는 새 ID를 지정합니다. 중단한 실행은 다음과 같이 재개합니다.

```bash
python app.py --resume --run-id supervisor-live
```

적격성 탈락 후보의 분석을 기존처럼 생략하려면 `--eligibility-mode strict`를 지정합니다. 기본값은 `stage-benchmark`입니다.

재개 시 RAG·LLM 사용 여부와 적격성 모드는 원래 실행과 같아야 합니다. 저장된 State와 다음 노드를 SQLite에서 복원합니다. 완료한 실행을 재개하면 기존 결과를 반환합니다.

## 생성 파일


| 파일 | 내용 |
|---|---|
| `artifacts/<run-id>/report.r0.pdf` | 최초 보고서입니다. SUMMARY, 네 관점, REFERENCE를 포함합니다. |
| `report.r1.pdf`, `report.r2.pdf` | 품질 미달 시 생성한 수정본입니다. 수정하지 않으면 생성되지 않습니다. |
| `report.rN.json` | 해당 PDF의 구조화된 본문, 원값, 출처와 PDF 해시입니다. |
| `quality.json` | 회차별 품질 평가와 최종 통과 여부입니다. |
| `run.json` | 실행·추적 ID, 후보별 라우팅 사유와 종료 결과입니다. |
| `events.jsonl` | 실제 노드 실행 순서와 Supervisor 판단 기록입니다. |
| `checkpoints.sqlite` | 중단 후 재개하기 위한 State입니다. |

품질 평가 통과 시 종료 코드는 0입니다. 수정 한도 이후에도 미달이면 `quality_failed`와 종료 코드 2를 반환합니다. 이 경우 생성된 PDF는 검토용 결과이며 통과한 보고서로 제출하지 않습니다.

## 200페이지 문서와 초기 단계 비교


확장 manifest는 17개 문서, 사용 페이지 200페이지입니다. 기존 161페이지에 에이딘 소속 저자의 센서 논문 18페이지, BMW 고객 확인 자료 7페이지, 에이딘의 정량 사양 자료 14페이지를 추가했습니다. 원문 파일과 SHA256을 함께 관리합니다.

보고서에는 기존 투자 기준 점수와 `early-stage-v2` 비교 점수를 함께 표시합니다. 초기 단계 기준은 K1의 공개 정량 사양, K2의 조건이 명시된 실물 센서 시험, K3의 최근 공개 시연 기록을 각 항목 최대 2/5점으로 인정합니다. 제품 사양을 논문 수로, 센서 오차를 조작 성공률로, 전시 시연을 제조 현장 실증으로 바꾸지 않습니다. 이 비교 점수는 투자 판정에 사용하지 않습니다.

출처별 추가 근거와 수집 한계는 [문서 확장 기록](corpus_expansion.md)에 정리했습니다.

## 보고서 품질 기준


과제 안내의 **1안인 규칙 기반 평가**를 사용합니다. 출처의 존재와 연결성, 제한된 추천 표현, 발행기관 다양성, 불리한 근거와 미확인 항목의 표시, 후보별 네 관점의 포함 여부를 검사합니다. 파일의 무결성과 10페이지 상한도 검사합니다.

이 검사는 모든 문장의 의미가 원문으로 입증되는지 판정하는 LLM Judge가 아닙니다. 의미상 환각과 간접적인 편향은 사람이 추가로 검토해야 합니다. 초기 해설의 품질이 미달하면 검증된 원값과 인용을 중심으로 재작성합니다. 발행기관 부족처럼 재작성으로 해소되지 않는 문제는 계속 미달로 남습니다.

기존 투자 Judge는 점수와 Gate를 계산합니다. 이번 보고서의 중립성은 기술 우열을 단정하거나 기술을 추천하지 않는 것을 뜻합니다. 기존 HOLD/INVEST는 정해진 규칙의 계산 결과로 표시하며, 기술 우열과 구분합니다.

## 코드 구성


| 위치 | 책임 |
|---|---|
| `graph/supervisor.py` | Supervisor 그래프, 보수적 판정, 후보 결과 저장을 담당합니다. |
| `nodes/supervisor.py` | State를 읽고 다음 담당자와 재작업 사유를 결정합니다. |
| `agents/supervised.py` | 담당자별 입력을 제한하고 출력 계약과 실패를 처리합니다. |
| `schemas/supervisor.py` | 제어 상태, 할당 요청, 보고서, 품질 평가 모델을 정의합니다. |
| `graph/checkpoints.py` | SQLite 저장과 허용된 타입의 복원을 담당합니다. |
| `nodes/report_quality.py` | 보고서 생성 이후 품질 평가와 재작성 분기를 담당합니다. |
| `reporting/supervisor_report.py` | 네 관점의 PDF·JSON을 생성합니다. |
| `scripts/build_submission_report.py`, `reporting/fonts/` | 저장된 평가 결과를 제출 보고서로 구성하고 Pretendard 글꼴을 적용합니다. |
| `docs/supervisor/submission/`, `docs/supervisor/evidence/ui-captures/` | 최종 PDF·DOCX·ZIP과 별도 웹 트레이싱 사진을 보관합니다. |
| `agents/`, `rag/`, `nodes/judge.py` | 기존 담당 에이전트, 검색기와 투자 규칙을 재사용합니다. |

담당자의 원값은 Judge에서 명시적으로 정규화하며, 실제 채점에 사용한 값은 JSON의 `scoring_values`에 저장합니다. 기술 설명은 정량 지표와 별도로 출처와 함께 보고서에 표시합니다.

설계 근거와 요구사항별 구현 위치는 [설계 문서](design.md)에 정리했습니다. 실제 검증 결과와 제출 자료는 [검증 기록](validation.md)에 기록합니다. 일곱 평가 항목을 대조한 결과는 [평가표 점검](rubric_audit.md)에 정리했습니다.

## 테스트


```bash
python -m scripts.prepare_corpus --manifest data/rag/manifest.expanded.csv
LANGSMITH_TRACING=false python -m pytest -q
```

신규 테스트는 근거에 따른 라우팅 변경, 특정 담당자 재조사, 통신 제약, 작업 실패 복구, 재시도 상한, 보고서 평가 루프, 지속적인 품질 미달, 파일 변조와 SQLite 재개를 확인합니다. 기존 테스트도 함께 실행합니다.

