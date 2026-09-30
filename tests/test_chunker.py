from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pytest

from rag.chunker import chunk_page, chunk_pages
from rag.models import DocumentPage, DocumentType


class WordTokenCodec:
    """Deterministic test codec; production will use the BGE-M3 tokenizer."""

    def __init__(self, vocabulary: list[str]) -> None:
        self.tokens = vocabulary
        self.token_to_id = {token: index for index, token in enumerate(vocabulary)}

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        return [self.token_to_id[token] for token in text.split()]

    def decode(
        self,
        token_ids: Sequence[int],
        *,
        skip_special_tokens: bool = True,
        clean_up_tokenization_spaces: bool = False,
    ) -> str:
        return " ".join(self.tokens[token_id] for token_id in token_ids)


def make_page(*, page_number: int, tokens: list[str]) -> DocumentPage:
    return DocumentPage(
        source_id="src_test",
        doc_id="doc_test",
        candidate_id="company_a",
        doc_type=DocumentType.TECH,
        publisher="Test Publisher",
        title="Robot Hand Test Report",
        url="https://example.com/report.pdf",
        published_at=None,
        local_path=Path("data/documents/tech/test.pdf"),
        sha256="a" * 64,
        page=page_number,
        content=" ".join(tokens),
    )


def test_short_page_creates_one_chunk() -> None:
    tokens = [f"t{i}" for i in range(100)]
    chunks = chunk_page(make_page(page_number=3, tokens=tokens), WordTokenCodec(tokens))

    assert len(chunks) == 1
    assert chunks[0].token_count == 100
    assert chunks[0].content == " ".join(tokens)


def test_long_page_uses_450_tokens_with_60_token_overlap() -> None:
    tokens = [f"t{i}" for i in range(600)]
    chunks = chunk_page(make_page(page_number=12, tokens=tokens), WordTokenCodec(tokens))

    assert len(chunks) == 2
    assert chunks[0].token_start == 0
    assert chunks[0].token_end == 450
    assert chunks[1].token_start == 390
    assert chunks[1].token_end == 600
    assert chunks[0].content.split()[-60:] == chunks[1].content.split()[:60]


def test_chunks_keep_original_page_and_source_metadata() -> None:
    first_tokens = [f"a{i}" for i in range(500)]
    second_tokens = [f"b{i}" for i in range(500)]
    codec = WordTokenCodec(first_tokens + second_tokens)
    chunks = chunk_pages(
        [
            make_page(page_number=7, tokens=first_tokens),
            make_page(page_number=19, tokens=second_tokens),
        ],
        codec,
    )

    assert {chunk.page for chunk in chunks} == {7, 19}
    assert all(chunk.source_id == "src_test" for chunk in chunks)
    assert all(chunk.doc_id == "doc_test" for chunk in chunks)
    assert all(not ("a0" in chunk.content and "b0" in chunk.content) for chunk in chunks)


def test_same_input_creates_same_chunk_ids() -> None:
    tokens = [f"t{i}" for i in range(600)]
    page = make_page(page_number=12, tokens=tokens)
    codec = WordTokenCodec(tokens)

    first = chunk_page(page, codec)
    second = chunk_page(page, codec)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (450, -1), (450, 450), (450, 451)],
)
def test_invalid_chunk_settings_are_rejected(chunk_size: int, overlap: int) -> None:
    tokens = ["token"]
    with pytest.raises(ValueError):
        chunk_page(
            make_page(page_number=1, tokens=tokens),
            WordTokenCodec(tokens),
            chunk_size=chunk_size,
            overlap=overlap,
        )
