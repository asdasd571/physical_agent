# 김진형 담당 모듈 실행 및 통합 안내

설계 PDF(2026-09-30, 20쪽)의 기술·시너지·보고서 영역을 구현했다.
공통 `schemas/`, `rag/`, 다른 담당자의 Agent, 루트 의존성 파일은 수정하지 않았다.
개발 브랜치는 `feature/tech-synergy-report`이며, main의 Graph·review·judge·archive와 통합 검증했다.

## 설치와 실행

저장소 루트에서 Python 3.11 이상으로 실행한다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt -r reporting/requirements.txt
python -m pytest -q
python -m reporting.demo --output /tmp/physical-agent-demo.pdf
```

`python3.11`이 없다면 Python 3.11 이상의 실행 파일로 바꾼다.
`uv` 사용 시 `uv venv --python 3.11 .venv`로 환경을 만들 수 있다.
동일한 PDF/JSON 경로가 있으면 덮어쓰지 않고 오류를 반환한다. 재실행할 때 출력 이름을 바꾼다.
데모에는 **가상 데이터** 표시가 있으며, 실제 기업을 평가한 제출용 보고서가 아니다.
PDF 옆 JSON에는 입력 원값·점수·판정과 실제 인용한 출처가 보존된다.
임시 산출물은 `/tmp`에 두며 Git에 추가하지 않는다.

추가 패키지는 `reporting/requirements.txt`에만 정의했다. 통합 담당자는
Jinja2와 PyMuPDF를 공통 설치 절차에 반영하면 된다. PyMuPDF의 내장 한글 지원 글꼴을 PDF에
포함하며 사용자의 시스템 글꼴 파일을 저장소에 복사하지 않는다.

## Node 연결

```python
from agents.tech import make_tech_node, make_llm_extractor
from agents.synergy import make_synergy_node
from agents.report import report_node

# 팀에서 설정한 LLM 인스턴스: invoke(messages)를 지원해야 한다.
extractor = make_llm_extractor(configured_chat_model)
graph.add_node("tech", make_tech_node(extractor=extractor))
graph.add_node("synergy", make_synergy_node(extractor=extractor))
graph.add_node("report", report_node)
```

`configured_chat_model`과 `graph`는 통합 애플리케이션에서 생성하는 객체다.
모델·키·요금제는 이 모듈에서 임의로 지정하지 않는다. 공통 RAG backend는 먼저
`rag.configure_search_backend(...)`로 등록한다.

LLM을 쓰지 않는 수동 근거 경로도 지원한다:

```python
from agents.tech import tech_node
from agents.synergy import synergy_node

tech_update = tech_node(state)
# 실제 Graph에서는 공통 sources reducer로 병합한다.
synergy_update = synergy_node(state)
```

기본 Node는 담당 evidence 폴더의 JSON을 읽고 공통 RAG를 호출한다.
자연어 RAG 결과를 원값으로 바꾸려면 `extractor`가 필요하다. 설정하지 않으면
자연어에서 수치를 임의로 추정하지 않는다. `query_attempts.note`에 추출기 설정 여부를 기록한다.
RAG backend가 없으면 `ACCESS_FAILED`, 정상 검색이 비었으면 `NO_DATA`로 남긴다.
오류 난 추출기, 깨진 JSON, 미등록 출처, 충돌 금액은 실행 오류로 전달한다.

테스트와 다른 추출기 사용을 위한 인자:

```python
node = make_tech_node(
    search=search_documents,       # 공통 RAG와 같은 keyword 인자
    extractor=my_extractor,       # (prompt, documents, Candidate) -> evidence bundle dict
    evidence_dir="data/evidence/tech",
)
node = make_synergy_node(
    extractor=my_extractor,
    evidence_dir="data/evidence/tech",
    parent_dir="data/evidence/parent",
)
```

추출기에 전달되는 문서는 `source_id`, `doc_type`, `page`, `content`를 갖는다.
반환 스키마는 `prompts/tech.md`, `prompts/synergy.md`에 정의했다.
추출기는 받은 문서 이외의 출처를 만들 수 없다. 독립 검증 여부 등 의미상의 판단은
후속 `review`가 원문과 다시 대조해야 한다. 프롬프트만으로 사실 검증이 완료되지는 않는다.

## 수동 원문·조회 기록

JSON 최상위 형식:

```json
{
  "candidate_id": "확정 후보의 candidate_id",
  "sources": [],
  "records": [],
  "coverage": []
}
```

`sources`는 공통 `SourceRecord`의 JSON 표현이다. `records`의 `source_ids`는
이 배열 또는 기존 State에 존재해야 하며, 원문 발췌 `evidence_excerpt`가 필수다.
PDF는 경로·SHA256·문서 ID·원문 페이지가 필요하다. 발행일이 평가일 이후인 자료는 제외한다.
공통 모기업 문서만 `candidate_id="COMMON"`을 허용하며, COMMON에 후보 기술·인증을 넣으면 오류다.
실제 후보 ID가 일치하지 않는 파일은 사용하지 않는다.

로컬 JSON은 담당자가 원문을 확인한 입력이다. 단순히 `independent_verified=true`를 작성했다고
원문의 주장이 자동으로 검증되는 것은 아니다. 시험의 독립 재현과 논문의 존재 확인은 구분한다.

0건은 조회 범위를 모두 확인한 기록이 있을 때만 다음 coverage로 입력한다.
검색 상위 5개에 결과가 없다는 사실은 완전 조회가 아니다.

```json
{
  "indicator_id": "K1",
  "complete": true,
  "query_status": "SUCCESS",
  "independent_verified": true,
  "source_ids": ["실제_전체_조회기록_source_id"]
}
```

## 원값 계약

| 지표 | raw_value | 처리 |
|---|---|---|
| T2 | paper_count, founder_count, papers_per_founder(Decimal), dois | 설립 전 5년, DOI 중복 제거, 창업자 식별 필요 |
| K1 | DOI 수(정수) | 설립 후·최근 5년·기업 소속, 설립 전 DOI 제외 |
| K2 | successful_trials, total_trials, success_rate_percent | 유효한 30회 이상 실물 시험; 조건과 제외 관측값 보존 |
| K3 | 현장 수(정수) | 최근 3년, 고객·운영기관 독립 확인, 완료 제조 현장 고유 ID |
| R2 | amount_krw, amount_100m_krw, amount_krw_100m(채점용 Decimal), projects | 평가연도 포함 3개 달력연도, 현재 연도는 평가일까지; 기업 귀속분만 |
| S1 | performed_task_count, task_count(동일 건수), task_ids | 고객·정부·운영기관 독립 수행 작업군 |
| S2 | matched_task_count, matches | S1과 모기업 공개 PDF 페이지 양쪽 연결 |
| F4 | checks, explosive_area, certified_or_in_progress | 공정·모델별 최신 인증 조회 상태, Gate 계산은 하지 않음 |

서로 다른 시험을 합산하거나 최고 성공률을 선택하지 않는다. 동일 조건은 최신 자료를 쓰고
모기업 관련 작업을 우선한다. 독립 재현 없는 시험은 자체 발표로 반환한다.
K2 채택 조건 미달은 `raw_value=None`, 원관측값은 `condition.observations`에 남는다.
금액·비율은 Decimal로 계산하고 최종 성공률만 두 자리로 표시한다. Agent가 점수를 만들지는 않는다.
연구비의 외화 환산은 수행하지 않는다. 환산이 필요하면 환율과 원화 귀속액 근거를 별도로 확보해야 한다.
공개 자료에서 확인한 양수의 합계·건수는 확보한 자료의 범위이며, 완전성은 review에서 확인해야 한다.

F4 확인 상태는 `UNKNOWN`, `NOT_APPLICABLE`, `CERTIFIED`, `IN_PROGRESS`,
`NO_VALID_EVIDENCE`다. 조회 실패/구역 미확인을 인증 없음으로 바꾸지 않는다.
`NO_VALID_EVIDENCE`는 방폭 구역 확인, 정상 완전 조회, 진행 자료 확인까지 끝났을 때만 기록한다.
인증서가 있으나 범위 또는 유효기간을 확인하지 못했다면 `UNKNOWN`으로 남긴다.
같은 날짜·조건에서 성공/시도 횟수가 충돌하면 임의 선택 없이 오류로 중단한다.
시험·논문·실증·수행·인증의 날짜 누락은 채택 대상에서 제외하고 미확인 상태로 처리한다.

## 검색 한도와 repair

지표별 초기 RAG 검색 최대 2회(최초 + 결과 부족 시 질의 재작성), repair 최대 1회를 사용한다.
동일 후보 분석이 State에 있으면 재호출은 이를 재사용한다. 새 실행은 분석 필드를 초기화해야 한다.
후보가 바뀌거나 평가일이 달라지면 이전 분석을 재사용하지 않는다.

repair는 현재 후보의 `evidence_review.repair_required`와 담당 `repair_targets`로 식별한다.
공통 repair Node는 `retry_count=0`에서 담당 handler를 호출한 뒤 1로 증가시킨다.
이전 분석 객체를 이용해 지정된 담당·지표만 재검색하고 다른 지표는 보존한다.
보완된 분석 객체 전체를 반환하므로 중첩 dict reducer가 필요하지 않다.
공통 sources reducer에는 `update["sources"]`만 추가한다. State 전체를 `dict.update`해서
sources를 덮어쓰면 기존 근거가 사라질 수 있다.

웹·OpenAlex·NTIS 자동 수집 도구는 현재 저장소에 없어 여기서 별도 구현하지 않았다.
그 결과는 담당자가 원문·조회 기록을 JSON으로 입력하거나 팀의 공통 도구에서 같은 계약으로 전달한다.

## 보고서 archive 계약

보고서는 검색이나 LLM 호출 없이 확정 EvaluationRecord만 사용한다.
현재 공통 스키마에 검증 완료 필드가 없으므로 두 archive 계약을 지원한다.
명시적 완료 표시를 사용하는 호출자는 실제 review와 judge가 끝난 후 다음을 저장한다.

```python
metadata = {
    "review_completed": True,
    "scoring_completed": True,
}
```

두 표시 중 하나라도 제공하면 둘 다 true여야 한다. 완료 표시가 없는 main의 judge/archive는
`missing_indicator_count`와 `missing_indicator_ids`를 사용하며, 원지표의 결측 상태와 정확히
일치하는지 확인한다. 이는 저장 형식 검증이며 원문 검증의 증거를 대신하지 않는다.
호출자는 실제 review → judge → archive를 거친 평가만 전달해야 한다.
현재 후보의 `state["evidence_review"]` 하나로
이전 후보까지 검증되었다고 간주하지 않는다. G1 미통과로 생략된 후보는
`G1.passed=False`, `total_score=None`, `decision.status=HOLD`이면 보고할 수 있다.
원본 점수·판정은 재계산하거나 수정하지 않는다.
채점된 후보는 12개 원지표·지표 점수와 6개 항목 평균이 모두 있어야 한다.
범위를 벗어난 점수, NaN, Gate 미통과/70점 미만과 충돌하는 INVEST는 출력하지 않는다.
`metadata.synthetic=True`인 가상 평가에는 호출 옵션과 무관하게 테스트 표시를 붙인다.

사업 개요, 하드웨어·모델 역할, 경쟁 비교 등 서술은 검증된 원문이 있을 때만 선택적으로 저장한다:

```python
metadata["narratives"] = [{
    "section": "technology",  # business / technology / market / risk
    "text": "원문과 대조한 기술 설명",
    "source_ids": ["등록된_source_id"],
}]
```

출처 없는 서술은 거부한다. 미제공 수익모델·기업가치·시장 규모는 생성하지 않는다.
보고서 경로는 `run.settings["report_output_path"]`로 지정할 수 있다.
기본값은 `reporting/output/investment_report_평가일.pdf`다. 제출 시 교수님 안내의
`RAG-Output_캠퍼스-X반_이름1+이름2+....pdf` 형식으로 지정한다.

보고서는 항상 5쪽이며 SUMMARY는 첫 장 위쪽 반 페이지 안에 독립 배치한다.
글자 크기를 10/9/8pt 순으로 조정해 배치하고 그래도 넘치면 `ReportLayoutError`로 중단한다.
자동 잘림·조용한 후보 삭제·6쪽 이상 출력은 허용하지 않는다.
모든 원값과 전체 조건은 JSON에 보존하고, PDF에는 판단에 필요한 원값·시험 조건·인용을 정리한다.
투자 라운드·특허·인력의 중첩 기록은 저장된 원값을 요약 표시하며 재계산하지 않는다.
REFERENCE는 두 열로 배치하고 전체 인용 출처의 제목·URL·페이지를 보존한다.

## 검증 및 남은 통합

테스트는 DOI·설립 경계, 분모 오류, 다른 시험 조건, 자체 발표, 현장/과제 중복,
S2 양쪽 근거, F4 조회 상태, 후보 분리, repair 한도, 출처 위조, 전체 보류,
3개 후보/12개 지표 PDF, 한글 글꼴 포함, 인용, 페이지 초과와 기존 파일 보존을 확인한다.
추가 검토에서는 날짜 누락, 인증 정보 불완전, 추출기의 원문 유형 바꿔치기,
점수 누락·판정 모순, 시험 수치 충돌을 재현하는 회귀 테스트를 추가했다.

main 통합 기준 전체 테스트 184개가 통과했다. 실제 공통 repair handler, judge/archive와
담당 Node를 연결하는 회귀 테스트도 포함한다. 저장소의 후보 3개와 로컬 evidence를 사용한
전체 Graph 실행에서 5쪽 PDF와 JSON 생성을 확인했다(외부 LLM·RAG backend 없이,
`graph.invoke(..., config={"recursion_limit": 100})` 사용).
실제 RAG 인덱스·외부 LLM 호출 및 원자료 사실 검증은 별도로 필요하다.
이 실행 확인을 실제 투자 타당성 검증이나 최종 제출물 승인으로 간주하지 않는다.

교수님 [과제 안내](https://actually-war-1ea.notion.site/AI-1cf7f4c86693800e9e11fa490ed1a2ff?pvs=143)의
보고서 구조와 재현 요구를 반영했다. 루트 README의 Contributors·실행법·Lessons Learned 통합은
김도현 담당 파일이므로 여기의 내용을 전달해 반영한다.

Lessons Learned: RAG 문서 ID만 출처 키로 쓰면 여러 페이지의 인용이 충돌한다.
문서 해시·페이지·청크를 포함한 ID로 분리했고, PDF 출력에서는 영문 합자로 ID가 바뀌지 않도록
고정폭 글꼴을 사용했다. PDF 페이지 수만 검사해서는 표 잘림을 잡을 수 없어, 배치 가능 여부도 검증한다.
