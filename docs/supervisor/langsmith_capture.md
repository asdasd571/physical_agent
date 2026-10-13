# LangSmith 실제 웹 화면 캡처 안내

이 안내는 기존 실행을 LangSmith 웹에서 열어 촬영하는 방법입니다. 저장된 `tracing-*.png`는 API 기록을 렌더링한 이미지이며 웹 화면 캡처가 아닙니다. 실제 웹 캡처는 `docs/supervisor/evidence/ui-captures/`에 별도로 저장합니다.

## 1. 프로젝트와 실행 열기

LangSmith에 로그인하고 API 키가 속한 워크스페이스를 선택합니다. 프로젝트 이름은 `physical-agent-supervisor`입니다. 다음 링크로 기록된 실행을 바로 열 수 있습니다.

| 실행 | 링크 | 확인할 내용 |
|---|---|---|
| 실제 RAG·LLM 운영 실행 | [physical-agent-supervisor](https://smith.langchain.com/o/e4414c93-2ee4-4f39-9fa6-0a03aaddc4c3/projects/p/ef520cd3-1898-45ff-bc9f-19afd6b901ff/r/de10b31f-89c7-46a1-84c4-7632ee41515a) | Supervisor 동적 라우팅과 부족 근거 재조사입니다. |
| 품질 재작성 검증 | [controlled-quality-repair](https://smith.langchain.com/o/e4414c93-2ee4-4f39-9fa6-0a03aaddc4c3/projects/p/ef520cd3-1898-45ff-bc9f-19afd6b901ff/r/70274d27-8262-4962-b8e2-1559ad8bc89f) | 품질 미달 뒤 보고서 재작성과 재평가입니다. |
| 작업 실패 복구 검증 | [controlled-worker-retry](https://smith.langchain.com/o/e4414c93-2ee4-4f39-9fa6-0a03aaddc4c3/projects/p/ef520cd3-1898-45ff-bc9f-19afd6b901ff/r/033d5cf0-c705-49fb-8404-419eea1cacdc) | 최초 Tech TimeoutError 이후 재호출과 복구입니다. |

접근 오류가 발생하면 로그인 계정과 워크스페이스의 프로젝트 접근 권한을 확인합니다. 직접 링크가 열리지 않으면 프로젝트의 Traces 또는 Runs 목록에서 위 실행 이름을 선택합니다.

## 2. 동적 라우팅과 재조사 캡처

1. 운영 실행을 열고 **Details** 화면에서 하위 노드 트리를 펼칩니다. 노드 옆 화살표로 접힌 항목을 펼칩니다.
2. 실행 이름과 완료 상태, `supervisor`와 담당 Agent의 반복 호출이 함께 보이도록 촬영합니다. 긴 트리는 위에서 아래로 일부 내용이 겹치도록 나누어 촬영합니다.
3. 재조사 직전 `supervisor` 노드를 선택하고 Output/Outputs를 확인합니다. `supervisor.next_node`, `supervisor.assignment.reason`, `supervisor.assignment.indicator_ids`, `supervisor.assignment.repair=true`가 확인되는 구간을 촬영합니다. 모든 Supervisor 호출이 재조사는 아니므로 해당 출력에서 `repair=true`인지 확인합니다.
4. `live/tracing-1.png`, `live/tracing-2.png`와 같이 순서대로 저장합니다.

운영 기록은 담당 Agent 호출 22회와 재작업 7회입니다. 근거 조사 재작업은 해당 Agent를 다시 호출하므로 트리에 별도 `repair` 노드가 나타나는 것을 요구하지 않습니다.

## 3. 품질 미달과 보고서 수정 루프 캡처

1. `controlled-quality-repair` 실행을 열고 트리의 마지막 구간을 펼칩니다.
2. `report → quality → revise_report → report → quality → finalize` 순서가 보이는 화면을 촬영합니다.
3. 첫 `quality`를 선택하고 출력의 `quality.passed=false`와 `quality.revision=0`, 실패 사유를 촬영합니다.
4. 두 번째 `quality`를 선택하고 `quality.passed=true`와 `quality.revision=1`을 촬영합니다.
5. `quality-repair/tracing-1.png`부터 순서대로 저장합니다.

이 실행은 품질 결함을 의도적으로 주입한 검증 시나리오입니다. 실제 RAG·LLM 운영 실행은 최초 품질 평가에서 통과했으며, 운영 실행에서 품질 실패 루프가 발생했다는 의미가 아닙니다.

## 4. macOS에서 저장

`⌘ + ⇧ + 4`를 누르고 필요한 화면 영역을 드래그하면 PNG로 저장됩니다. `⌘ + ⇧ + 5`에서도 영역을 선택할 수 있습니다. 프로젝트·실행 이름, 노드 순서와 판정값이 읽히도록 영역을 잡습니다. 캡처 파일의 실제 저장 위치는 macOS 캡처 옵션에서 확인합니다.

캡처를 다음과 같이 배치합니다.

```text
docs/supervisor/evidence/ui-captures/
├── live/
│   ├── tracing-1.png
│   └── tracing-2.png
└── quality-repair/
    ├── tracing-1.png
    ├── tracing-2.png
    └── tracing-3.png
```

필요한 장수는 화면 길이에 따라 늘릴 수 있습니다. 위 경로는 권장 저장 구조이며 현재 웹 캡처가 확보되었다는 뜻은 아닙니다. 캡처 확보 후 제출 묶음과 점검 문서의 남은 항목을 갱신합니다.

화면의 Details와 실행 입출력 확인 방식은 [LangSmith 공식 View traces 안내](https://docs.langchain.com/langsmith/view-traces)를 기준으로 합니다.
