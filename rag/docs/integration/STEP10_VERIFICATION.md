# STEP 10 Agent 연동 확인 방법

STEP 10은 RAG가 다른 팀원의 Agent에 검색 결과만 제공한다는 공통 계약을 확인한다. GraphState, Agent 출력 Schema와 투자 판단 로직은 변경하지 않는다.

## 연동 흐름

```text
저장된 Dense·BM25 index
→ HybridRetriever 복원
→ configure_search_backend()
→ Agent의 search_documents() 호출
→ list[RetrievedChunk]
```

## 1. 자동 통합 테스트

```bash
.venv/bin/python -m pytest tests/rag/test_agent_integration.py -q
.venv/bin/python -m pytest -q
```

확인할 내용:

- 다른 Agent가 `from rag import search_documents`로 호출 가능한지
- 설계에서 정한 `query`, `candidate_id`, `doc_types`, `top_k` 인자를 그대로 받는지
- 저장·복원된 Hybrid index가 공개 API에 연결되는지
- `company_a`, `tech` 필터가 다른 후보와 공통 market 문서를 제외하는지
- 반환값이 `list[RetrievedChunk]`인지
- 각 결과에 `chunk_id`, `source_id`, `doc_id`, `page`, `content`, `score`가 있는지

## 2. 실제 BGE-M3 index로 실행

STEP 8에서 생성한 실제 index를 사용한다.

```bash
.venv/bin/python -m scripts.verify_step10_agent_call \
  "What is the highest priority of SK Innovation and its subsidiaries for workplace operations?" \
  --index-dir data/rag/index/step8_ski \
  --doc-type parent \
  --top-k 5 \
  --device mps
```

예상 결과:

- JSON 배열 반환
- 첫 번째 결과의 `doc_id`가 `ski_esg_report_2022`
- 첫 번째 결과의 `page`가 `102`
- `metadata.retrieval.fusion`이 `rrf`

## 다른 Agent에서 사용하는 코드

애플리케이션 시작 시 한 번만 backend를 등록한 뒤 각 Agent는 공개 검색 함수만 호출한다.

```python
from rag import search_documents

results = search_documents(
    query="이 회사의 로봇핸드 실물 조작 성공률은?",
    candidate_id="company_a",
    doc_types=["tech"],
    top_k=5,
)
```

RAG 결과를 이용해 투자 지표를 판정하거나 점수를 계산하는 일은 각 Agent의 책임이다.
