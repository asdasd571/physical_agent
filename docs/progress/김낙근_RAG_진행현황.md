# 김낙근 RAG 개발 진행현황

## 현재 브랜치

```text
feature/rag
```

## 전체 진행 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| STEP 1 | RAG 구조와 공개 인터페이스 확정 | 완료 |
| STEP 2 | 데이터 모델, manifest, PDF loader | 완료 |
| STEP 3 | 페이지 단위 token chunker | 완료 |
| STEP 4 | BGE-M3 embedding과 FAISS | 구현 완료, 실제 모델 smoke test 대기 |
| STEP 5 | Kiwi tokenizer와 BM25 | 완료 |
| STEP 6 | RRF 순위 융합 | 완료 |
| STEP 7 | 필터 포함 `search_documents()` 완성 | 완료 |
| STEP 8 | 실제 문서 indexing과 Top5 검색 | 완료 |
| STEP 9 | Hit Rate@5와 MRR@5 평가 | 구현 완료, 40문항 수집 대기 |
| STEP 10 | 다른 Agent 호출 통합 확인 | 완료 |

## STEP 3 작업 기록

### 구현 내용

- `DocumentChunk` 모델 추가
- Hugging Face tokenizer와 호환되는 `TokenCodec` 계약 추가
- 기본 `chunk_size=450`, `overlap=60` 적용
- 각 `DocumentPage`를 독립적으로 분할해 페이지 경계 유지
- `source_id`, `doc_id`, `candidate_id`, `doc_type`, 원문 `page` 유지
- page ID, token 범위와 content hash 기반 deterministic `chunk_id` 생성
- 빈 tokenizer 결과와 잘못된 chunk 설정 검증

### 테스트 범위

- [x] 450 tokens보다 짧은 페이지는 청크 1개
- [x] 450 tokens보다 긴 페이지는 여러 청크
- [x] 인접 청크 60 tokens overlap
- [x] 서로 다른 원문 페이지가 하나의 청크로 합쳐지지 않음
- [x] 원문 page, source ID, document ID 유지
- [x] 동일 입력에서 동일 chunk ID 생성
- [x] 잘못된 chunk size와 overlap 거부

### 테스트 진행 기록

- 최초 수집 단계에서 `rag/__init__.py`의 `__all__` export 위치 오류 발견
- 공개 export 목록 내부로 이동하도록 최소 수정
- chunker 기능 테스트를 포함한 전체 테스트 `19 passed`

### 설계 결정

STEP 3에서 임의의 tokenizer를 production 기본값으로 두지 않는다. `chunk_page()`는 tokenizer를 명시적으로 받으며, STEP 4에서 `BAAI/bge-m3`의 실제 tokenizer를 연결한다. 이렇게 해야 450 tokens가 실제 embedding 모델 기준과 일치한다.

## 다음 작업

1. `BAAI/bge-m3` 실제 모델 다운로드와 한국어·영어 문장 embedding 확인
2. 실제 BGE-M3 tokenizer를 STEP 3 chunker에 연결
3. STEP 9 Hit Rate@5와 MRR@5 평가 구현

## STEP 4 작업 기록

### 구현 내용

- `sentence-transformers` 기반 BGE-M3 lazy loading
- Dense vector만 생성하고 L2 normalization 적용
- batch 문서 embedding과 단일 query embedding
- 모델 로딩 시간과 마지막 embedding 시간 기록
- FAISS `IndexFlatIP` 기반 cosine 검색
- 인덱스와 전체 chunk metadata 저장·복원
- 중복 chunk ID, dimension, NaN·무한값 검증

### 테스트 결과

- deterministic fake embedder를 이용한 FAISS 검색과 저장·복원 확인
- 전체 테스트 `28 passed`
- `faiss 1.15.1`, `numpy 2.5.3`, `sentence-transformers 5.7.0` import 확인
- 실제 BGE-M3 모델 파일 다운로드는 아직 실행하지 않음

## STEP 5 작업 기록

### 구현 내용

- Kiwi 기반 한국어 형태소 분석
- 영문 단어, 숫자, 소수·백분율과 하이픈 기술명 보존
- Unicode 폭과 다양한 dash 문자를 일관된 표기로 정규화
- BM25 `k1=1.5`, `b=0.75` 기본값 적용
- Sparse Top20 검색
- BM25 token corpus와 전체 chunk metadata 저장·복원
- Dense와 BM25가 공유하는 `DocumentChunk` 직렬화 규격 추가

### 테스트 결과

- 실제 Kiwi tokenizer 실행 확인
- `vision-language-action`, `3-finger`, `12.8%` 보존 확인
- BM25 관련 문서 순위와 무관한 질의 처리 확인
- BM25 저장·복원 후 원문 page와 metadata 유지
- 전체 테스트 `36 passed`
- 최초 테스트에서 `rag/__init__.py` export 위치 오류를 발견해 최소 수정 후 재검증

## STEP 6 작업 기록

### 구현 내용

- Dense Top20과 BM25 Top20 입력 제한
- RRF `k=60`
- Dense와 BM25 동일 가중치
- 중복 chunk ID의 점수 합산
- 기본 최종 Top5 반환
- 채널별 rank와 원검색 score를 retrieval metadata에 보존
- 동일 chunk ID의 출처·페이지·본문 충돌 검증

### 테스트 결과

- STEP 6 단독 테스트 `7 passed`
- 전체 회귀 테스트 `43 passed`
- `2 / 61`, `1 / 61 + 1 / 62` 수식 검증
- 원검색 score가 아닌 rank로 융합되는지 검증
- 각 채널 21위 이후 제외와 기본 Top5 확인
- 수동 확인 방법을 `rag/docs/fusion/STEP6_VERIFICATION.md`에 기록

## STEP 7 작업 기록

### 구현 내용

- candidate_id와 doc_type 공통 필터
- 후보 검색 시 다른 후보의 tech·risk 제외
- 후보 검색 시 candidate_id가 없는 parent·market 허용
- doc_types가 지정되면 요청 유형만 허용
- Dense와 BM25 검색 전에 필터 적용
- Dense Top20 + BM25 Top20 + RRF HybridRetriever
- 공개 `search_documents()` backend 연결

### 테스트 결과

- STEP 7 단독 테스트 `7 passed`
- 전체 회귀 테스트 `50 passed`
- candidate A와 candidate B 문서 격리 확인
- 공통 parent·market 문서 포함 확인
- tech 전용 검색에서 공통 문서 제외 확인
- 수동 확인 방법을 `rag/docs/retrieval/STEP7_VERIFICATION.md`에 기록

## STEP 8 작업 기록

### 구현 내용

- manifest부터 PDF loader, BGE tokenizer chunking, Dense·BM25 index 저장까지 통합
- 저장 index에서 HybridRetriever 복원
- indexing과 Top5 검색 CLI
- 공식 검증 PDF 다운로드와 SHA256 검증 스크립트
- RAG 테스트를 `tests/rag/`로 이동

### 실제 문서 검증

- SK Innovation ESG Report 2022 공식 PDF
- 전체 177페이지 중 원문 101~102페이지 사용
- 실제 BGE-M3로 6개 chunk 생성
- 모델 로딩 9.44초, Dense indexing 1.29초, BM25 indexing 0.85초
- 영어 질문 Top1: 원문 102페이지, RRF score `0.0327868852`
- 한국어 질문 Top1: 영어 원문 102페이지, RRF score `0.0325224749`
- 실제 PDF 102페이지 육안 대조 완료

### 테스트 결과

- RAG 테스트 `47 passed`
- 전체 테스트 `51 passed`
- 수동 재현 방법을 `rag/docs/indexing/STEP8_VERIFICATION.md`에 기록

## STEP 9 작업 기록

### 구현 내용

- 고정 `retrieval_questions.json` 로드와 입력 검증
- 정확한 `doc_id + page` 기준 Hit Rate@5와 MRR@5
- 질문별 latency와 전체 평균, p50, p95 계산
- `language_pair`별 품질·latency 집계
- 질문별 Top5 문서·페이지·chunk ID·score 결과 저장
- 저장된 Hybrid index를 평가하는 로컬 CLI

### 실제 문서 검증

- STEP 8 공식 PDF 평가 문항 2개 실행
- 영어→영어 1문항과 한국어→영어 1문항 모두 원문 102페이지 Top1
- Hit Rate@5 `1.0`, MRR@5 `1.0`
- 결과를 `evaluation/results/step9_sample.json`에 기록
- 2문항은 실행 검증용이며, 설계 목표 40문항의 검색 품질을 대표하지 않음
- 공용 `data/`에서 담당 영역을 구분하도록 RAG 데이터를 `data/rag/`로 이동

### 테스트 결과

- STEP 9 단독 테스트 `7 passed`
- RAG 테스트 `54 passed`
- 전체 테스트 `58 passed`
- 수동 재현 방법을 `rag/docs/evaluation/STEP9_VERIFICATION.md`에 기록

## STEP 10 작업 기록

### 구현 내용

- 다른 Agent가 공개 `search_documents()`만 사용하는 통합 테스트 추가
- 저장된 Dense·BM25 index 복원 후 공개 backend 등록 확인
- 설계의 `query`, `candidate_id`, `doc_types`, `top_k` 호출 형식 검증
- `RetrievedChunk` 반환 타입과 필수 근거 필드 검증
- 실제 BGE-M3 index를 공개 API로 실행하는 검증 스크립트 추가
- GraphState, 공통 Schema와 Agent 출력 형식은 변경하지 않음

### 실제 문서 검증

- SK Innovation 공식 PDF index를 공개 `search_documents()` 경로로 검색
- Top1 `doc_id`: `ski_esg_report_2022`
- Top1 원문 페이지: `102`
- Dense·BM25 RRF metadata 반환 확인

### 테스트 결과

- STEP 10 통합 테스트 `1 passed`
- RAG 테스트 `55 passed`
- 전체 테스트 `59 passed`
- 직접 확인 방법을 `rag/docs/integration/STEP10_VERIFICATION.md`에 기록

## main 병합 전 문서·설정 정리

- 역할 문서에 명시된 검색 상수를 `rag/config.py`로 중앙화
- 기존 모듈의 상수 이름은 호환되도록 유지
- STEP 6~10 검증 문서를 `rag/docs/` 아래 기능별 폴더로 이동
- `rag/DEVELOPMENT_STATUS.md`는 개발 현황의 단일 기준으로 기존 위치 유지
- `docs/roles/김낙근_RAG.md` 구조와 완료 체크리스트를 실제 구현에 맞게 갱신
- 설정 테스트 포함 RAG `56 passed`, 전체 `60 passed`

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-09-30 | STEP 3 token chunker와 테스트 작성 |
| 2026-09-30 | STEP 4 BGE-M3 embedding wrapper와 FAISS Dense store 작성 |
| 2026-09-30 | STEP 5 Kiwi tokenizer와 BM25 Sparse store 작성 |
| 2026-09-30 | STEP 6 Dense·BM25 RRF 순위 융합 작성 |
| 2026-09-30 | STEP 7 후보·문서 유형 필터와 Hybrid Search 작성 |
| 2026-09-30 | STEP 8 실제 BGE-M3와 공식 PDF Hybrid RAG 검증 |
| 2026-09-30 | STEP 9 고정 평가셋과 Hit Rate@5·MRR@5·latency 구현 |
| 2026-09-30 | STEP 10 다른 Agent의 공개 RAG API 통합 확인 |
| 2026-09-30 | main 병합 전 RAG 설정과 기능별 검증 문서 구조 정리 |
