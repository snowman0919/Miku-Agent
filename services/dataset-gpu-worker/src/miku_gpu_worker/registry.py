"""Pinned model registry validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import WorkerError

IMMUTABLE_REVISION = re.compile(r"^[0-9a-f]{40,64}$")


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

