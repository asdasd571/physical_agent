"""Load a persisted index and verify the public Agent-facing RAG contract."""

from __future__ import annotations

import argparse
import json

from rag import (
    BgeM3Embedder,
    KiwiTechnicalTokenizer,
    configure_search_backend,
    load_hybrid_retriever,
    search_documents,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an Agent-style RAG call")
    parser.add_argument("query")
    parser.add_argument("--index-dir", default="data/rag/index")
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument("--doc-type", action="append", dest="doc_types")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--device", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    embedder = BgeM3Embedder(device=args.device)
    retriever = load_hybrid_retriever(
        args.index_dir,
        embedder=embedder,
        sparse_tokenizer=KiwiTechnicalTokenizer(),
    )
    configure_search_backend(retriever)

    # This is the same public call that tech, market, and synergy Agents use.
    results = search_documents(
        query=args.query,
        candidate_id=args.candidate_id,
        doc_types=args.doc_types,
        top_k=args.top_k,
    )
    print(
        json.dumps(
            [result.model_dump() for result in results],
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
