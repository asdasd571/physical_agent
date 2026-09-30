"""Persistent Kiwi-tokenized BM25 index for sparse retrieval."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Protocol, Sequence

from .models import DocumentChunk


BM25_INDEX_FILENAME = "bm25.json"
BM25_FORMAT_VERSION = 1


class SparseTokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class Bm25SearchResult:
    chunk: DocumentChunk
    score: float


class Bm25StoreError(RuntimeError):
    pass


class Bm25Store:
    """Small-corpus BM25 implementation suitable for the 200-page assignment."""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be positive")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.k1 = k1
        self.b = b
        self._chunks: list[DocumentChunk] = []
        self._documents: list[list[str]] = []
        self._term_frequencies: list[Counter[str]] = []
        self._document_frequencies: Counter[str] = Counter()
        self._average_document_length = 0.0
        self.last_indexing_seconds: float | None = None

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def chunks(self) -> tuple[DocumentChunk, ...]:
        return tuple(self._chunks)

    def build(
        self,
        chunks: Sequence[DocumentChunk],
        tokenizer: SparseTokenizer,
    ) -> None:
        if not chunks:
            raise ValueError("at least one chunk is required")
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("duplicate chunk_id found while building BM25 index")

        started = perf_counter()
        documents = [tokenizer.tokenize(chunk.content) for chunk in chunks]
        empty_indices = [index for index, tokens in enumerate(documents) if not tokens]
        if empty_indices:
            raise ValueError(f"tokenizer returned no tokens for chunk indices: {empty_indices}")
        self._set_corpus(chunks, documents)
        self.last_indexing_seconds = perf_counter() - started

    def _set_corpus(
        self,
        chunks: Sequence[DocumentChunk],
        documents: Sequence[Sequence[str]],
    ) -> None:
        self._chunks = list(chunks)
        self._documents = [list(tokens) for tokens in documents]
        self._term_frequencies = [Counter(tokens) for tokens in self._documents]
        self._document_frequencies = Counter()
        for tokens in self._documents:
            self._document_frequencies.update(set(tokens))
        self._average_document_length = sum(map(len, self._documents)) / len(
            self._documents
        )

    def _idf(self, term: str) -> float:
        document_count = len(self._documents)
        frequency = self._document_frequencies.get(term, 0)
        return math.log(1 + (document_count - frequency + 0.5) / (frequency + 0.5))

    def _score_document(self, query_terms: Counter[str], index: int) -> float:
        frequencies = self._term_frequencies[index]
        document_length = len(self._documents[index])
        length_normalization = 1 - self.b + self.b * (
            document_length / self._average_document_length
        )
        score = 0.0
        for term, query_frequency in query_terms.items():
            term_frequency = frequencies.get(term, 0)
            if term_frequency == 0:
                continue
            numerator = term_frequency * (self.k1 + 1)
            denominator = term_frequency + self.k1 * length_normalization
            score += self._idf(term) * (numerator / denominator) * query_frequency
        return score

    def search(
        self,
        query: str,
        tokenizer: SparseTokenizer,
        *,
        top_k: int = 20,
    ) -> list[Bm25SearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not self._chunks:
            return []
        query_tokens = tokenizer.tokenize(query)
        if not query_tokens:
            return []

        query_terms = Counter(query_tokens)
        scored = [
            (self._score_document(query_terms, index), index)
            for index in range(len(self._chunks))
        ]
        scored.sort(key=lambda item: (-item[0], self._chunks[item[1]].chunk_id))
        return [
            Bm25SearchResult(chunk=self._chunks[index], score=score)
            for score, index in scored[: min(top_k, len(scored))]
            if score > 0
        ]

    def save(self, directory: str | Path) -> None:
        if not self._chunks:
            raise Bm25StoreError("cannot save an empty BM25 index")
        target = Path(directory).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": BM25_FORMAT_VERSION,
            "k1": self.k1,
            "b": self.b,
            "chunk_count": len(self._chunks),
            "chunks": [chunk.model_dump() for chunk in self._chunks],
            "documents": self._documents,
        }
        (target / BM25_INDEX_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> "Bm25Store":
        path = Path(directory).expanduser().resolve() / BM25_INDEX_FILENAME
        if not path.is_file():
            raise Bm25StoreError(f"BM25 index not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format_version") != BM25_FORMAT_VERSION:
            raise Bm25StoreError("unsupported BM25 index format version")

        chunks = [DocumentChunk.model_validate(item) for item in payload.get("chunks", [])]
        documents = payload.get("documents", [])
        if payload.get("chunk_count") != len(chunks) or len(documents) != len(chunks):
            raise Bm25StoreError("BM25 index chunk metadata mismatch")
        if not chunks:
            raise Bm25StoreError("BM25 index is empty")

        store = cls(k1=float(payload["k1"]), b=float(payload["b"]))
        store._set_corpus(chunks, documents)
        return store
