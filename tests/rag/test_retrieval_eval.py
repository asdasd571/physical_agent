from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pytest

from evaluation.retrieval_eval import evaluate_retrieval, load_questions
from rag.models import DocumentType, RetrievedChunk


def result(doc_id: str, page: int, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chunk-{doc_id}-{page}-{rank}",
        source_id=f"source-{doc_id}",
        doc_id=doc_id,
        candidate_id=None,
        doc_type=DocumentType.PARENT,
        page=page,
        content="content",
        score=1.0 / rank,
    )


class FixedRetriever:
    def __init__(self, answers: dict[str, list[RetrievedChunk]]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str | None, Sequence[DocumentType] | None, int]] = []

    def search(
        self,
        query: str,
        candidate_id: str | None = None,
        doc_types: Sequence[DocumentType] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        self.calls.append((query, candidate_id, doc_types, top_k))
        return self.answers[query]


def write_questions(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "question_id": "q1",
                    "query": "rank three",
                    "candidate_id": " company-a ",
                    "doc_types": ["tech"],
                    "relevant_pages": [{"doc_id": "correct", "page": 7}],
                    "language_pair": "ko-en",
                },
                {
                    "question_id": "q2",
                    "query": "miss",
                    "relevant_pages": [{"doc_id": "missing", "page": 1}],
                    "language_pair": "en-en",
                },
            ]
        ),
        encoding="utf-8",
    )


def test_hit_rate_mrr_and_exact_page_match(tmp_path: Path) -> None:
    questions_path = tmp_path / "questions.json"
    write_questions(questions_path)
    questions = load_questions(questions_path)
    retriever = FixedRetriever(
        {
            "rank three": [
                result("wrong", 7, 1),
                result("correct", 6, 2),
                result("correct", 7, 3),
            ],
            "miss": [result("other", 1, 1)],
        }
    )

    report = evaluate_retrieval(retriever, questions)

    assert report.hit_rate_at_5 == 0.5
    assert report.mrr_at_5 == pytest.approx(1 / 6)
    assert report.questions[0].first_relevant_rank == 3
    assert report.questions[1].reciprocal_rank == 0.0
    assert report.by_language_pair["ko-en"]["hit_rate_at_5"] == 1.0
    assert retriever.calls[0][1:] == ("company-a", (DocumentType.TECH,), 5)


def test_question_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    questions_path = tmp_path / "questions.json"
    item = {
        "question_id": "duplicate",
        "query": "query",
        "relevant_pages": [{"doc_id": "doc", "page": 1}],
    }
    questions_path.write_text(json.dumps([item, item]), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate question_id"):
        load_questions(questions_path)


@pytest.mark.parametrize("page", [0, -1, True, "1"])
def test_question_loader_rejects_invalid_page(tmp_path: Path, page: object) -> None:
    questions_path = tmp_path / "questions.json"
    questions_path.write_text(
        json.dumps(
            [
                {
                    "question_id": "q1",
                    "query": "query",
                    "relevant_pages": [{"doc_id": "doc", "page": page}],
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="positive integer"):
        load_questions(questions_path)


def test_evaluation_is_fixed_to_top_five(tmp_path: Path) -> None:
    questions_path = tmp_path / "questions.json"
    write_questions(questions_path)
    with pytest.raises(ValueError, match="top_k=5"):
        evaluate_retrieval(FixedRetriever({}), load_questions(questions_path), top_k=10)
