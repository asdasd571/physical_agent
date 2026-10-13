"""실행 산출물과 테스트 결과를 읽어 10페이지 이내의 평가 보고서를 만든다."""

import argparse
from html import escape
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pymupdf

from reporting.supervisor_report import write_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory")
    parser.add_argument("--tests", default="artifacts/pytest.xml")
    parser.add_argument("--output", default="docs/supervisor/evidence/evaluation_report.pdf")
    args = parser.parse_args()
    directory = Path(args.run_directory)
    run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    quality = json.loads((directory / "quality.json").read_text(encoding="utf-8"))
    suites = ET.parse(args.tests).getroot()
    count = sum(int(suite.attrib["tests"]) for suite in suites.iter("testsuite"))
    failures = sum(int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0)) for suite in suites.iter("testsuite"))
    rows = "".join(f"<tr><td>{escape(candidate)}</td><td>{control['dispatch_count']}</td>"
                   f"<td>{escape(control['termination_reason'])}</td></tr>" for candidate, control in run["routing"].items())
    pages = [
        "<h1>Multi-Agent Orchestration 평가 보고서</h1><h2>SUMMARY</h2>"
        "<p>기존 Physical AI 스타트업 투자평가 RAG를 Supervisor 구조로 확장했습니다. "
        "후보별 근거의 부족한 항목을 확인하여 조사 담당자를 선택하고, 보고서 생성 이후 품질 평가와 재작성을 수행합니다.</p>"
        "<h2>1. 패턴과 구현</h2><p>Supervisor는 적격성, 미수행 관점, 미확인 지표 수와 호출 예산을 기준으로 분기합니다. "
        "하위 에이전트는 직접 연결하지 않고 Supervisor로 복귀합니다. 담당자에게 자신의 이전 결과와 명시적으로 전달한 자료만 제공합니다.</p>"
        "<p>근거 충분성 통과와 조사 한도 도달을 구분합니다. 근거가 부족한 채 한도에 도달하면 HOLD로 남깁니다. "
        "투자 점수 계산과 보고서 품질 평가는 별도 노드입니다.</p>"
        "<h2>2. State와 복구</h2><p>제어 상태와 분석 결과를 분리하고 출처는 ID로 병합합니다. 후보는 최대 3개, "
        "담당자 호출은 기본 2회, 보고서 수정은 2회로 제한합니다. SQLite 체크포인트로 완료 노드를 반복하지 않고 재개합니다.</p>"
        "<p>실행 ID, LangSmith trace ID와 외부 JSONL을 연결합니다. PDF 원문과 검색 벡터는 State 밖에서 관리합니다. "
        "예외가 발생하면 유형을 기록하고 재시도하며, 마지막까지 확보하지 못한 값은 자료 없음으로 표시합니다.</p>"
        "<h2>3. 문서와 적격성 분기</h2><p>200페이지의 문서에서 논문 DOI와 저자 소속, 센서 측정 오차, 고객 확인 운영량을 수집합니다. "
        "투자 단계만 범위 밖인 정상 비상장사는 비교 분석을 진행합니다. 비교 점수와 투자 점수를 구분하며 G1 제외를 해제하지 않습니다.</p>"
        "<h2>4. 보고서 품질</h2><p>규칙 기반으로 출처 연결, 중립성, 편향 통제, 네 관점의 포함 여부를 평가합니다. "
        "품질 미달 시 원값과 출처를 기준으로 재작성합니다. 해결되지 않은 문제는 수정 한도 뒤에도 실패 상태로 유지합니다.</p>",
        "<h1>실행 검증과 한계</h1>"
        f"<p>실행 ID: {escape(run['run_id'])}<br>LangSmith trace ID: {escape(run['trace_id'])}</p>"
        f"<p>자동 테스트: {count}개 / 실패·오류: {failures}개입니다. 동적 분기, 재조사, 작업 실패, 통신 제약, 품질 재작성과 재개를 검증했습니다.</p>"
        "<table><tr><th>후보</th><th>담당자 호출 수</th><th>종료 사유</th></tr>" + rows + "</table>"
        f"<p>최종 보고서 품질 상태는 {escape(quality['status'])}입니다.</p>"
        "<h2>동적 동작 실증</h2><p>운영 실행에서 근거가 부족한 담당자를 다시 호출하고, 투자 단계 제외 후보도 비교 분석했습니다. "
        "별도 결함 주입 시나리오에서는 추천 표현을 포함한 초안을 거부한 뒤 재작성하여 통과하는 경로와 최초 호출 장애 후 재시도를 확인했습니다. "
        "이 시나리오는 운영 결과와 구분하여 기록했습니다.</p>"
        "<h2>제약과 해석</h2><p>품질 평가는 형식과 구조 중심입니다. 인용된 원문이 모든 문장을 의미상 입증하는지, "
        "출처 자체가 신뢰할 만한지까지 자동으로 보장하지 않습니다. 현재 보고서의 HOLD는 수집한 근거와 규칙에 따른 결과입니다.</p>"
        "<p>기존 기준과 초기 단계 기준의 점수를 병기합니다. 공개 사양·실물 센서 시험·공개 시연은 초기 단계 기준에서 최대 2/5점만 인정합니다. "
        "기존 투자 판정에는 이 완화 기준을 사용하지 않습니다.</p>"
        "<p>첨부 PNG는 LangSmith API에서 실제 실행 기록을 조회하여 렌더링한 자료입니다. 웹 UI 캡처와 구분합니다. "
        "과제에서 요구하는 웹 화면 캡처는 LangSmith의 해당 실행 화면에서 별도로 확보해야 합니다.</p>"
        "<h2>REFERENCE</h2><p>과제 안내: Multi-Agent Orchestration, 2026-10-13.<br>"
        "기존 코드: github.com/asdasd571/physical_agent.<br>"
        "실행 근거: run.json, quality.json, LangSmith trace와 pytest.xml입니다.<br>"
        "다음 페이지는 해당 실행에서 생성한 후보 평가 보고서입니다.</p>",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    intro = output.with_name(".submission-intro.pdf")
    write_pdf(pages, intro)
    try:
        with pymupdf.open(intro) as document, pymupdf.open(run["report"]) as report:
            document.insert_pdf(report)
            if len(document) > 10:
                raise ValueError("평가 보고서가 10페이지를 초과합니다.")
            document.save(output)
            print(f"{len(document)}페이지 평가 보고서를 생성했습니다: {output}")
    finally:
        intro.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
