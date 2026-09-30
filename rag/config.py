"""Shared RAG defaults with no environment-specific or absolute paths."""

from typing import Final


CHUNK_SIZE: Final[int] = 450
CHUNK_OVERLAP: Final[int] = 60
DENSE_TOP_K: Final[int] = 20
BM25_TOP_K: Final[int] = 20
RRF_K: Final[int] = 60
DEFAULT_TOP_K: Final[int] = 5
EMBEDDING_MODEL: Final[str] = "BAAI/bge-m3"
