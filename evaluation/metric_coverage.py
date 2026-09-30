"""Check whether investment metrics have retrievable raw-value evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rag.embeddings import BgeM3Embedder
from rag.indexing import load_hybrid_retriever
from rag.manifest import load_manifest
from rag.models import DocumentType
from rag.tokenizer import KiwiTechnicalTokenizer


def _selected_pages(entry: Any) -> set[int]:
    if not entry.page_ranges:
        return set(range(1, entry.original_pages + 1))
    pages: set[int] = set()
    for part in entry.page_ranges.split(";"):
        bounds = part.split("-", 1)
        start = int(bounds[0])
        end = int(bounds[-1])
        pages.update(range(start, end + 1))
    return pages


def validate_coverage_spec(spec: list[dict[str, Any]], manifest_path: str | Path) -> None:
    manifest = load_manifest(manifest_path)
    available = {
        (entry.doc_id, page)
        for entry in manifest.entries
        for page in _selected_pages(entry)
    }
    expected = {"T1", "T2", "K1", "K2", "K3", "S1", "S2", "P1", "R1", "R2", "R3", "M1", "F1", "F2", "F3", "F4"}
    actual = {item.get("metric") for item in spec}
    if actual != expected:
        raise ValueError(f"coverage metrics mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    for item in spec:
        status = item.get("status")
        if status == "OK":
            if not item.get("query") or not item.get("relevant_pages"):
                raise ValueError(f"{item['metric']} OK requires query and relevant_pages")
            for page in item["relevant_pages"]:
                key = (page["doc_id"], page["page"])
                if key not in available:
                    raise ValueError(f"{item['metric']} answer page is not in manifest: {key}")
        elif status != "MISSING" or not item.get("reason"):
            raise ValueError(f"{item.get('metric')} must be OK or explained MISSING")


def run_coverage(spec: list[dict[str, Any]], retriever: Any | None = None) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for item in spec:
        if item["status"] == "MISSING":
            results.append((item["metric"], "MISSING"))
            continue
        if retriever is None:
            results.append((item["metric"], "DECLARED"))
            continue
        returned = retriever.search(
            item["query"],
            candidate_id=item.get("candidate_id"),
            doc_types=[DocumentType(value) for value in item.get("doc_types", [])] or None,
            top_k=5,
        )
        expected = {(p["doc_id"], p["page"]) for p in item["relevant_pages"]}
        hit = any((chunk.doc_id, chunk.page) in expected for chunk in returned)
        results.append((item["metric"], "OK" if hit else "NOT_IN_TOP5"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default="evaluation/metric_coverage.json")
    parser.add_argument("--manifest", default="data/rag/manifest.csv")
    parser.add_argument("--index-dir")
    parser.add_argument("--device")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    validate_coverage_spec(spec, args.manifest)
    retriever = None
    if args.index_dir:
        retriever = load_hybrid_retriever(
            args.index_dir,
            embedder=BgeM3Embedder(device=args.device),
            sparse_tokenizer=KiwiTechnicalTokenizer(),
        )
    for metric, status in run_coverage(spec, retriever):
        print(f"{metric:<3} {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
