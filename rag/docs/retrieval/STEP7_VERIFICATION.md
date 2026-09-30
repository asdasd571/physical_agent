# STEP 7 Hybrid Search 확인 방법

## 구현 기준

- `candidate_id` 필터를 Dense와 BM25 검색 전에 적용
- `doc_types` 필터를 Dense와 BM25 검색 전에 적용
- 특정 후보 검색에서 다른 후보의 `tech`, `risk` 문서 제외
- 특정 후보 검색에서도 공통 `parent`, `market` 문서 허용
- `doc_types=["tech"]`이면 공통 문서를 자동 추가하지 않음
- Dense Top20 + BM25 Top20 + RRF `k=60` + 최종 기본 Top5

## 1. STEP 7 테스트 실행

프로젝트 루트에서 실행한다.

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_filters.py tests/test_retriever.py -v
```

예상 결과:

```text
7 passed
```

## 2. 직접 확인할 항목

### 후보 필터

`candidate_id="company_a"`로 검색했을 때:

- `company_a`의 `tech`, `risk`는 검색 가능
- `company_b`의 `tech`, `risk`는 결과에 없어야 함
- `candidate_id=None`인 `parent`, `market`은 검색 가능

### 문서 유형 필터

```python
search_documents(
    query="robot",
    candidate_id="company_a",
    doc_types=["tech"],
    top_k=5,
)
```

결과의 모든 `doc_type`이 `tech`인지 확인한다. 이 경우 `parent`, `market`은 공통 문서여도 포함되면 안 된다.

### RRF 연결

각 결과에서 다음을 확인한다.

```python
result.metadata["retrieval"]["fusion"] == "rrf"
result.metadata["retrieval"]["rrf_k"] == 60
```

`result.score`는 RRF score이며 신뢰도나 확률이 아니다.

## 3. 전체 회귀 테스트

```bash
python -m pytest -q
python -m compileall -q rag schemas tests
```

확인할 항목:

- 기존 PDF loader와 chunker 테스트 통과
- Dense, BM25와 RRF 테스트 통과
- 공개 `search_documents()` 시그니처가 변경되지 않음
- State와 Schema 테스트 통과

## 4. 현재 검증 범위

이 테스트는 작은 deterministic corpus로 hybrid 검색과 필터 연결을 검증한다. 실제 기업 PDF와 실제 BGE-M3 검색 품질은 STEP 8에서 별도로 확인해야 한다.
