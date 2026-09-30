import json
from pathlib import Path

from evaluation.metric_coverage import run_coverage, validate_coverage_spec
from evaluation.retrieval_eval import load_questions
from rag.manifest import load_manifest


def _manifest_pages() -> set[tuple[str, int]]:
    manifest = load_manifest("data/rag/manifest.csv")
    pages: set[tuple[str, int]] = set()
    for entry in manifest.entries:
        for part in (entry.page_ranges or f"1-{entry.original_pages}").split(";"):
            bounds = [int(value) for value in part.split("-", 1)]
            pages.update((entry.doc_id, page) for page in range(bounds[0], bounds[-1] + 1))
    return pages


def test_operating_manifest_and_40_question_labels_are_consistent() -> None:
    manifest = load_manifest("data/rag/manifest.csv")
    assert manifest.total_used_pages <= 200
    assert manifest.pages_by_type[next(t for t in manifest.pages_by_type if t.value == "parent")] > 0

    questions = load_questions("evaluation/retrieval_questions.json")
    assert len(questions) == 40
    assert sum(q.question_id.startswith("tech-") for q in questions) == 16
    assert sum(q.question_id.startswith("market-") for q in questions) == 12
    assert sum(q.question_id.startswith("parent-") for q in questions) == 12
    available = _manifest_pages()
    assert all(
        (page.doc_id, page.page) in available
        for question in questions
        for page in question.relevant_pages
    )


def test_metric_coverage_spec_has_all_metrics_and_valid_manifest_pages() -> None:
    spec = json.loads(Path("evaluation/metric_coverage.json").read_text(encoding="utf-8"))
    validate_coverage_spec(spec, "data/rag/manifest.csv")
    results = dict(run_coverage(spec))
    assert len(results) == 16
    assert results["S2"] == "DECLARED"
    assert results["K2"] == "MISSING"
