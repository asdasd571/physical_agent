# STEP 9 검색 품질 평가 확인 방법

## 구현한 평가 기준

- Hit Rate@5: Top5에 정답 `doc_id + page`가 하나 이상 있으면 1
- MRR@5: Top5에서 처음 등장한 정답의 `1 / rank`
- latency: 각 질문의 Hybrid Search 전체 실행시간
- 전체 평균, p50, p95와 `language_pair`별 지표 기록

같은 문서라도 페이지가 다르면 정답으로 처리하지 않는다.

## 1. 자동 테스트

```bash
.venv/bin/python -m pytest tests/rag/test_retrieval_eval.py -q
.venv/bin/python -m pytest -q
```

예상 결과:

```text
7 passed
58 passed
```

확인할 내용:

- 정답이 3위이면 reciprocal rank가 `1/3`인지
- `doc_id`만 같고 페이지가 다르면 오답인지
- 정답이 없으면 hit와 reciprocal rank가 0인지
- 중복 질문 ID와 잘못된 페이지 번호를 거부하는지
- 질문의 candidate와 doc_type 필터가 검색기에 전달되는지

## 2. 실제 BGE-M3 평가

STEP 8의 인덱스가 없다면 먼저 `rag/docs/indexing/STEP8_VERIFICATION.md`에 따라 준비한다.

```bash
.venv/bin/python -m evaluation.retrieval_eval \
  --questions evaluation/retrieval_questions.json \
  --index-dir data/rag/index/step8_ski \
  --output evaluation/results/step9_sample.json \
  --device mps
```

Apple Silicon이 아니면 `--device mps`를 제거하거나 환경에 맞는 device를 지정한다.

현재 2문항 예시 평가 결과:

```text
question_count: 2
Hit Rate@5: 1.0
MRR@5: 1.0
영어 질문 정답 순위: 1
한국어→영어 질문 정답 순위: 1
```

첫 검색에는 모델의 첫 추론 준비시간이 포함될 수 있으므로 latency는 실행 환경과 캐시 상태에 따라 달라진다.

## 3. 팀 평가셋 확장

`evaluation/retrieval_questions.json`에 다음 형태로 문항을 추가한다.

```json
{
  "question_id": "tech-001",
  "query": "로봇핸드의 실물 조작 성공률은?",
  "candidate_id": "company_a",
  "doc_types": ["tech"],
  "relevant_pages": [
    {"doc_id": "company_a_tech_report", "page": 12}
  ],
  "language_pair": "ko-en"
}
```

정답은 검색 결과를 보고 역으로 정하지 말고, 팀원이 PDF 원문을 먼저 확인한 `doc_id + 원문 page`를 사용한다. 현재 2문항 결과는 실행 검증용이며, 설계 목표인 40문항 전체 품질을 대표하지 않는다.
