"""End-to-end document indexing and persisted HybridRetriever loading."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

from .bm25_store import Bm25Store, SparseTokenizer
from .chunker import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, chunk_pages
from .dense_store import FaissDenseStore
from .embeddings import BgeM3Embedder, DenseEmbedder
from .loader import load_manifest_documents
from .manifest import load_manifest
from .models import DocumentChunk
from .retriever import HybridRetriever
from .tokenizer import KiwiTechnicalTokenizer


DENSE_DIRECTORY = "dense"
BM25_DIRECTORY = "bm25"
INDEX_RUN_FILENAME = "index_run.json"
INDEX_RUN_FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class IndexBuildReport:
    document_count: int
    page_count: int
    chunk_count: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    model_load_seconds: float | None
    dense_indexing_seconds: float | None
    bm25_indexing_seconds: float | None
    total_indexing_seconds: float


def build_indexes(
    chunks: Sequence[DocumentChunk],
    index_directory: str | Path,
    *,
    embedder: DenseEmbedder,
    sparse_tokenizer: SparseTokenizer,
    document_count: int,
    page_count: int,
    embedding_model: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> IndexBuildReport:
    """Build and persist Dense and BM25 indexes over the same chunk corpus."""

    if not chunks:
        raise ValueError("at least one chunk is required for indexing")
    target = Path(index_directory).expanduser().resolve()
    started = perf_counter()

    dense_store = FaissDenseStore(dimension=embedder.dimension)
    dense_store.build(chunks, embedder)
    bm25_store = Bm25Store()
    bm25_store.build(chunks, sparse_tokenizer)

    dense_store.save(target / DENSE_DIRECTORY)
    bm25_store.save(target / BM25_DIRECTORY)
    metrics = getattr(embedder, "metrics", None)
    report = IndexBuildReport(
        document_count=document_count,
        page_count=page_count,
        chunk_count=len(chunks),
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        model_load_seconds=getattr(metrics, "model_load_seconds", None),
        dense_indexing_seconds=dense_store.last_indexing_seconds,
        bm25_indexing_seconds=bm25_store.last_indexing_seconds,
        total_indexing_seconds=perf_counter() - started,
    )
    payload = {
        "format_version": INDEX_RUN_FORMAT_VERSION,
        **asdict(report),
    }
    target.mkdir(parents=True, exist_ok=True)
    (target / INDEX_RUN_FILENAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def index_manifest(
    manifest_path: str | Path = "data/rag/manifest.csv",
    index_directory: str | Path = "data/rag/index",
    *,
    embedder: BgeM3Embedder | None = None,
    sparse_tokenizer: KiwiTechnicalTokenizer | None = None,
) -> IndexBuildReport:
    """Run manifest validation, PDF loading, chunking, and index persistence."""

    manifest = load_manifest(manifest_path)
    pages = load_manifest_documents(manifest)
    model = embedder or BgeM3Embedder()
    kiwi = sparse_tokenizer or KiwiTechnicalTokenizer()
    chunks = chunk_pages(pages, model.tokenizer)
    return build_indexes(
        chunks,
        index_directory,
        embedder=model,
        sparse_tokenizer=kiwi,
        document_count=len(manifest.entries),
        page_count=len(pages),
        embedding_model=model.model_name,
    )


def load_hybrid_retriever(
    index_directory: str | Path = "data/rag/index",
    *,
    embedder: DenseEmbedder,
    sparse_tokenizer: SparseTokenizer,
) -> HybridRetriever:
    """Restore persisted Dense and BM25 stores and create a retriever."""

    target = Path(index_directory).expanduser().resolve()
    run_path = target / INDEX_RUN_FILENAME
    if not run_path.is_file():
        raise FileNotFoundError(f"index run metadata not found: {run_path}")
    payload: dict[str, Any] = json.loads(run_path.read_text(encoding="utf-8"))
    if payload.get("format_version") != INDEX_RUN_FORMAT_VERSION:
        raise ValueError("unsupported index run format version")
    dense_store = FaissDenseStore.load(target / DENSE_DIRECTORY)
    bm25_store = Bm25Store.load(target / BM25_DIRECTORY)
    if embedder.dimension != dense_store.dimension:
        raise ValueError("loaded embedding model dimension does not match saved index")
    return HybridRetriever(dense_store, bm25_store, embedder, sparse_tokenizer)
