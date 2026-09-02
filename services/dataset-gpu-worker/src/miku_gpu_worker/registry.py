"""Pinned model registry validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import WorkerError

IMMUTABLE_REVISION = re.compile(r"^[0-9a-f]{40,64}$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MODEL_REGISTRY = REPOSITORY_ROOT / "experiments" / "v0.2.0-gpu-worker" / "model-registry.json"


def load_registry(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise WorkerError("MODEL_OUTPUT_INVALID", "model registry must be a JSON array")
    for item in value:
        revision = item.get("revision")
        if not isinstance(revision, str) or not IMMUTABLE_REVISION.fullmatch(revision):
            raise WorkerError("MODEL_OUTPUT_INVALID", f"floating model revision rejected: {revision!r}")
        for key in ("model_id", "provider", "task", "license", "weight_sha256", "config_sha256"):
            if not item.get(key):
                raise WorkerError("MODEL_OUTPUT_INVALID", f"model registry entry missing {key}")
    return value


def validate_binding(task: str, binding: dict[str, Any]) -> dict[str, Any]:
    matches = [
        item for item in load_registry(MODEL_REGISTRY)
        if item["task"] == task and item["model_id"] == binding.get("model_id")
    ]
    if len(matches) != 1:
        raise WorkerError("MODEL_HASH_MISMATCH", f"model is not registered for {task}")
    item = matches[0]
    if item.get("status") == "rejected":
        raise WorkerError("MODEL_ACCESS_FAILED", f"model is rejected for {task}")
    expected = {
        "revision": item["revision"],
        "weight_sha256": item["weight_sha256"],
        "config_sha256": item["config_sha256"],
        "license": item["license"],
        "dtype": item["required_dtype"],
        "environment_lock_sha256": item["environment"].rsplit("@", 1)[-1],
    }
    mismatches = [key for key, value in expected.items() if binding.get(key) != value]
    if mismatches:
        raise WorkerError("MODEL_HASH_MISMATCH", f"model binding mismatch: {mismatches}")
    return item
