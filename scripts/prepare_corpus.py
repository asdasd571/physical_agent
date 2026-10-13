"""원본 manifest의 해시와 일치하는 공개 PDF만 내려받는다."""

import argparse
import csv
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/rag/manifest.csv")
    parser.add_argument("--available-only", action="store_true",
                        help="확인된 문서만 별도 local manifest에 기록합니다.")
    args = parser.parse_args()
    manifest = Path(args.manifest)
    with manifest.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    available, missing = [], []
    for row in rows:
        path = manifest.parent / row["local_path"]
        if not path.exists() and ".pdf" in row["source_url"].lower():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".download") as tmp:
                result = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                                         "--max-time", "45", row["source_url"], "--output", tmp.name],
                                        capture_output=True)
                data = Path(tmp.name).read_bytes()
                if result.returncode == 0 and data.startswith(b"%PDF") and sha256(data).hexdigest() == row["sha256"]:
                    path.write_bytes(data)
        if path.is_file() and sha256(path.read_bytes()).hexdigest() == row["sha256"]:
            available.append(row)
            print(f"확인: {row['doc_id']}", flush=True)
        else:
            missing.append(row["doc_id"])
            print(f"누락 또는 해시 불일치: {row['doc_id']}", flush=True)
    if args.available_only:
        target = manifest.with_name("manifest.available.local.csv")
        if not available:
            raise SystemExit("확인된 PDF가 없습니다.")
        with target.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(available)
        print(f"부분 자료 {len(available)}/{len(rows)}개: {target}")
    elif missing:
        raise SystemExit("원본 자료가 누락되었습니다. 원문 PDF를 복원하거나 --available-only로 부분 검증하십시오.")


if __name__ == "__main__":
    main()
