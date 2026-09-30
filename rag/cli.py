"""Command-line entry points for local indexing and hybrid search."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from .embeddings import BgeM3Embedder
from .indexing import index_manifest, load_hybrid_retriever
from .tokenizer import KiwiTechnicalTokenizer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agentic RAG utilities")
    commands = parser.add_subparsers(dest="command", required=True)

    index = commands.add_parser("index", help="build Dense and BM25 indexes")
    index.add_argument("--manifest", default="data/manifest.csv")
    index.add_argument("--index-dir", default="data/index")
    index.add_argument("--device", default=None)
    index.add_argument("--batch-size", type=int, default=8)

    search = commands.add_parser("search", help="search a persisted hybrid index")
    search.add_argument("query")
    search.add_argument("--index-dir", default="data/index")
    search.add_argument("--candidate-id", default=None)
    search.add_argument("--doc-type", action="append", dest="doc_types")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--device", default=None)
    return parser


def _run_index(args: argparse.Namespace) -> int:
    embedder = BgeM3Embedder(device=args.device, batch_size=args.batch_size)
    report = index_manifest(
        args.manifest,
        args.index_dir,
        embedder=embedder,
        sparse_tokenizer=KiwiTechnicalTokenizer(),
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


def _run_search(args: argparse.Namespace) -> int:
    from .models import DocumentType

    embedder = BgeM3Embedder(device=args.device)
    retriever = load_hybrid_retriever(
        args.index_dir,
        embedder=embedder,
        sparse_tokenizer=KiwiTechnicalTokenizer(),
    )
    doc_types = [DocumentType(value) for value in args.doc_types] if args.doc_types else None
    results = retriever.search(
        args.query,
        candidate_id=args.candidate_id,
        doc_types=doc_types,
        top_k=args.top_k,
    )
    for rank, result in enumerate(results, start=1):
        print(f"[{rank}]")
        print(f"score: {result.score:.10f}")
        print(f"doc_id: {result.doc_id}")
        print(f"candidate_id: {result.candidate_id}")
        print(f"doc_type: {result.doc_type.value}")
        print(f"page: {result.page}")
        print(f"source_id: {result.source_id}")
        print(f"content: {result.content}")
        print()
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    if args.command == "index":
        return _run_index(args)
    return _run_search(args)


if __name__ == "__main__":
    raise SystemExit(main())
