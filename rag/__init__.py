"""Shared retrieval components for the investment-evaluation system."""

from .loader import load_manifest_documents, load_pdf_pages
from .manifest import Manifest, load_manifest
from .models import DocumentPage, DocumentType, ManifestEntry, RetrievedChunk
from .service import (
    SearchBackendNotConfiguredError,
    configure_search_backend,
    search_documents,
)

__all__ = [
    "DocumentPage",
    "DocumentType",
    "Manifest",
    "ManifestEntry",
    "RetrievedChunk",
    "SearchBackendNotConfiguredError",
    "configure_search_backend",
    "load_manifest",
    "load_manifest_documents",
    "load_pdf_pages",
    "search_documents",
]
