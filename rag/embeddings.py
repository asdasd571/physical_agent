"""BGE-M3 Dense embedding with lazy local model loading."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, Sequence

import numpy as np
from numpy.typing import NDArray


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


class DenseEmbedder(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]: ...

    def embed_query(self, query: str) -> NDArray[np.float32]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingMetrics:
    model_load_seconds: float | None
    last_embedding_seconds: float | None


class BgeM3Embedder:
    """Local BAAI/bge-m3 wrapper using Dense vectors only.

    ``SentenceTransformer`` is imported lazily so manifest and loader commands do
    not pay the model import/load cost. Embeddings are L2-normalized for cosine
    similarity through FAISS inner-product search.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        *,
        device: str | None = None,
        batch_size: int = 8,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model = None
        self._dimension: int | None = None
        self._model_load_seconds: float | None = None
        self._last_embedding_seconds: float | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for BGE-M3; "
                "install requirements.txt"
            ) from exc

        started = perf_counter()
        self._model = SentenceTransformer(self.model_name, device=self.device)
        get_dimension = getattr(self._model, "get_embedding_dimension", None)
        if get_dimension is None:
            get_dimension = self._model.get_sentence_embedding_dimension
        self._dimension = int(get_dimension())
        self._model_load_seconds = perf_counter() - started

    @property
    def tokenizer(self):
        """Expose the exact BGE-M3 tokenizer used by the STEP 3 chunker."""

        self.load()
        return self._model.tokenizer

    @property
    def dimension(self) -> int:
        self.load()
        assert self._dimension is not None
        return self._dimension

    @property
    def metrics(self) -> EmbeddingMetrics:
        return EmbeddingMetrics(
            model_load_seconds=self._model_load_seconds,
            last_embedding_seconds=self._last_embedding_seconds,
        )

    def _encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        if not texts:
            dimension = self.dimension
            return np.empty((0, dimension), dtype=np.float32)
        if any(not text.strip() for text in texts):
            raise ValueError("embedding text must not be empty")

        self.load()
        started = perf_counter()
        vectors = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        self._last_embedding_seconds = perf_counter() - started
        array = np.asarray(vectors, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.ndim != 2 or array.shape[1] != self.dimension:
            raise ValueError(f"unexpected embedding shape: {array.shape}")
        if not np.isfinite(array).all():
            raise ValueError("embedding contains NaN or infinite values")
        return array

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return self._encode(texts)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        if not query.strip():
            raise ValueError("query must not be empty")
        return self._encode([query])[0]
