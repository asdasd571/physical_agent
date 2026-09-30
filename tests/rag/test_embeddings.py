from __future__ import annotations

import numpy as np
import pytest

from rag.embeddings import BgeM3Embedder


class FakeSentenceTransformer:
    def __init__(self) -> None:
        self.tokenizer = object()

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts, **kwargs):
        vectors = [[float(len(text)), 1.0, 0.0] for text in texts]
        return np.asarray(vectors, dtype=np.float32)


def loaded_embedder() -> BgeM3Embedder:
    embedder = BgeM3Embedder(batch_size=2)
    embedder._model = FakeSentenceTransformer()
    embedder._dimension = 3
    embedder._model_load_seconds = 0.01
    return embedder


def test_embed_documents_returns_float32_matrix() -> None:
    vectors = loaded_embedder().embed_documents(["one", "two"])

    assert vectors.shape == (2, 3)
    assert vectors.dtype == np.float32


def test_embed_query_returns_one_vector() -> None:
    vector = loaded_embedder().embed_query("robot hand")

    assert vector.shape == (3,)


def test_empty_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        loaded_embedder().embed_query("  ")


def test_exact_model_tokenizer_is_exposed() -> None:
    embedder = loaded_embedder()
    assert embedder.tokenizer is embedder._model.tokenizer
