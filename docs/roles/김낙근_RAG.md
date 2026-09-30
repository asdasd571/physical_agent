# 김낙근 공통 RAG와 검색 도구

## 목표

PDF 문서를 페이지 단위로 적재하고, BGE-M3 Dense 검색과 Kiwi BM25 검색 결과를 RRF로 결합해 다른 Agent가 사용할 Top5 근거를 반환한다. RAG는 근거 검색까지만 담당하고 점수 계산이나 투자 판단은 하지 않는다.

## 담당 브랜치

```text
feature/rag
```

## 담당 폴더 구조

```text
rag/
├── __init__.py
├── config.py
├── models.py
├── manifest.py
├── loader.py
├── chunker.py
├── embeddings.py
├── dense_store.py
├── bm25_store.py
├── fusion.py
├── filters.py
├── retriever.py
├── indexing.py
├── cli.py
├── service.py
└── docs/
    ├── fusion/
    ├── retrieval/
    ├── indexing/
    ├── evaluation/
    └── integration/

data/rag/
├── manifest.csv
├── documents/
│   ├── tech/
│   ├── parent/
│   ├── market/
│   └── risk/
└── index/
    ├── faiss/
    ├── bm25/
    └── metadata/

evaluation/
├── retrieval_eval.py
├── retrieval_questions.json
└── results/

tests/rag/
├── test_manifest.py
├── test_loader.py
├── test_chunker.py
├── test_fusion.py
├── test_retriever.py
└── test_agent_integration.py
```

## `rag/`에 들어갈 파일

### `rag/__init__.py`

외부에서 사용할 공개 객체만 노출한다.

```python
from rag.models import RetrievedChunk
from rag.service import search_documents

__all__ = ["RetrievedChunk", "search_documents"]
```

### `rag/config.py`

검색 설정과 인덱스 경로를 한곳에서 관리한다.

```python
CHUNK_SIZE = 450
CHUNK_OVERLAP = 60
DENSE_TOP_K = 20
BM25_TOP_K = 20
RRF_K = 60
DEFAULT_TOP_K = 5
EMBEDDING_MODEL = "BAAI/bge-m3"
```

API Key나 개인 PC의 절대 경로는 넣지 않는다.

### `rag/models.py`

RAG 내부와 외부 인터페이스가 공유하는 데이터 모델을 둔다.

주요 모델:

- `DocumentType`
- `ManifestEntry`
- `DocumentPage`
- `DocumentChunk`
- `RetrievedChunk`

검색 결과 예시:

```python
RetrievedChunk(
    chunk_id="chunk_7f40c1...",
    source_id="src_42da10...",
    doc_id="figure_robot_hand_report",
    candidate_id="figure_ai",
    doc_type=DocumentType.TECH,
    page=12,
    content="The robot hand completed 28 of 30 trials...",
    score=0.0325,
)
```

`score`는 RRF 순위 융합 점수이며 신뢰도나 확률이 아니다.

### `rag/manifest.py`

`data/rag/manifest.csv`를 읽고 다음을 검사한다.

- 필수 컬럼 존재 여부
- `doc_id`와 원문 중복
- SHA256 형식
- `doc_type` 값
- 기업 문서의 `candidate_id`
- 전체 `used_pages <= 200`

### `rag/loader.py`

PDF를 원문 페이지 단위로 읽는다.

- 원문 SHA256 확인
- 실제 PDF 페이지 수 확인
- `page_ranges`에 지정된 페이지만 추출
- 원문 PDF 페이지 번호 유지
- 빈 페이지는 OCR 필요 오류로 기록

### `rag/chunker.py`

한 페이지 내부에서만 token chunk를 만든다.

```python
def chunk_page(
    page: DocumentPage,
    tokenizer: TokenCodec,
    *,
    chunk_size: int = 450,
    overlap: int = 60,
) -> list[DocumentChunk]:
    ...
```

한 청크가 여러 페이지에 걸치면 안 된다. 긴 표는 제목과 header를 다음 청크에 반복할 수 있도록 metadata를 남긴다.

### `rag/embeddings.py`

BGE-M3 모델의 로딩과 Dense embedding 생성을 담당한다.

```python
class BgeM3Embedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...
```

모델은 검색마다 다시 로드하지 않고 한 번만 로드한다.

### `rag/dense_store.py`

FAISS 인덱스를 생성하고 저장·불러오기 한다.

저장 예시:

```text
data/rag/index/faiss/index.faiss
data/rag/index/faiss/chunk_ids.json
```

Dense 검색은 필터가 적용된 문서 집합에서 상위 20개를 반환한다.

### `rag/bm25_store.py`

Kiwi tokenizer와 BM25 인덱스를 관리한다.

토큰화 예시:

```text
입력: vision-language-action 기반 robot-hand 3-finger 제어
보존 대상: vision-language-action, robot-hand, 3-finger
```

BM25 검색도 필터가 적용된 문서 집합에서 상위 20개를 반환한다.

### `rag/fusion.py`

Dense와 BM25 결과를 동일 가중치 RRF로 결합한다.

```python
rrf_score = 1 / (60 + dense_rank) + 1 / (60 + bm25_rank)
```

한쪽 검색에만 등장한 결과도 해당 순위 점수로 포함한다.

### `rag/retriever.py`

필터 적용, Dense 검색, BM25 검색, RRF 결합을 연결한다.

필터 규칙:

- `tech`, `risk`: 요청한 `candidate_id`와 일치
- `parent`, `market`: 공통 문서이므로 후보 검색에서도 포함
- `doc_types`: 요청한 유형만 포함

### `rag/service.py`

다른 팀원이 사용하는 유일한 검색 진입점이다.

```python
def search_documents(
    query: str,
    candidate_id: str | None = None,
    doc_types: list[str] | None = None,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    ...
```

호출 예시:

```python
results = search_documents(
    query="이 회사의 로봇핸드 실물 조작 성공률은?",
    candidate_id="company_a",
    doc_types=["tech"],
    top_k=5,
)
```

## `data/`에 들어갈 파일

### `data/rag/manifest.csv`

```csv
doc_id,publisher,published_at,source_url,sha256,original_pages,used_pages,doc_type,candidate_id,local_path,title,page_ranges
figure_tech_001,Figure AI,2026-01-20,https://example.com/report.pdf,64자리해시,30,8,tech,figure_ai,documents/tech/figure_report.pdf,Figure AI Technical Report,10-17
sk_parent_001,SK Innovation,2025-12-01,https://example.com/sk.pdf,64자리해시,50,6,parent,COMMON,documents/parent/sk_report.pdf,SK Innovation Report,21-26
```

### `data/rag/documents/`

검색에 사용할 공개 PDF 원문을 유형별로 저장한다. 저작권이나 저장소 용량 때문에 Git에 올리면 안 되는 원문은 `.gitignore` 처리하고, 다운로드 URL과 준비 방법만 README에 기록한다.

### `data/rag/index/`

재생성 가능한 검색 인덱스를 둔다. 대용량 FAISS와 모델 파일은 기본적으로 Git에 올리지 않는다. 빈 폴더 유지가 필요하면 `.gitkeep`만 커밋한다.

## `evaluation/`에 들어갈 파일

### `evaluation/retrieval_questions.json`

```json
[
  {
    "question_id": "tech-001",
    "query": "로봇핸드의 실물 조작 성공률은?",
    "candidate_id": "company_a",
    "doc_types": ["tech"],
    "relevant_pages": [
      {"doc_id": "company_a_tech_report", "page": 12}
    ],
    "language_pair": "ko-en"
  }
]
```

### `evaluation/retrieval_eval.py`

다음을 계산한다.

- Hit Rate@5
- MRR@5
- 검색 평균 latency
- p50 latency
- p95 latency
- 교차 언어 문항 성능

### `evaluation/results/`

평가 시각, 모델, 청크 설정과 측정 결과를 JSON으로 저장한다.

```json
{
  "model": "BAAI/bge-m3",
  "chunk_size": 450,
  "chunk_overlap": 60,
  "hit_rate_at_5": 0.825,
  "mrr_at_5": 0.71,
  "p50_latency_ms": 83.4,
  "p95_latency_ms": 146.2
}
```

측정하지 않은 수치를 임의로 작성하지 않는다.

## Git에 올리지 않을 파일

```text
모델 캐시
대용량 FAISS 인덱스
저작권상 재배포할 수 없는 원문 PDF
개인 PC 절대 경로가 포함된 설정
.env
__pycache__/
```

## 완료 체크리스트

- [x] 사용 페이지 합계가 200페이지를 넘으면 적재가 중단된다.
- [x] 모든 chunk가 하나의 원문 페이지에만 속한다.
- [x] Dense Top20과 BM25 Top20을 실제로 검색한다.
- [x] RRF `k=60`, 동일 가중치를 적용한다.
- [x] 공통 문서가 후보 필터에서 누락되지 않는다.
- [x] Top5 결과에 필수 필드가 모두 존재한다.
- [x] Hit Rate@5와 MRR@5를 실제 질문으로 측정한다.
