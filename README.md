# physical_agent

LLM 기반 Agentic RAG 투자평가 파이프라인이다. Dense/BM25 검색 결과를 LLM이 근거 구조로 추출하고,
LangGraph의 review/repair 루프를 거친 뒤 결정론적 Judge가 점수와 Gate를 확정한다. LLM은 최종 투자
해설을 작성하지만 점수나 `INVEST/HOLD`를 변경할 수 없다.

## 실행

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt -r reporting/requirements.txt

export OPENAI_API_KEY="반별로_공유받은_API_KEY"
export OPENAI_MODEL="gpt-4o-mini"

python -m rag.cli index \
  --manifest data/rag/manifest.csv \
  --index-dir data/rag/index/investment \
  --device mps

python app.py --index data/rag/index/investment
```

또는 프로젝트 루트의 `.env`에 `OPENAI_API_KEY`와 `OPENAI_MODEL`을 작성하면 `app.py`가 자동으로 읽는다.

Linux/Intel 환경에서는 `--device cpu`를 사용한다. API 비용 없이 구조만 확인하려면
`python app.py --index data/rag/index/investment --skip-llm`을 사용할 수 있지만, 이 경우 LLM 기반
근거 추출과 투자 해설은 실행되지 않는다.

보고서는 `reporting/output/investment_report_YYYY-MM-DD_RUNID.pdf`와 같은 이름의 JSON으로 생성된다.
직접 경로를 정하려면 `--report-output reporting/output/my_report.pdf`를 사용한다.
