from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .config import FoundryPaths
from .registry import Registry
from .store import ObjectStore


SCHEMA = Path(__file__).resolve().parents[4] / "schemas" / "dataset" / "agentic-execution-receipt.schema.json"


def _load_receipt(path: Path) -> tuple[dict[str, Any], str]:
    body = path.read_bytes()
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("agentic execution receipt must be an object")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise ValueError(f"agentic execution receipt schema: {errors[0].message}")
    return value, hashlib.sha256(body).hexdigest()


def import_execution_receipt(
    paths: FoundryPaths, registry: Registry, receipt_path: Path, *, actor: str
) -> dict[str, object]:
    if receipt_path.is_symlink():
        raise ValueError("invalid agentic execution receipt import")
    receipt_path = receipt_path.resolve(strict=True)
    if not receipt_path.is_file() or not isinstance(actor, str) or not actor.strip():
        raise ValueError("invalid agentic execution receipt import")
    receipt, digest = _load_receipt(receipt_path)
    with registry.connect() as connection:
        if connection.execute("SELECT 1 FROM sources WHERE source_id=?", (receipt["source_id"],)).fetchone() is None:
            raise KeyError(receipt["source_id"])
        previous = connection.execute(
            "SELECT execution_receipt_sha256 FROM agentic_trajectories WHERE trajectory_id=?",
            (receipt["trajectory_id"],),
        ).fetchone()
        if previous:
            if previous[0] != digest:
                raise ValueError("trajectory was already imported with a different receipt")
            canonical = paths.object_path(digest)
            if not canonical.is_file() or ObjectStore.hash_file(canonical) != (digest, receipt_path.stat().st_size):
                raise IOError("canonical execution receipt failed integrity verification")
            return {"trajectory_id": receipt["trajectory_id"], "receipt_sha256": digest, "idempotent": True}
    stored = ObjectStore(paths, registry).ingest(
        receipt_path, receipt["source_id"], role="agentic:execution_receipt", media_type="application/json"
    )
    if stored != digest:
        raise ValueError("canonical receipt hash differs")
    with registry.transaction() as connection:
        connection.execute(
            """INSERT INTO agentic_trajectories(
                 trajectory_id,source_id,task_type,events_json,execution_backed,failure_recovery,
                 verified,provenance_json,training_status,verification_status,
                 execution_receipt_sha256,environment_binding_json,test_receipt_json,side_effect_class
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (receipt["trajectory_id"], receipt["source_id"], receipt["task_type"],
             json.dumps(receipt["events"], ensure_ascii=False, sort_keys=True), 1,
             int(receipt["failure_recovery"]), 1,
             json.dumps(receipt["provenance"], ensure_ascii=False, sort_keys=True), "quarantine",
             "execution_backed", digest,
             json.dumps(receipt["environment_binding"], sort_keys=True),
             json.dumps(receipt["test_receipt"], sort_keys=True), receipt["side_effect_class"]),
        )
        registry.audit(connection, "agentic.execution_imported", actor, "agentic", receipt["trajectory_id"],
                       {"receipt_sha256": digest, "source_id": receipt["source_id"]})
    return {"trajectory_id": receipt["trajectory_id"], "receipt_sha256": digest, "idempotent": False}
