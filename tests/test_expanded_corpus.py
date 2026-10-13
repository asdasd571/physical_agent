import hashlib
import json
from pathlib import Path

import pymupdf
import pytest

from rag.manifest import load_manifest, ManifestError

ROOT = Path(__file__).resolve().parents[1]


def test_expanded_manifest_is_200_pages_and_original_unchanged():
    expanded = load_manifest(ROOT / "data/rag/manifest.expanded.csv")
    assert len(expanded.entries) == 17
    assert expanded.total_used_pages == 200
    assert load_manifest(ROOT / "data/rag/manifest.csv").total_used_pages == 161
    with pytest.raises(ManifestError):
        expanded.validate_page_budget(199)


def test_added_source_files_match_manifest_and_have_numeric_evidence():
    manifest = load_manifest(ROOT / "data/rag/manifest.expanded.csv")
    wanted = {"aidin_sensor_design_2025", "bmw_figure_customer_2026", "aidin_wrc_2024"}
    for entry in manifest.entries:
        if entry.doc_id not in wanted:
            continue
        path = manifest.resolve_local_path(entry)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry.sha256
        with pymupdf.open(path) as document:
            assert len(document) == entry.original_pages
            if entry.doc_id == "aidin_sensor_design_2025":
                assert "Aidin Robotics" in document[0].get_text()
                assert "15 N" in document[13].get_text()
            elif entry.doc_id == "bmw_figure_customer_2026":
                assert "90,000" in document[3].get_text()


def test_reviewed_evidence_has_real_pdf_pages_and_registered_citations():
    for candidate in ("arobot", "aidin_robotics", "figure_ai"):
        bundle = json.loads((ROOT / f"data/evidence/tech/{candidate}_expanded.json").read_text())
        registry = {s["source_id"]: s for s in bundle["sources"]}
        for record in bundle["records"]:
            assert record["source_ids"] and set(record["source_ids"]) <= registry.keys()
        for source in registry.values():
            if source["kind"] != "PDF":
                continue
            path = ROOT / source["local_path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
            with pymupdf.open(path) as document:
                assert 1 <= source["page"] <= len(document)
