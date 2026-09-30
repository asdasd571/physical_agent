"""Persistent FAISS Dense index with deterministic chunk metadata ordering."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Sequence

import numpy as np

from .config import DENSE_TOP_K
from .embeddings import DenseEmbedder
from .filters import filter_chunk_indices
from .models import DocumentChunk, DocumentType


INDEX_FILENAME = "index.faiss"
METADATA_FILENAME = "chunks.json"
INDEX_FORMAT_VERSION = 1


class DenseStoreError(RuntimeError):
    pass


class DenseSearchResult:
    __slots__ = ("chunk", "score")

    def __init__(self, chunk: DocumentChunk, score: float) -> None:
        self.chunk = chunk
        self.score = score


def _import_faiss():
    try:
        import faiss
    except ImportError as exc:
        raise DenseStoreError(
            "faiss-cpu is required for the Dense index; install requirements.txt"
        ) from exc
    return faiss


class FaissDenseStore:
    """Cosine-similarity index backed by normalized FAISS inner product."""

    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        faiss = _import_faiss()
        self.dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)
        self._chunks: list[DocumentChunk] = []
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
        embedder: DenseEmbedder,
    ) -> None:
        if not chunks:
            raise ValueError("at least one chunk is required")
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("duplicate chunk_id found while building Dense index")
        if embedder.dimension != self.dimension:
            raise ValueError(
                f"embedding dimension mismatch: store={self.dimension}, "
                f"embedder={embedder.dimension}"
            )

        started = perf_counter()
        vectors = np.asarray(
            embedder.embed_documents([chunk.content for chunk in chunks]),
            dtype=np.float32,
        )
        expected_shape = (len(chunks), self.dimension)
        if vectors.shape != expected_shape:
            raise ValueError(
                f"embedding shape mismatch: expected {expected_shape}, got {vectors.shape}"
            )
        if not np.isfinite(vectors).all():
            raise ValueError("embedding contains NaN or infinite values")

        faiss = _import_faiss()
        vectors = np.ascontiguousarray(vectors)
        faiss.normalize_L2(vectors)
        self._index.reset()
        self._index.add(vectors)
        self._chunks = list(chunks)
        self.last_indexing_seconds = perf_counter() - started

    def search(
        self,
        query: str,
        embedder: DenseEmbedder,
        *,
        top_k: int = DENSE_TOP_K,
        candidate_id: str | None = None,
        doc_types: Sequence[DocumentType] | None = None,
    ) -> list[DenseSearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not self._chunks:
            return []
        if embedder.dimension != self.dimension:
            raise ValueError("query embedding dimension does not match Dense index")

        vector = np.asarray(embedder.embed_query(query), dtype=np.float32)
        if vector.shape != (self.dimension,):
            raise ValueError(
                f"query embedding shape mismatch: expected {(self.dimension,)}, "
                f"got {vector.shape}"
            )
        if not np.isfinite(vector).all():
            raise ValueError("query embedding contains NaN or infinite values")
        vector = np.ascontiguousarray(vector.reshape(1, -1))
        _import_faiss().normalize_L2(vector)

        eligible_indices = filter_chunk_indices(
            self._chunks,
            candidate_id=candidate_id,
            doc_types=doc_types,
        )
        if not eligible_indices:
            return []

        faiss = _import_faiss()
        if len(eligible_indices) == len(self._chunks):
            search_index = self._index
        else:
            filtered_vectors = np.ascontiguousarray(
                np.vstack([self._index.reconstruct(index) for index in eligible_indices]),
                dtype=np.float32,
            )
            search_index = faiss.IndexFlatIP(self.dimension)
            search_index.add(filtered_vectors)

        limit = min(top_k, len(eligible_indices))
        scores, indices = search_index.search(vector, limit)
        return [
            DenseSearchResult(
                self._chunks[
                    eligible_indices[index]
                    if len(eligible_indices) != len(self._chunks)
                    else index
                ],
                float(score),
            )
            for score, index in zip(scores[0], indices[0], strict=True)
            if index >= 0
        ]

    def save(self, directory: str | Path) -> None:
        if not self._chunks:
            raise DenseStoreError("cannot save an empty Dense index")
        target = Path(directory).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        _import_faiss().write_index(self._index, str(target / INDEX_FILENAME))
        payload = {
            "format_version": INDEX_FORMAT_VERSION,
            "dimension": self.dimension,
            "chunk_count": len(self._chunks),
            "chunks": [chunk.model_dump() for chunk in self._chunks],
        }
        (target / METADATA_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> "FaissDenseStore":
        target = Path(directory).expanduser().resolve()
        index_path = target / INDEX_FILENAME
        metadata_path = target / METADATA_FILENAME
        if not index_path.is_file() or not metadata_path.is_file():
            raise DenseStoreError(f"Dense index files not found: {target}")

        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        if payload.get("format_version") != INDEX_FORMAT_VERSION:
            raise DenseStoreError("unsupported Dense index format version")
        chunks = [DocumentChunk.model_validate(item) for item in payload.get("chunks", [])]
        if payload.get("chunk_count") != len(chunks):
            raise DenseStoreError("Dense metadata chunk_count mismatch")

        store = cls(int(payload["dimension"]))
        index = _import_faiss().read_index(str(index_path))
        if index.d != store.dimension:
            raise DenseStoreError("FAISS index dimension does not match metadata")
        if index.ntotal != len(chunks):
            raise DenseStoreError("FAISS vector count does not match chunk metadata")
        store._index = index
        store._chunks = chunks
        return store
