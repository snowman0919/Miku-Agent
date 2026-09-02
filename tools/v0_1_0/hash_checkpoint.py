#!/usr/bin/env python3
"""Hash actual checkpoint file bytes, never cache symlink targets implicitly."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    root = args.checkpoint.resolve(strict=True)
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            resolved = path.resolve(strict=True)
            files.append({"path": str(path.relative_to(root)), "size_bytes": resolved.stat().st_size, "sha256": sha256(resolved)})
    manifest = {
        "schema_version": 1,
        "repository": args.repository,
        "revision": args.revision,
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "file_count": len(files),
        "files": files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
