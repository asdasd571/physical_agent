"""Shared retrieval components for the investment-evaluation system."""

from .chunker import chunk_page, chunk_pages
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

__all__ = [
    "DocumentChunk",
    "DocumentPage",
    "DocumentType",
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
    "search_documents",
]
