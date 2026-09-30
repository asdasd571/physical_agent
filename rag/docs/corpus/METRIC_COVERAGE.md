# 투자지표 Corpus Coverage

RAG는 점수나 `INVEST/HOLD`를 판단하지 않고 지표 계산에 필요한 원값과 출처만 반환한다. 값이 corpus에 없으면 Agent는 `자료 없음`으로 남겨야 한다.

## 운영 문서 풀

- 총 14개 문서, 161쪽, 197 chunks
- `tech` 97쪽, `market` 49쪽, `parent` 12쪽, `risk` 3쪽
- 일반 AI 위험관리·투자 프레임워크는 F1~F4 원값이 없어 운영 manifest에서 제외
- parent는 SK Innovation ESG Report와 Incheon CLX Safety Regulation의 선택 페이지만 사용

## Coverage

| 지표 | 상태 | 직접 근거 또는 부족 사유 |
|---|---|---|
| T1 | MISSING | 후보별 핵심 기술진의 검증 가능한 경력 원값 부족 |
| T2 | OK | AIDIN 카탈로그 p.2 |
| K1 | OK | Figure Helix p.2 |
| K2 | MISSING | 성공 횟수/전체 시도 횟수 없음 |
| K3 | OK | Figure BMW deployment p.1 |
| S1 | OK | AIDIN 카탈로그 p.12 |
| S2 | OK | SK ESG p.34, p.80 및 Incheon CLX p.4, p.8 |
| P1 | OK | KIRIA p.69 등 |
| R1 | OK | Figure Series C p.1. AeiROBOT/AIDIN 금액 근거는 없음 |
| R2 | MISSING | 국가 연구비 확정 금액 없음 |
| R3 | MISSING | 후보별 기간별 고용 인원 없음 |
| M1 | MISSING | 등록 상태·패밀리를 검증할 특허 원문 없음 |
| F1 | MISSING | 후보별 현금·단기금융상품·영업현금흐름 없음 |
| F2 | MISSING | 후보별 자본·부채·감사의견 없음 |
| F3 | MISSING | 후보별 공식 제재 조회 원문 없음 |
| F4 | MISSING | KCs·IECEx·방폭 인증 근거 없음 |

## 직접 확인

```bash
.venv/bin/python -m evaluation.metric_coverage
.venv/bin/python -m pytest -q
```

```bash
.venv/bin/python -m evaluation.metric_coverage \
  --index-dir data/rag/index/investment_v2 --device mps
```

```bash
.venv/bin/python -m evaluation.retrieval_eval \
  --questions evaluation/retrieval_questions.json \
  --index-dir data/rag/index/investment_v2 --device mps \
  --output evaluation/results/investment_corpus_40.json
```

```bash
.venv/bin/python -m rag.cli search \
  "배터리 셀 또는 모듈 핸들링 작업에 대한 SK 계열 제조 현장 수요" \
  --index-dir data/rag/index/investment_v2 \
  --doc-type parent --top-k 5 --device mps
```

마지막 결과가 `doc_type: parent`이고 `sk_innovation_esg_2022` p.6을 포함하는지, corpus에 없는 지표가 `MISSING`으로 남는지 확인한다.
