from __future__ import annotations

from rag.models import DocumentType, RetrievedChunk
from rag.service import configure_search_backend, search_documents


class FakeBackend:
    def __init__(self) -> None:
        self.received: dict[str, object] = {}

    def search(self, query, candidate_id=None, doc_types=None, top_k=5):
        self.received = {
            "query": query,
            "candidate_id": candidate_id,
            "doc_types": doc_types,
            "top_k": top_k,
        }
        return [
            RetrievedChunk(
                chunk_id="chunk_a",
                source_id="src_a",
                doc_id="doc_a",
                candidate_id="company_a",
                doc_type=DocumentType.TECH,
                page=12,
                content="evidence",
                score=0.03,
            )
        ]


def test_public_search_contract_normalizes_doc_types() -> None:
    backend = FakeBackend()
    configure_search_backend(backend)

    results = search_documents(
        " 로봇핸드 성공률 ",
        candidate_id="company_a",
        doc_types=["tech"],
        top_k=5,
    )

    assert len(results) == 1
    assert backend.received == {
        "query": "로봇핸드 성공률",
        "candidate_id": "company_a",
        "doc_types": [DocumentType.TECH],
        "top_k": 5,
    }
