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
| STEP 4 | BGE-M3 embedding과 FAISS | 대기 |
| STEP 5 | Kiwi tokenizer와 BM25 | 대기 |
| STEP 6 | RRF 순위 융합 | 대기 |
| STEP 7 | 필터 포함 `search_documents()` 완성 | 대기 |
| STEP 8 | 실제 문서 indexing과 Top5 검색 | 대기 |
| STEP 9 | Hit Rate@5와 MRR@5 평가 | 대기 |
| STEP 10 | 다른 Agent 호출 통합 확인 | 대기 |

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

1. STEP 3 커밋과 `feature/rag` push
2. BGE-M3 모델 로딩 시간 측정
3. 문서 embedding과 FAISS 인덱스 저장 구조 구현

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-09-30 | STEP 3 token chunker와 테스트 작성 |
