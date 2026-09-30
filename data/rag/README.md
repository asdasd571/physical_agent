# RAG Data

김낙근 담당 RAG 파이프라인의 입력과 재생성 데이터를 관리한다.

```text
data/rag/
├── manifest.csv              # 공유용 문서 목록 형식
├── manifest.*.local.csv      # 로컬 검증 manifest (Git 제외)
├── documents/                # 원문 PDF (Git 제외)
└── index/                    # 재생성 가능한 Dense·BM25 index (Git 제외)
```

원문 PDF와 생성 index는 용량과 저작권 문제로 Git에 올리지 않는다. 재현 가능한 다운로드 URL, SHA256과 실행 방법은 `rag/STEP8_VERIFICATION.md`에 기록한다.
