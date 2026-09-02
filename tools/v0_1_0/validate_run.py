#!/usr/bin/env python3
"""Validate semantic completeness of one V0.1.0 feasibility run."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path

import yaml


REQUIRED = {
    "run-binding.yaml", "environment.json", "gpu-inventory.json",
    "storage-inventory.json", "network-inventory.json", "model-source.json",
    "checkpoint-manifest.json", "software-lock.json", "commands.log",
    "metrics.json", "classification.yaml",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    errors = []
    missing = sorted(name for name in REQUIRED if not (args.run / name).is_file())
    if missing:
        errors.append(f"missing files: {', '.join(missing)}")
    for directory in ("errors", "notes"):
        if not (args.run / directory).is_dir():
            errors.append(f"missing directory: {directory}")
    if not missing:
        binding = yaml.safe_load((args.run / "run-binding.yaml").read_text(encoding="utf-8"))
        try:
            parsed = uuid.UUID(str(binding["run_id"]))
            if str(parsed) != args.run.name or str(parsed) != str(binding["run_id"]):
                errors.append("run_id must equal the canonical UUID directory name")
        except (KeyError, ValueError):
            errors.append("run_id is not a canonical UUID")
        manifest = json.loads((args.run / "checkpoint-manifest.json").read_text(encoding="utf-8"))
        if manifest.get("file_count") != len(manifest.get("files", [])):
            errors.append("checkpoint file_count does not match files")
        for item in manifest.get("files", []):
            if len(item.get("sha256", "")) != hashlib.sha256().digest_size * 2:
                errors.append(f"invalid SHA-256 for {item.get('path')}")
        classification = yaml.safe_load((args.run / "classification.yaml").read_text(encoding="utf-8"))
        if classification.get("result") not in {"PASS", "CONDITIONAL", "BLOCKED", "FAIL"}:
            errors.append("invalid feasibility classification")
    print(json.dumps({"run": str(args.run), "valid": not errors, "errors": errors}, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
