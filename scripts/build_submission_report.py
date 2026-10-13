"""실행 산출물과 테스트 결과를 읽어 10페이지 이내의 평가 보고서를 만든다."""

import argparse
from html import escape
import json
from pathlib import Path
import re
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pymupdf

from reporting.supervisor_report import report_pages, write_pdf
from schemas import Candidate, EvaluationRecord, SourceRecord
from schemas.supervisor import ReportDraft, SupervisorControl


def restyle_saved_analysis(run, output, font_directory):
    """저장된 평가 값·출처·평가일을 그대로 사용하여 글꼴만 다시 적용한다."""
    source = Path(run["report"])
    payload = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
    with pymupdf.open(source) as original:
        match = re.search(r"평가일:\s*(\d{4}-\d{2}-\d{2})", original[0].get_text())
    if not match:
        raise ValueError("원본 보고서에서 평가일을 확인할 수 없습니다.")
    candidates = json.loads(Path("data/candidates.json").read_text(encoding="utf-8"))
    state = {
        "candidates": [Candidate.model_validate(c) for c in candidates],
        "evaluations": [EvaluationRecord.model_validate(e) for e in payload["evaluations"]],
        "sources": [SourceRecord.model_validate(s) for s in payload["sources"]],
        "routing_history": {k: SupervisorControl.model_validate(v) for k, v in run["routing"].items()},
        "run": SimpleNamespace(evaluation_date=match[1]),
    }
    draft = ReportDraft.model_validate(payload["draft"])
    write_pdf(report_pages(state, draft, font_directory=font_directory), output,
              font_directory=font_directory)


def attach_web_captures(document, directory):
    """원본 PNG를 보존하고 실제 웹 캡처를 A3 부록 한 페이지에 배치한다."""
    captures = [directory / "live/tracing-2.png",
                directory / "quality-repair/tracing-1.png",
                directory / "quality-repair/tracing-2.png"]
    missing = [str(path) for path in captures if not path.is_file()]
    if missing:
        raise FileNotFoundError("웹 캡처가 없습니다: " + ", ".join(missing))
    page = document.new_page(width=842, height=1191)

    def label(rect, html):
        result = page.insert_htmlbox(pymupdf.Rect(rect), html,
            css="body {font-size:10pt; color:#18364d; font-family:sans-serif;} p {margin:0;} ")
        if result[0] < 0:
            raise ValueError("캡처 부록 설명이 영역을 초과했습니다.")

    def screenshot(path, rect, clip):
        with pymupdf.open(path) as image:
            with pymupdf.open("pdf", image.convert_to_pdf()) as source:
                pixels = pymupdf.Pixmap(path)
                scale = pymupdf.Matrix(source[0].rect.width / pixels.width,
                                       source[0].rect.height / pixels.height)
                page.show_pdf_page(pymupdf.Rect(rect), source, 0,
                                   clip=pymupdf.Rect(clip) * scale)
        name = "ui-captures/" + path.relative_to(directory).as_posix()
        document.embfile_add(name, path.read_bytes(), filename=path.name,
                            desc="LangSmith 실제 웹 화면 원본 PNG")

    label((36, 28, 806, 60), "<h2 style='margin:0'>LangSmith 실제 웹 트레이싱 캡처</h2>")
    label((36, 62, 806, 102), "<p>2026-10-13 캡처. 본문의 기존 실행과 구분되는 새 워크스페이스 재실행입니다. "
          "아래는 웹 화면의 해당 영역이며, 전체 원본 PNG 3개를 PDF 파일 첨부로 함께 보존했습니다.</p>")
    label((36, 107, 806, 132), "<p><b>① 운영 재조사</b> - supervisor-newkey-20261013 / next_node=tech, repair=true</p>")
    screenshot(captures[0], (36, 137, 806, 581), (60, 175, 2130, 1370))
    label((36, 594, 405, 625), "<p><b>② 품질 실패</b> - passed=false, revision=0</p>")
    label((437, 594, 806, 625), "<p><b>③ 재작성 후 통과</b> - passed=true, revision=1</p>")
    screenshot(captures[1], (36, 628, 405, 869), (900, 300, 2130, 1105))
    screenshot(captures[2], (437, 628, 806, 869), (900, 300, 2130, 1105))
    label((36, 880, 405, 905), "<p><b>④ 보고서 수정 루프</b> - 동일한 품질 검증 실행</p>")
    # 같은 원본에서 트리 구간을 확대 표시한다. 원본 내용을 재작성하지 않는다.
    with pymupdf.open(captures[2]) as image:
        with pymupdf.open("pdf", image.convert_to_pdf()) as source:
            pixels = pymupdf.Pixmap(captures[2])
            scale = pymupdf.Matrix(source[0].rect.width / pixels.width,
                                   source[0].rect.height / pixels.height)
            page.show_pdf_page(pymupdf.Rect(36, 910, 405, 1130), source, 0,
                               clip=pymupdf.Rect(60, 1180, 895, 1690) * scale)
    base = "https://smith.langchain.com/o/e441cc68-4689-4954-b979-5465103d779b/projects/p/9e589d32-c32d-420b-8c45-5e5ba31438e9/r/"
    label((437, 910, 806, 1130),
          "<p>품질 검증은 결함을 의도적으로 주입한 controlled-quality-repair 실행입니다. "
          "운영 실행에서 품질 미달이 발생했다는 의미가 아닙니다.</p><br>"
          "<p>report → quality → revise_report → report → quality → finalize</p><br>"
          f"<p><a href='{base}cb5985fe-ed01-4199-b536-d3f667f1157c'>운영 트레이스 열기</a><br>"
          f"<a href='{base}2d29362d-3d37-4d6b-beba-0a6595792be3'>품질 재작성 트레이스 열기</a></p>")
    label((36, 1145, 806, 1174), "<p>부록은 가독성을 위해 A3로 구성했습니다. 원본: docs/supervisor/evidence/ui-captures/</p>")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory")
    parser.add_argument("--tests", default="artifacts/pytest.xml")
    parser.add_argument("--output", default="docs/supervisor/evidence/evaluation_report.pdf")
    parser.add_argument("--captures", type=Path, help="실제 LangSmith 웹 캡처 폴더")
    parser.add_argument("--font-directory", type=Path, help="Pretendard TTF 글꼴 폴더")
    parser.add_argument("--analysis-pdf", type=Path, help="동일 실행의 별도 서식 적용 보고서")
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
        "기존 투자 판정에는 이 완화 기준을 사용하지 않습니다.</p>" +
        ("<p>마지막 페이지에 실제 LangSmith 웹 트레이싱 캡처를 첨부했습니다. 본문의 실행은 기존 워크스페이스 기록이며, "
         "웹 캡처는 새 워크스페이스의 운영 재실행과 품질 재작성 검증입니다. 전체 원본 PNG도 PDF에 첨부했습니다.</p>" if args.captures else
         "<p>실제 LangSmith 웹 트레이싱 캡처는 보고서 PDF와 별도 PNG로 제출합니다. 운영 재조사와 품질 실패·재작성·통과를 "
         "촬영했습니다. 웹 캡처는 새 워크스페이스 실행이며 본문의 기존 실행과 구분합니다.</p>") +
        "<h2>REFERENCE</h2><p>과제 안내: Multi-Agent Orchestration, 2026-10-13.<br>"
        "기존 코드: github.com/asdasd571/physical_agent.<br>"
        "실행 근거: run.json, quality.json, LangSmith trace와 pytest.xml입니다.<br>"
        "다음 페이지는 해당 실행에서 생성한 후보 평가 보고서입니다.</p>",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    intro = output.with_name(".submission-intro.pdf")
    styled_analysis = output.with_name(".submission-analysis.pdf")
    write_pdf(pages, intro, font_directory=args.font_directory)
    try:
        analysis = args.analysis_pdf or run["report"]
        if args.font_directory and not args.analysis_pdf:
            restyle_saved_analysis(run, styled_analysis, args.font_directory)
            analysis = styled_analysis
        with pymupdf.open(intro) as document, pymupdf.open(analysis) as report:
            document.insert_pdf(report)
            if args.captures:
                attach_web_captures(document, args.captures)
            if len(document) > 10:
                raise ValueError("평가 보고서가 10페이지를 초과합니다.")
            document.save(output, garbage=4, deflate=True)
            print(f"{len(document)}페이지 평가 보고서를 생성했습니다: {output}")
    finally:
        intro.unlink(missing_ok=True)
        styled_analysis.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
