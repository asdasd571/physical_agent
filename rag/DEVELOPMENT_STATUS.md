# Development Status

## 현재 상태

- 담당자: 김낙근
- 브랜치: `feature/rag`
- 현재 단계: STEP 5 Kiwi tokenizer와 BM25 구현 완료
- 마지막 업데이트: 2026-09-30

## 완료된 작업

- [x] RAG 전체 구조와 공개 검색 인터페이스 확정
- [x] `ManifestEntry`, `DocumentPage`, `RetrievedChunk` 모델 구현
- [x] manifest 필수 필드와 전체 200페이지 예산 검증
- [x] 원문 페이지 번호를 유지하는 PDF loader 구현
- [x] `DocumentChunk` 모델 구현
- [x] 페이지별 450-token, 60-token overlap chunker 구현
- [x] deterministic `chunk_id` 생성
- [x] 짧은 페이지, 긴 페이지, overlap, 페이지 경계와 ID 안정성 테스트
- [x] BGE-M3 lazy loading과 Dense embedding wrapper 구현
- [x] 실제 BGE-M3 tokenizer 공개 및 chunker 연결 규격 확보
- [x] FAISS cosine 유사도 인덱스 생성과 검색 구현
- [x] FAISS 인덱스와 chunk metadata 저장·복원 구현
- [x] 모델 로딩 시간과 indexing 시간 측정 필드 구현
- [x] Kiwi 기반 한국어 sparse tokenizer 구현
- [x] 영문·숫자·하이픈 기술명 보존과 Unicode 표기 정규화
- [x] BM25 점수 계산과 Sparse Top20 검색 구현
- [x] BM25 index와 chunk metadata 저장·복원 구현
- [x] Dense·BM25 공용 `DocumentChunk` 직렬화 규격 구현

## 진행 중인 작업

- [ ] `BAAI/bge-m3` 모델 파일 다운로드 후 실제 embedding smoke test

## 다음 작업

1. STEP 6 Dense Top20과 BM25 Top20의 RRF 구현
2. RRF `k=60`, 동일 가중치와 중복 chunk 결합 테스트
3. 실제 BGE-M3로 짧은 한국어·영어 문장 embedding smoke test
4. 실제 PDF page를 BGE-M3 tokenizer로 chunking

## 변경된 파일

- `rag/DEVELOPMENT_STATUS.md`
  - 김낙근 담당 RAG 개발 절차와 현재 진행 상태 기록
- `rag/models.py`
  - `DocumentChunk` 모델 추가
- `rag/chunker.py`
  - tokenizer 독립형 페이지 단위 token chunker 구현
- `rag/__init__.py`
  - chunk 모델과 함수 공개
- `tests/test_chunker.py`
  - chunk 크기, overlap, 페이지 경계와 deterministic ID 테스트
- `docs/progress/김낙근_RAG_진행현황.md`
  - STEP 3 완료 상태 기록
- `rag/embeddings.py`
  - BGE-M3 lazy loading, batch Dense embedding과 실행시간 측정 구현
- `rag/dense_store.py`
  - FAISS 인덱스 생성, Top-K 검색, 저장과 복원 구현
- `tests/test_embeddings.py`
  - embedding shape, query, tokenizer와 입력 검증 테스트
- `tests/test_dense_store.py`
  - FAISS 검색 순위, metadata 복원, 중복과 dimension 검증 테스트
- `requirements.txt`
  - `numpy`, `faiss-cpu`, `sentence-transformers`, `kiwipiepy` 추가
- `rag/tokenizer.py`
  - Kiwi 형태소 분석과 영문·숫자·하이픈 기술명 보존 구현
- `rag/bm25_store.py`
  - BM25 build, Top-K 검색, 저장과 복원 구현
- `tests/test_tokenizer.py`
  - Unicode, 하이픈, 영문 기술명, 숫자 보존 테스트
- `tests/test_bm25_store.py`
  - Sparse 검색 순위, 저장·복원, 중복과 파라미터 테스트

## 현재 인터페이스

```python
def search_documents(
    query: str,
    candidate_id: str | None = None,
    doc_types: list[str] | None = None,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    ...
```

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

```python
embedder = BgeM3Embedder(model_name="BAAI/bge-m3")
chunks = chunk_pages(pages, embedder.tokenizer)

store = FaissDenseStore(dimension=embedder.dimension)
store.build(chunks, embedder)
results = store.search(query, embedder, top_k=20)
```

```python
tokenizer = KiwiTechnicalTokenizer()
bm25_store = Bm25Store(k1=1.5, b=0.75)
bm25_store.build(chunks, tokenizer)
results = bm25_store.search(query, tokenizer, top_k=20)
```

## 테스트 결과

실행 명령:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q rag schemas tests
```

결과:

```text
36 passed in 1.31s
compileall PASS
```

확인한 항목:

- 짧은 페이지는 단일 청크 생성
- 450 tokens 초과 페이지 분할
- 인접 청크 60-token overlap
- 서로 다른 원문 페이지의 내용이 합쳐지지 않음
- 원문 `page`, `source_id`, `doc_id` 유지
- 동일 입력에서 동일 `chunk_id` 생성
- 기존 manifest, loader, schema와 service 테스트 영향 없음
- Dense embedding의 `(문서 수, dimension)` 반환 형식
- FAISS 검색에서 가장 유사한 chunk가 1위로 반환됨
- 인덱스 저장·복원 후 chunk ID, page, source ID와 local path 유지
- 중복 chunk ID와 embedding dimension 불일치 거부
- `faiss`, `numpy`, `sentence-transformers` 로컬 import 정상 동작
- Kiwi 실제 형태소 분석 실행 확인
- `vision-language-action`, `3-finger`, `12.8%` 단일 token 보존
- BM25 관련 문서가 1위로 반환되고 무관한 질의는 빈 결과 반환
- BM25 저장·복원 후 chunk page와 custom metadata 유지
- 기존 Dense index 저장·복원 테스트 영향 없음

## 미해결 문제

- 문제: 실제 `BAAI/bge-m3` 모델 파일을 다운로드하는 smoke test는 아직 실행하지 않음
- 원인: 모델 파일이 크고 이번 로컬 테스트는 deterministic fake embedder로 FAISS 계약을 우선 검증함
- 현재 상태: `sentence-transformers` 런타임 import는 확인했으며 실제 모델 다운로드·embedding은 다음 확인 대상으로 남김

## 다른 팀원에게 영향을 주는 변경

- API 변경 여부: `KiwiTechnicalTokenizer`, `Bm25Store`가 추가됐으나 기존 `search_documents()` 규격은 변경 없음
- State/Schema 변경 여부: 없음
- requirements 변경 여부: `kiwipiepy` 추가
- 다른 브랜치에서 대응이 필요한 내용: 병합 후 `pip install -r requirements.txt` 재실행 필요

## Git 상태

STEP 3 코드는 이전 요청에 따라 `2a9841d`로 `feature/rag`에 commit/push된 상태다.

STEP 4까지는 `feature/rag`에 commit/push 완료됐다.

STEP 5 코드, requirements와 개발 현황 문서는 검증을 마쳤으며 `feature/rag`에 commit/push한다.

다음 commit 후보 메시지:

`:sparkles:[FEAT] Kiwi BM25 Sparse 검색 구현`
