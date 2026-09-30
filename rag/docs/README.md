# RAG 기능별 문서

`rag/`의 실행·검증 문서를 기능 단위로 분리한다. 개발 현황의 단일 기준인 `rag/DEVELOPMENT_STATUS.md`는 기존 위치에 유지한다.

| 폴더 | 기능 | 문서 |
|---|---|---|
| `fusion/` | Dense·BM25 RRF 결합 | `STEP6_VERIFICATION.md` |
| `retrieval/` | 필터와 공개 Hybrid Search | `STEP7_VERIFICATION.md` |
| `indexing/` | 실제 PDF indexing과 검색 | `STEP8_VERIFICATION.md` |
| `evaluation/` | Hit Rate@5·MRR@5 평가 | `STEP9_VERIFICATION.md` |
| `integration/` | 다른 Agent 공개 API 연동 | `STEP10_VERIFICATION.md` |
