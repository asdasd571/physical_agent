# Development Status

## 현재 상태

- 담당자: 김낙근
- 브랜치: `feature/rag`
- 현재 단계: STEP 8 실제 공식 PDF indexing과 Top5 검색 완료
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
- [x] Dense Top20과 BM25 Top20 RRF 결합 구현
- [x] RRF `k=60`, 동일 가중치와 최종 기본 Top5 적용
- [x] RRF 결과에 채널별 원순위와 원점수 metadata 기록
- [x] RRF score 의미와 수동 확인 방법 문서화
- [x] 공통 candidate·doc_type 필터 규칙 구현
- [x] Dense와 BM25 검색 전에 동일한 필터 적용
- [x] 특정 후보 검색에서 다른 후보 문서 제외
- [x] 특정 후보 검색에서도 공통 parent·market 문서 허용
- [x] Dense Top20 + BM25 Top20 + RRF HybridRetriever 구현
- [x] 공개 `search_documents()`에 실제 hybrid backend 연결
- [x] RAG 테스트 파일을 `tests/rag/`로 정리
- [x] manifest → PDF → chunk → Dense·BM25 index 통합 파이프라인 구현
- [x] 저장된 index에서 HybridRetriever 복원 구현
- [x] indexing과 search CLI 구현
- [x] 실제 `BAAI/bge-m3` 모델 다운로드와 Dense embedding 실행
- [x] SK Innovation 공식 PDF 원문 101~102페이지 indexing
- [x] 영어와 한국어 질문으로 영어 원문 102페이지 Top1 검색
- [x] Top1 검색 결과와 실제 PDF 102페이지 육안 대조

## 진행 중인 작업

- [ ] STEP 9 고정 검색 평가셋과 Hit Rate@5·MRR@5 구현

## 다음 작업

1. retrieval_questions.json 평가 데이터 형식 확정
2. Hit Rate@5와 MRR@5 구현
3. search latency, p50과 p95 측정
4. 팀원에게 실제 질문과 정답 doc_id·page 수집

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
- `rag/fusion.py`
  - Dense Top20과 BM25 Top20 동일 가중치 RRF 구현
- `tests/test_fusion.py`
  - RRF 수식, 순위 기반 결합, Top20 제한과 Top5 반환 테스트
- `rag/STEP6_VERIFICATION.md`
  - 사용자가 직접 실행할 명령과 예상 결과 기록
- `rag/filters.py`
  - candidate_id와 doc_type 공통 필터 규칙 구현
- `rag/retriever.py`
  - Dense, BM25와 RRF를 연결한 HybridRetriever 구현
- `rag/dense_store.py`
  - 필터된 chunk vector 집합에서 Dense Top20 검색
- `rag/bm25_store.py`
  - 필터된 corpus 기준 BM25 통계와 Top20 검색
- `tests/test_filters.py`
  - 후보 문서와 공통 문서 필터 규칙 테스트
- `tests/test_retriever.py`
  - hybrid 검색과 공개 search_documents 통합 테스트
- `rag/STEP7_VERIFICATION.md`
  - STEP 7 직접 실행 명령과 확인 항목 기록
- `rag/indexing.py`
  - manifest부터 Dense·BM25 index 저장까지 통합 파이프라인 구현
- `rag/cli.py`
  - 실제 index 생성과 Top5 검색 CLI 구현
- `scripts/prepare_step8_sample.py`
  - 공식 검증 PDF 다운로드, SHA256 확인과 로컬 manifest 생성
- `tests/rag/`
  - 모든 RAG 테스트를 담당 폴더로 이동
- `tests/rag/test_indexing.py`
  - index 생성·저장·복원·검색 통합 테스트
- `rag/STEP8_VERIFICATION.md`
  - 실제 BGE-M3와 공식 PDF 재현 절차 기록
- `.gitignore`
  - 원문 PDF, 생성 index와 로컬 manifest 제외

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

```python
results = reciprocal_rank_fusion(
    dense_results,
    bm25_results,
    top_k=5,
)
```

```python
retriever = HybridRetriever(
    dense_store=dense_store,
    bm25_store=bm25_store,
    embedder=embedder,
    tokenizer=tokenizer,
)
configure_search_backend(retriever)

results = search_documents(
    query="로봇핸드 실물 조작 성공률",
    candidate_id="company_a",
    doc_types=["tech"],
    top_k=5,
)
```

```bash
python -m rag.cli index \
  --manifest data/manifest.step8.local.csv \
  --index-dir data/index/step8_ski \
  --device mps

python -m rag.cli search \
  "What is the highest priority of SK Innovation and its subsidiaries for workplace operations?" \
  --index-dir data/index/step8_ski \
  --doc-type parent \
  --top-k 5 \
  --device mps
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
RAG tests: 47 passed in 1.24s
All tests: 51 passed in 1.06s
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
- Dense·BM25 양쪽 1위 chunk의 RRF score가 `2 / 61`인지 확인
- Dense와 BM25의 동일 순위에 동일 가중치가 적용되는지 확인
- 원검색 score 크기가 아닌 검색 순위로 결합되는지 확인
- 각 채널의 21위 이후 결과 제외 확인
- 최종 기본 Top5와 RRF metadata 확인
- 같은 chunk ID의 출처·페이지·본문 충돌 시 오류 확인
- candidate A 검색에서 candidate B의 기업 문서 제외 확인
- candidate A 검색에서 공통 parent·market 문서 포함 확인
- `doc_types=["tech"]` 검색에서 공통 문서 제외 확인
- Dense와 BM25 모두 필터된 후보군에서 Top20 계산 확인
- 공개 `search_documents()`가 hybrid backend와 RRF 결과를 반환하는지 확인
- 공식 PDF SHA256과 전체 177페이지 확인
- manifest 사용 페이지가 원문 101~102페이지로 유지되는지 확인
- 실제 BGE-M3 tokenizer로 6개 chunk 생성 확인
- 실제 BGE-M3 Dense와 Kiwi BM25 index 생성 확인
- 영어 질문 Top1이 원문 102페이지, RRF score가 `2/61`인지 확인
- 한국어 질문으로 영어 원문 102페이지 Top1 검색 확인
- PDF 102페이지를 이미지로 렌더링해 검색 본문과 육안 대조

## 미해결 문제

- 문제: 한 문서와 두 질문만 검증했으므로 전체 검색 품질 수치는 아직 없음
- 원인: 팀원이 확인한 정답 doc_id·page 평가셋이 아직 준비되지 않음
- 현재 상태: STEP 9에서 Hit Rate@5, MRR@5와 latency를 측정할 예정

## 다른 팀원에게 영향을 주는 변경

- API 변경 여부: `index_manifest()`, `load_hybrid_retriever()`와 CLI가 추가됨. 기존 `search_documents()` 시그니처는 변경 없음
- State/Schema 변경 여부: 없음
- requirements 변경 여부: 없음
- 다른 브랜치에서 대응이 필요한 내용: RAG 테스트 경로가 `tests/rag/`로 이동함. 전체 `pytest` 명령에는 영향 없음

## Git 상태

STEP 3 코드는 이전 요청에 따라 `2a9841d`로 `feature/rag`에 commit/push된 상태다.

STEP 4까지는 `feature/rag`에 commit/push 완료됐다.

STEP 5까지는 `feature/rag`에 commit/push 완료됐다.

STEP 6까지는 `feature/rag`에 commit/push 완료됐다.

STEP 7까지는 `feature/rag`에 commit/push 완료됐다.

STEP 8 코드, 테스트 이동과 실제 문서 검증 문서는 검증을 마쳤으며 `feature/rag`에 commit/push한다.

다음 commit 후보 메시지:

`:sparkles:[FEAT] 실제 PDF Hybrid RAG 인덱싱 실행 구현`
