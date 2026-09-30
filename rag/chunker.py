"""Token-based page chunking without crossing original PDF page boundaries."""

from __future__ import annotations

import hashlib
from typing import Iterable, Protocol, Sequence

from .models import DocumentChunk, DocumentPage, stable_id


DEFAULT_CHUNK_SIZE = 450
DEFAULT_CHUNK_OVERLAP = 60


class TokenCodec(Protocol):
    """Minimal tokenizer contract implemented by Hugging Face tokenizers."""

    def encode(
        self,
        text: str,
        *,
        add_special_tokens: bool = False,
    ) -> list[int]: ...

    def decode(
        self,
        token_ids: Sequence[int],
        *,
        skip_special_tokens: bool = True,
        clean_up_tokenization_spaces: bool = False,
    ) -> str: ...


def _validate_settings(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must not be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_page(
    page: DocumentPage,
    tokenizer: TokenCodec,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Split one page into token chunks while retaining original provenance.

    Special tokens are excluded because chunk size describes evidence text, not
    model-specific wrapper tokens. The same tokenizer must later be used for the
    BGE-M3 indexing pipeline.
    """

    _validate_settings(chunk_size, overlap)
    token_ids = tokenizer.encode(page.content, add_special_tokens=False)
    if not token_ids:
        raise ValueError(f"tokenizer returned no tokens for {page.doc_id} p.{page.page}")

    chunks: list[DocumentChunk] = []
    stride = chunk_size - overlap
    for token_start in range(0, len(token_ids), stride):
        token_end = min(token_start + chunk_size, len(token_ids))
        chunk_token_ids = token_ids[token_start:token_end]
        content = tokenizer.decode(
            chunk_token_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        ).strip()
        if not content:
            raise ValueError(
                f"tokenizer decoded an empty chunk for {page.doc_id} p.{page.page} "
                f"tokens {token_start}:{token_end}"
            )

        chunk_id = stable_id(
            "chunk",
            page.page_id,
            token_start,
            token_end,
            _content_digest(content),
        )
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                page_id=page.page_id,
                source_id=page.source_id,
                doc_id=page.doc_id,
                candidate_id=page.candidate_id,
                doc_type=page.doc_type,
                page=page.page,
                content=content,
                token_start=token_start,
                token_end=token_end,
                token_count=token_end - token_start,
                publisher=page.publisher,
                title=page.title,
                url=page.url,
                published_at=page.published_at,
                local_path=page.local_path,
                sha256=page.sha256,
                metadata=dict(page.metadata),
            )
        )
        if token_end == len(token_ids):
            break
    return chunks


def chunk_pages(
    pages: Iterable[DocumentPage],
    tokenizer: TokenCodec,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Chunk pages independently so no chunk can span two PDF pages."""

    _validate_settings(chunk_size, overlap)
    chunks: list[DocumentChunk] = []
    for page in pages:
        chunks.extend(
            chunk_page(
                page,
                tokenizer,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
    return chunks
