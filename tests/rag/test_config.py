from rag.config import (
    BM25_TOP_K,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_TOP_K,
    DENSE_TOP_K,
    EMBEDDING_MODEL,
    RRF_K,
)


def test_rag_defaults_match_the_approved_design() -> None:
    assert CHUNK_SIZE == 450
    assert CHUNK_OVERLAP == 60
    assert DENSE_TOP_K == 20
    assert BM25_TOP_K == 20
    assert RRF_K == 60
    assert DEFAULT_TOP_K == 5
    assert EMBEDDING_MODEL == "BAAI/bge-m3"
