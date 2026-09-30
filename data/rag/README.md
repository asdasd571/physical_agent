# RAG Data

김낙근 담당 RAG 파이프라인의 입력과 재생성 데이터를 관리한다.

```text
data/rag/
├── manifest.csv              # 공유용 문서 목록 형식
├── manifest.*.local.csv      # 로컬 검증 manifest (Git 제외)
├── documents/                # 원문 PDF (Git 제외)
└── index/                    # 재생성 가능한 Dense·BM25 index (Git 제외)
```

`manifest.csv`가 참조하는 운영 원문 PDF는 팀원이 병합 직후 동일한 문서로 색인·테스트할 수 있도록 Git에 포함한다. manifest에 등록되지 않은 실험용 PDF와 생성 index는 Git에 올리지 않는다. 재현 가능한 다운로드 URL과 SHA256은 manifest에 기록한다.

운영 문서의 선정 기준과 192페이지 배분은 `DOCUMENT_COLLECTION_PLAN.md`에 기록하며, 실제 색인 대상은 `manifest.csv`의 `page_ranges`만 사용한다. 기존 SK ESG 원문은 검색 기능 검증용 로컬 데이터이며 운영 manifest에는 포함하지 않는다.
