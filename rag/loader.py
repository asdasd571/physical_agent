"""PDF page loader that keeps the original, 1-based PDF page numbers."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

from pypdf import PdfReader

from .manifest import Manifest, ManifestError
from .models import DocumentPage, ManifestEntry


class PDFLoadError(RuntimeError):
    """Raised when a manifest PDF cannot be verified or parsed."""


def calculate_sha256(path: str | Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_page_ranges(spec: str | None, total_pages: int) -> tuple[int, ...]:
    """Parse ``1-3;8,10`` into unique, ascending 1-based page numbers."""

    if not spec:
        return tuple(range(1, total_pages + 1))

    pages: set[int] = set()
    for token in re.split(r"[;,]", spec):
        token = token.strip()
        if not token:
            continue
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", token)
        if not match:
            raise PDFLoadError(f"invalid page_ranges token: {token!r}")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start > end:
            raise PDFLoadError(f"page range starts after it ends: {token!r}")
        if start < 1 or end > total_pages:
            raise PDFLoadError(
                f"page range {token!r} is outside PDF page count {total_pages}"
            )
        pages.update(range(start, end + 1))
    if not pages:
        raise PDFLoadError("page_ranges did not select any pages")
    return tuple(sorted(pages))


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf_pages(
    entry: ManifestEntry,
    pdf_path: str | Path | None = None,
    *,
    verify_sha256: bool = True,
    allow_empty_pages: bool = False,
) -> list[DocumentPage]:
    """Load selected PDF pages described by one manifest entry.

    A blank/scanned page fails explicitly by default so an OCR requirement cannot
    silently become missing evidence. OCR itself belongs to a later ingestion step.
    """

    path = Path(pdf_path or entry.local_path).expanduser().resolve()
    if not path.is_file():
        raise PDFLoadError(f"PDF not found for {entry.doc_id}: {path}")
    if path.suffix.lower() != ".pdf":
        raise PDFLoadError(f"local_path must point to a PDF: {path}")
    if verify_sha256:
        actual_hash = calculate_sha256(path)
        if actual_hash != entry.sha256:
            raise PDFLoadError(
                f"SHA256 mismatch for {entry.doc_id}: expected {entry.sha256}, "
                f"got {actual_hash}"
            )

    try:
        reader = PdfReader(path)
    except Exception as exc:
        raise PDFLoadError(f"failed to open PDF for {entry.doc_id}: {exc}") from exc

    actual_pages = len(reader.pages)
    if actual_pages != entry.original_pages:
        raise PDFLoadError(
            f"page count mismatch for {entry.doc_id}: manifest={entry.original_pages}, "
            f"PDF={actual_pages}"
        )
    selected_pages = parse_page_ranges(entry.page_ranges, actual_pages)
    if len(selected_pages) != entry.used_pages:
        raise PDFLoadError(
            f"used_pages mismatch for {entry.doc_id}: manifest={entry.used_pages}, "
            f"selected={len(selected_pages)}"
        )

    documents: list[DocumentPage] = []
    for original_page in selected_pages:
        try:
            content = _normalize_text(reader.pages[original_page - 1].extract_text() or "")
        except Exception as exc:
            raise PDFLoadError(
                f"failed to extract {entry.doc_id} page {original_page}: {exc}"
            ) from exc
        if not content:
            if allow_empty_pages:
                continue
            raise PDFLoadError(
                f"no text extracted from {entry.doc_id} page {original_page}; "
                "OCR and manual numeric/unit verification are required"
            )
        documents.append(
            DocumentPage(
                source_id=entry.source_id,
                doc_id=entry.doc_id,
                candidate_id=entry.candidate_id,
                doc_type=entry.doc_type,
                publisher=entry.publisher,
                title=entry.title or entry.doc_id,
                url=entry.source_url,
                published_at=entry.published_at,
                local_path=path,
                sha256=entry.sha256,
                page=original_page,
                content=content,
            )
        )
    return documents


def load_manifest_documents(
    manifest: Manifest,
    *,
    verify_sha256: bool = True,
) -> list[DocumentPage]:
    """Verify and load every manifest PDF after the global budget check."""

    manifest.validate_page_budget()
    pages: list[DocumentPage] = []
    for entry in manifest.entries:
        resolved_path = manifest.resolve_local_path(entry)
        try:
            pages.extend(
                load_pdf_pages(
                    entry,
                    resolved_path,
                    verify_sha256=verify_sha256,
                )
            )
        except PDFLoadError:
            raise
        except Exception as exc:
            raise ManifestError(f"failed to load {entry.doc_id}: {exc}") from exc
    return pages
