"""Byte and canonical-JSON hashing helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def transform_fingerprint(job: dict[str, Any], worker_spec: dict[str, Any]) -> str:
    transform = job["transform"]
    binding = {
        "task_type": job["task_type"],
        "model": worker_spec.get("model_binding"),
        "software_environment": worker_spec["software_environment"],
        "parameters": transform.get("parameters", {}),
        "transform": {"name": transform["name"], "version": transform["version"]},
        "input_hashes": [item["sha256"] for item in job["inputs"]],
        "code_commit": worker_spec["code_commit"],
    }
    return sha256_json(binding)

