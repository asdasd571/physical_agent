"""Download the official STEP 8 sample PDF and create a local manifest."""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.request import urlopen

from pypdf import PdfReader

from rag.loader import calculate_sha256


SOURCE_URL = (
    "https://www.skinnovation.com/files/sustainability/esg_report/"
    "2022%20SKI%20ESG%20Report_eng.pdf"
)
EXPECTED_SHA256 = "e69629ffc7176568cbceea738970a148cc28dc7709025696d2acd5f3a0c94071"
EXPECTED_PAGES = 177
PDF_PATH = Path("data/rag/documents/parent/sk_2022_esg_report_eng.pdf")
MANIFEST_PATH = Path("data/rag/manifest.step8.local.csv")


def main() -> int:
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PDF_PATH.is_file():
        with urlopen(SOURCE_URL, timeout=120) as response:
            PDF_PATH.write_bytes(response.read())

    sha256 = calculate_sha256(PDF_PATH)
    page_count = len(PdfReader(PDF_PATH).pages)
    if sha256 != EXPECTED_SHA256:
        raise RuntimeError(
            f"sample PDF SHA256 changed: expected {EXPECTED_SHA256}, got {sha256}"
        )
    if page_count != EXPECTED_PAGES:
        raise RuntimeError(
            f"sample PDF page count changed: expected {EXPECTED_PAGES}, got {page_count}"
        )

    fields = [
        "doc_id",
        "publisher",
        "published_at",
        "source_url",
        "sha256",
        "original_pages",
        "used_pages",
        "doc_type",
        "candidate_id",
        "local_path",
        "title",
        "page_ranges",
    ]
    row = {
        "doc_id": "ski_esg_report_2022",
        "publisher": "SK Innovation",
        "published_at": "2022-01-01",
        "source_url": SOURCE_URL,
        "sha256": sha256,
        "original_pages": page_count,
        "used_pages": 2,
        "doc_type": "parent",
        "candidate_id": "COMMON",
        "local_path": "documents/parent/sk_2022_esg_report_eng.pdf",
        "title": "SK Innovation ESG Report 2022",
        "page_ranges": "101-102",
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)

    print(f"PDF: {PDF_PATH}")
    print(f"SHA256: {sha256}")
    print(f"Pages: {page_count} (using original pages 101-102)")
    print(f"Manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
