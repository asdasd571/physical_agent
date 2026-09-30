"""Report node: archived State in, report location out; never performs search."""
from pathlib import Path

from schemas import GraphState, ReportResult
from reporting.renderer import ReportValidationError, render_investment_report, validate_report_inputs


def report_node(state: GraphState) -> dict:
    candidates = state["candidates"]
    evaluations = state["evaluations"]
    expected = [c.candidate_id for c in candidates]
    actual = [e.candidate_id for e in evaluations]
    if len(expected) != len(set(expected)) or set(expected) != set(actual) or len(actual) != len(expected):
        raise ReportValidationError("all candidates must be archived exactly once")
    if any(e.rule_version != state["run"].rule_version for e in evaluations):
        raise ReportValidationError("evaluation rule_version differs from run")
    _, used_sources = validate_report_inputs(evaluations, state.get("sources", []))
    output = state["run"].settings.get("report_output_path")
    if output is None:
        suffix = state["run"].run_id.split("-")[0]
        output = Path(__file__).resolve().parents[1] / "reporting/output" / f"investment_report_{state['run'].evaluation_date}_{suffix}.pdf"
    path = render_investment_report(evaluations, state.get("sources", []), Path(output),
                                    evaluation_date=state["run"].evaluation_date)
    return {"report": ReportResult(output_path=str(path), source_ids=[s.source_id for s in used_sources])}
