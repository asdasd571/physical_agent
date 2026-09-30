# Agent에서 RAG 사용하기

## 1. 애플리케이션 시작 시 한 번 설정

인덱스가 없다면 먼저 생성한다.

```bash
.venv/bin/python -m rag.cli index \
  --manifest data/rag/manifest.csv \
  --index-dir data/rag/index/investment \
  --device mps
```

애플리케이션 시작 시 저장된 인덱스를 한 번 로드한다.

```python
from rag import (
    BgeM3Embedder,
    KiwiTechnicalTokenizer,
    configure_search_backend,
    load_hybrid_retriever,
)

retriever = load_hybrid_retriever(
    "data/rag/index/investment",
    embedder=BgeM3Embedder(device="mps"),
    sparse_tokenizer=KiwiTechnicalTokenizer(),
)
configure_search_backend(retriever)
```

CPU 서버에서는 `device="cpu"`를 사용한다.

## 2. Agent Node에서 검색

```python
from rag import search_documents

results = search_documents(
    query="BMW 현장 실증에서 Figure 로봇의 가동 시간과 처리량",
    candidate_id="figure_ai",
    doc_types=["tech"],
    top_k=5,
)
```

Agent별 권장 유형:

| Agent | `doc_types` | 용도 |
| --- | --- | --- |
| Tech | `["tech"]` | 제품 사양, 기술 구조, 현장 실증 |
| Market | `["market"]` | 국내외 시장 규모와 성장률 |
| Competitor | `["tech"]` | 공식 경쟁 제품 사양 비교 |
| Discover/Risk | `["risk"]` | 투자 실사와 AI 위험 기준 |

`candidate_id`를 지정하면 해당 후보 문서와 `COMMON` 공통 문서만 검색된다.

## 3. 결과에서 반드시 사용할 값

```python
for item in results:
    print(item.content)       # Agent가 읽을 근거 본문
    print(item.source_id)     # State.sources 연결 키
    print(item.doc_id)
    print(item.page)          # 원문 PDF 페이지
    print(item.score)         # RRF 검색 점수
```

최종 분석 결과에는 `source_id`를 남기고, `GraphState.sources`에는 대응하는 `SourceRecord`를 저장한다. `sources` reducer가 여러 Agent의 출처를 `source_id` 기준으로 합친다.

주의사항:

- `score`는 사실의 신뢰 확률이 아니라 검색 순위 결합 점수다.
- 기업 공식 자료의 주장은 독립 검증 사실과 구분한다.
- 수치·단위·기간은 `doc_id`와 `page`로 원문을 확인한다.
- backend를 등록하지 않으면 `SearchBackendNotConfiguredError`가 발생한다.
