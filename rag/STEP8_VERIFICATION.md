# STEP 8 실제 PDF 통합 검색 확인 방법

## 검증 문서

- 문서: SK Innovation ESG Report 2022 영문본
- 발행자: SK Innovation
- 원문 페이지: 101~102
- `doc_type`: `parent`
- `candidate_id`: `COMMON`
- 알려진 정답: 원문 102페이지의 Safety and Health Guidelines

PDF와 로컬 index는 Git에 올리지 않는다.

## 1. 환경 준비

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## 2. 공식 PDF와 로컬 manifest 준비

```bash
python -m scripts.prepare_step8_sample
```

예상 결과:

```text
Pages: 177 (using original pages 101-102)
Manifest: data/manifest.step8.local.csv
```

스크립트는 공식 PDF의 SHA256과 전체 177페이지를 검사한다. 검색에는 원문 101~102페이지만 사용하므로 페이지 예산에는 2페이지가 반영된다.

## 3. 실제 BGE-M3와 Kiwi BM25 index 생성

Apple Silicon Mac:

```bash
python -m rag.cli index \
  --manifest data/manifest.step8.local.csv \
  --index-dir data/index/step8_ski \
  --device mps \
  --batch-size 4
```

CPU 환경:

```bash
python -m rag.cli index \
  --manifest data/manifest.step8.local.csv \
  --index-dir data/index/step8_ski \
  --device cpu \
  --batch-size 4
```

최초 실행에서는 `BAAI/bge-m3` 모델 다운로드 때문에 오래 걸릴 수 있다.

확인할 값:

```text
document_count: 1
page_count: 2
chunk_count: 6
embedding_model: BAAI/bge-m3
chunk_size: 450
chunk_overlap: 60
```

## 4. 영어 질문으로 Top5 검색

```bash
python -m rag.cli search \
  "What is the highest priority of SK Innovation and its subsidiaries for workplace operations?" \
  --index-dir data/index/step8_ski \
  --doc-type parent \
  --top-k 5 \
  --device mps
```

Top1에서 확인할 내용:

```text
doc_id: ski_esg_report_2022
doc_type: parent
page: 102
```

본문에 다음 문장이 있어야 한다.

```text
Establishing safe and healthy workplace operations is the highest priority of SK Innovation and its subsidiaries.
```

Top1 RRF score 예상값:

```text
0.0327868852 = 1/61 + 1/61
```

## 5. 한국어 질문으로 영어 문서 검색

```bash
python -m rag.cli search \
  "SK이노베이션과 자회사의 안전하고 건강한 사업장 운영에서 최우선 과제는 무엇인가?" \
  --index-dir data/index/step8_ski \
  --doc-type parent \
  --top-k 5 \
  --device mps
```

Top1이 원문 102페이지인지 확인한다. 이 검사는 BGE-M3의 한국어 질문 → 영어 근거 검색을 확인한다.

## 6. 원문 페이지 직접 대조

macOS에서 PDF를 열고 102페이지로 이동하거나 다음 명령으로 이미지를 만든다.

```bash
pdftoppm -f 102 -l 102 -png -singlefile -r 110 \
  data/documents/parent/sk_2022_esg_report_eng.pdf \
  /tmp/sk-page-102
```

원문 102페이지 왼쪽 상단 `Safety and Health Guidelines`에서 검색 결과 문장을 직접 확인한다.

## 7. 전체 자동 테스트

RAG 테스트만 실행:

```bash
python -m pytest tests/rag -q
```

전체 테스트:

```bash
python -m pytest -q
python -m compileall -q rag schemas tests
```

## 현재 검증 결과

- 실제 공식 PDF SHA256 확인
- 원문 101~102페이지 유지
- 실제 BGE-M3 tokenizer로 6개 chunk 생성
- 실제 BGE-M3 Dense embedding 생성
- Kiwi BM25 index 생성
- Dense + BM25 + RRF Top5 검색 성공
- 영어 질문의 Top1이 원문 102페이지
- 한국어 질문으로 영어 원문 102페이지 Top1 검색 성공

이 결과는 한 문서와 두 질문에 대한 smoke test다. 전체 검색 품질은 STEP 9의 고정 평가셋으로 Hit Rate@5와 MRR@5를 측정해야 한다.
