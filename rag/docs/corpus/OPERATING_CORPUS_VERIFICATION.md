# 운영 RAG 문서 풀 검증

## 1. 빠른 자동 테스트

```bash
.venv/bin/python -m pytest -q
```

다음 항목을 확인한다.

- manifest 200페이지 제한
- PDF 페이지 선택과 원문 페이지 번호 유지
- 450-token chunk와 60-token overlap
- Dense·BM25·RRF 검색
- 후보 필터와 공통 문서 필터
- Agent 공개 API
- State reducer

## 2. 원문 PDF와 manifest 확인

```bash
.venv/bin/python - <<'PY'
from rag.manifest import load_manifest
from rag.loader import load_manifest_documents

manifest = load_manifest("data/rag/manifest.csv")
pages = load_manifest_documents(manifest)

print("documents:", len(manifest.entries))
print("used pages:", manifest.total_used_pages)
print("pages by type:", {key.value: value for key, value in manifest.pages_by_type.items()})
print("loaded pages:", len(pages))
PY
```

예상 결과:

```text
documents: 14
used pages: 192
pages by type: {'tech': 97, 'parent': 0, 'market': 49, 'risk': 46}
loaded pages: 192
```

## 3. 실제 BGE-M3 인덱스 생성

Apple Silicon:

```bash
.venv/bin/python -m rag.cli index \
  --manifest data/rag/manifest.csv \
  --index-dir data/rag/index/investment \
  --device mps
```

CPU 환경:

```bash
.venv/bin/python -m rag.cli index \
  --manifest data/rag/manifest.csv \
  --index-dir data/rag/index/investment \
  --device cpu
```

완료되면 `chunk_count`, `dense_index_seconds`, `bm25_index_seconds`가 출력되고 다음 파일이 생성된다.

```text
data/rag/index/investment/
├── dense/index.faiss
├── dense/chunks.json
├── bm25/bm25.json
└── index_run.json
```

## 4. 후보별 검색 확인

에이로봇 기술 및 경쟁 제품:

```bash
.venv/bin/python -m rag.cli search \
  "에이로봇 ALICE 4의 손 자유도와 경쟁 로봇 핸드의 촉각 센서 사양" \
  --index-dir data/rag/index/investment \
  --candidate-id arobot \
  --doc-type tech \
  --top-k 5 \
  --device mps
```

에이딘로보틱스 센서 비교:

```bash
.venv/bin/python -m rag.cli search \
  "6축 힘 토크 센서의 측정 범위와 경쟁 제품 대비 차이" \
  --index-dir data/rag/index/investment \
  --candidate-id aidin_robotics \
  --doc-type tech \
  --top-k 5 \
  --device mps
```

Figure AI 현장 실증:

```bash
.venv/bin/python -m rag.cli search \
  "BMW 공장에서 Figure 로봇이 처리한 부품 수와 실제 가동 시간" \
  --index-dir data/rag/index/investment \
  --candidate-id figure_ai \
  --doc-type tech \
  --top-k 5 \
  --device mps
```

공통 투자 위험 기준:

```bash
.venv/bin/python -m rag.cli search \
  "AI 스타트업 투자 실사에서 시장과 팀, 재무 위험을 어떻게 확인해야 하는가" \
  --index-dir data/rag/index/investment \
  --candidate-id arobot \
  --doc-type risk \
  --top-k 5 \
  --device mps
```

## 5. 사용자가 직접 판정할 항목

테스트가 통과했다는 사실만 보지 말고 검색 결과의 다음 값을 원문 PDF와 비교한다.

1. `candidate_id`가 요청한 후보이거나 `None`인 공통 문서인지 확인한다.
2. `doc_type`이 요청한 유형인지 확인한다.
3. `doc_id`와 `page`로 원문 PDF의 해당 페이지를 직접 연다.
4. 출력된 `content`가 원문에 실제로 존재하는지 확인한다.
5. 질문에 필요한 수치와 단위가 Top5 안에 포함되는지 확인한다.
6. 기업 자체 발표는 독립 검증 사실이 아니라 회사 주장으로 해석한다.

RRF `score`는 신뢰 확률이 아니라 Dense와 BM25 검색 순위를 합친 점수다. 점수가 높다는 이유만으로 사실이 검증된 것은 아니다.
