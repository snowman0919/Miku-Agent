from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorkerSpec:
    kind: str
    worker_version: str
    tool: str
    tool_version: str
    model_id: str | None
    model_revision: str | None
    environment_digest: str
    input_object_hashes: tuple[str, ...]
    parameters: dict[str, object]

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def job_digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


OOM_FALLBACK_ORDER = ("reduce_batch", "reduce_chunk", "mixed_precision", "cpu_fallback", "split_job")
