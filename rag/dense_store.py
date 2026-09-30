"""Persistent FAISS Dense index with deterministic chunk metadata ordering."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

import numpy as np

from .embeddings import DenseEmbedder
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


def _chunk_to_dict(chunk: DocumentChunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "page_id": chunk.page_id,
        "source_id": chunk.source_id,
        "doc_id": chunk.doc_id,
        "candidate_id": chunk.candidate_id,
        "doc_type": chunk.doc_type.value,
        "page": chunk.page,
        "content": chunk.content,
        "token_start": chunk.token_start,
        "token_end": chunk.token_end,
        "token_count": chunk.token_count,
        "publisher": chunk.publisher,
        "title": chunk.title,
        "url": chunk.url,
        "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
        "local_path": str(chunk.local_path),
        "sha256": chunk.sha256,
        "metadata": chunk.metadata,
    }


def _chunk_from_dict(data: dict[str, Any]) -> DocumentChunk:
    published_at = data.get("published_at")
    return DocumentChunk(
        chunk_id=data["chunk_id"],
        page_id=data["page_id"],
        source_id=data["source_id"],
        doc_id=data["doc_id"],
        candidate_id=data.get("candidate_id"),
        doc_type=DocumentType(data["doc_type"]),
        page=int(data["page"]),
        content=data["content"],
        token_start=int(data["token_start"]),
        token_end=int(data["token_end"]),
        token_count=int(data["token_count"]),
        publisher=data["publisher"],
        title=data["title"],
        url=data.get("url"),
        published_at=date.fromisoformat(published_at) if published_at else None,
        local_path=Path(data["local_path"]),
        sha256=data["sha256"],
        metadata=data.get("metadata", {}),
    )


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
        top_k: int = 20,
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

        limit = min(top_k, len(self._chunks))
        scores, indices = self._index.search(vector, limit)
        return [
            DenseSearchResult(self._chunks[index], float(score))
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
            "chunks": [_chunk_to_dict(chunk) for chunk in self._chunks],
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
        chunks = [_chunk_from_dict(item) for item in payload.get("chunks", [])]
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
