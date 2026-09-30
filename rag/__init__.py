"""Shared retrieval components for the investment-evaluation system."""

from .bm25_store import Bm25SearchResult, Bm25Store
from .chunker import chunk_page, chunk_pages
from .dense_store import DenseSearchResult, FaissDenseStore
from .embeddings import BgeM3Embedder, DenseEmbedder, EmbeddingMetrics
from .fusion import reciprocal_rank_fusion
from .loader import load_manifest_documents, load_pdf_pages
from .manifest import Manifest, load_manifest
from .models import (
    DocumentChunk,
    DocumentPage,
    DocumentType,
    ManifestEntry,
    RetrievedChunk,
)
from .service import (
    SearchBackendNotConfiguredError,
    configure_search_backend,
    search_documents,
)
from .tokenizer import KiwiTechnicalTokenizer, normalize_search_text

__all__ = [
    "Bm25SearchResult",
    "Bm25Store",
    "DocumentChunk",
    "DocumentPage",
    "DocumentType",
    "DenseEmbedder",
    "DenseSearchResult",
    "EmbeddingMetrics",
    "BgeM3Embedder",
    "FaissDenseStore",
    "KiwiTechnicalTokenizer",
    "Manifest",
    "ManifestEntry",
    "RetrievedChunk",
    "SearchBackendNotConfiguredError",
    "chunk_page",
    "chunk_pages",
    "configure_search_backend",
    "load_manifest",
    "load_manifest_documents",
    "load_pdf_pages",
    "normalize_search_text",
    "reciprocal_rank_fusion",
    "search_documents",
]
