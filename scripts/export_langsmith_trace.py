"""LangSmith에 저장된 실제 노드 실행을 JSON과 PNG로 내보낸다.

PNG는 API 응답으로 렌더링한 기록이며 LangSmith 웹 화면 캡처와 구분한다.
"""

import argparse
from html import escape
import json
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client
import pymupdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_manifest")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    load_dotenv(override=True)
    manifest = json.loads(Path(args.run_manifest).read_text(encoding="utf-8"))
    root = Client().read_run(manifest["trace_id"], load_child_runs=True)
    rows = []

    def visit(run, depth):
        for child in sorted(run.child_runs or [], key=lambda r: r.start_time):
            # 라우터 내부 호출은 제외하고 그래프의 실제 노드 호출을 기록한다.
            metadata = (child.extra or {}).get("metadata", {})
            if metadata.get("langgraph_node") == child.name:
                duration = (child.end_time - child.start_time).total_seconds() if child.end_time else None
                outputs = child.outputs or {}
                decision = (outputs.get("supervisor") or {}).get("decisions", []) if isinstance(outputs, dict) else []
                rows.append({"id": str(child.id), "name": child.name, "start_time": child.start_time.isoformat(),
                             "seconds": duration, "status": child.status,
                             "decision": decision[-1] if child.name == "supervisor" and decision else None,
                             "quality": outputs.get("quality") if child.name == "quality" else None})
            visit(child, depth + 1)
    visit(root, 0)
    if not rows:
        raise RuntimeError("LangSmith의 노드 실행 기록이 없습니다. 수집 완료 후 다시 실행하십시오.")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    payload = {"origin": "LangSmith API", "root_run_id": str(root.id), "url": root.url,
               "status": root.status, "run_name": root.name, "controlled_fault": manifest.get("controlled_fault", False),
               "nodes": rows}
    (output / "langsmith-trace.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    for page_index, offset in enumerate(range(0, len(rows), 16), 1):
        html = f"<h1>LangSmith 실행 추적 — {page_index}</h1><p>원본 Run ID: {escape(str(root.id))}</p>"
        html += f"<p>실행: {escape(root.name)} / 상태: {escape(root.status)}</p>"
        html += "<p>LangSmith API에 저장된 실제 노드 기록입니다. 웹 UI 캡처가 아닙니다.</p>"
        if payload["controlled_fault"]:
            html += "<p>통제된 결함 주입 시나리오입니다. 운영 결과와 구분합니다.</p>"
        html += "<table><tr><th>순서</th><th>노드 / 판단</th><th>시간(초)</th></tr>"
        for index, row in enumerate(rows[offset:offset + 16], offset + 1):
            detail = ""
            if row["decision"]:
                d = row["decision"]
                detail = f"<br>{escape(d['candidate_id'])} → {escape(d['route'])}<br>{escape(d['reason'][:170])}"
            if row["quality"]:
                q = row["quality"]
                failed = [key for key, value in q.items() if isinstance(value, dict) and value.get("passed") is False]
                detail = f"<br>개정 {q['revision']} / {'통과' if q['passed'] else '미달'} / {escape(', '.join(failed))}"
            html += f"<tr><td>{index}</td><td><b>{escape(row['name'])}</b>{detail}</td><td>{row['seconds']:.3f}</td></tr>"
        html += "</table>"
        story = pymupdf.Story(html=html, user_css="body {font-size:10pt;} h1 {font-size:18pt;} table {width:100%;} td,th {padding:5pt; border-bottom:1px solid #ddd;} ")
        pdf_path = output / f".trace-{page_index}.pdf"
        writer = pymupdf.DocumentWriter(str(pdf_path))
        height = min(1500, 300 + len(rows[offset:offset + 16]) * 75)
        page = pymupdf.Rect(0, 0, 800, height)
        more, _ = story.place(pymupdf.Rect(30, 30, 770, height - 30))
        if more:
            raise RuntimeError("추적 이미지 영역을 초과했습니다.")
        device = writer.begin_page(page)
        story.draw(device)
        writer.end_page()
        writer.close()
        with pymupdf.open(pdf_path) as document:
            document[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(output / f"tracing-{page_index}.png")
        pdf_path.unlink()
    print(json.dumps({"url": root.url, "node_count": len(rows), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
