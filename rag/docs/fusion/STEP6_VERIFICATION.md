# STEP 6 RRF 확인 방법

## 구현 기준

- Dense 상위 20개 사용
- BM25 상위 20개 사용
- Reciprocal Rank Fusion `k=60`
- Dense와 BM25 동일 가중치
- 최종 기본 Top5 반환
- RRF score는 검색 순위 융합 점수이며 사실의 신뢰도나 확률이 아님

## 1. 개발 환경 준비

프로젝트 루트에서 실행한다.

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 2. STEP 6 테스트만 실행

```bash
python -m pytest tests/test_fusion.py -v
```

예상 결과:

```text
7 passed
```

확인할 항목:

- Dense와 BM25에서 모두 1위인 chunk의 점수가 `2 / 61`인지 확인
- Dense 1위와 BM25 1위가 각각 한쪽에만 있으면 같은 점수인지 확인
- 원래 Dense/BM25 score 크기가 아니라 순위로 결합되는지 확인
- 각 검색 결과의 21위 이후가 RRF 대상에서 제외되는지 확인
- 기본 반환 개수가 Top5인지 확인
- 같은 `chunk_id`의 본문·페이지가 서로 다르면 오류가 발생하는지 확인

## 3. 전체 회귀 테스트 실행

```bash
python -m pytest -q
python -m compileall -q rag schemas tests
```

확인할 항목:

- 기존 PDF loader와 chunker 테스트 통과
- FAISS Dense 검색 테스트 통과
- Kiwi BM25 테스트 통과
- 공통 Schema와 `search_documents()` 인터페이스 테스트 통과

## 4. Python에서 결과 확인

테스트 데이터는 `tests/test_fusion.py`에 있으며, 핵심 계산식은 다음과 같다.

```python
score = 1 / (60 + rank)
```

Dense 1위이면서 BM25 1위인 결과:

```text
1 / 61 + 1 / 61 = 0.0327868852...
```

Dense 1위, BM25 2위인 결과:

```text
1 / 61 + 1 / 62 = 0.0325224749...
```

`RetrievedChunk.metadata["retrieval"]`에서 다음 값을 확인할 수 있다.

```text
fusion
rrf_k
dense_rank
bm25_rank
dense_score
bm25_score
```

`RetrievedChunk.score`는 RRF score다. 이를 근거 신뢰도, 사실일 확률 또는 LLM confidence로 표시하면 안 된다.
