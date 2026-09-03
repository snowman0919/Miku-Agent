from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from conftest import source
from miku_foundry.agentic import import_execution_receipt


def receipt(source_id: str, trajectory_id: str) -> dict[str, object]:
    return {
        "receipt_id": "00000000-0000-4000-8000-000000000001",
        "source_id": source_id,
        "trajectory_id": trajectory_id,
        "task_type": "repository.validation",
        "events": [
            {"kind": "tool_call", "tool": "pytest", "summary": "run focused tests"},
            {"kind": "tool_result", "status": "passed", "summary": "tests passed"},
        ],
        "failure_recovery": False,
        "environment_binding": {
            "repository": "snowman0919/Miku-Agent",
            "base_commit": "1" * 40,
            "result_commit": "2" * 40,
            "runtime": "local-test",
        },
        "test_receipt": {
            "status": "passed",
            "commands": [{"command": "pytest -q", "exit_code": 0, "result": "1 passed"}],
        },
        "side_effect_class": "workspace-write",
        "provenance": {"actor": "test"},
        "created_at": 1,
    }


def test_agentic_import_requires_and_preserves_source_bound_execution_receipt(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry)
    trajectory_id = "00000000-0000-4000-8000-000000000002"
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt(source_id, trajectory_id)), encoding="utf-8")

    imported = import_execution_receipt(paths, registry, path, actor="operator")
    assert imported["idempotent"] is False
    assert import_execution_receipt(paths, registry, path, actor="operator")["idempotent"] is True
    with registry.connect() as connection:
        row = connection.execute(
            "SELECT * FROM agentic_trajectories WHERE trajectory_id=?", (trajectory_id,)
        ).fetchone()
        binding = connection.execute(
            "SELECT role FROM source_objects WHERE source_id=? AND sha256=?",
            (source_id, imported["receipt_sha256"]),
        ).fetchone()
    assert row["verification_status"] == "execution_backed" and row["training_status"] == "quarantine"
    assert binding[0] == "agentic:execution_receipt"

    claimed = "f" * 64
    with registry.connect() as connection, pytest.raises(sqlite3.IntegrityError, match="requires receipts"):
        connection.execute(
            """INSERT INTO agentic_trajectories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("00000000-0000-4000-8000-000000000003", source_id, "fake", "[]", 1, 0, 1,
             "{}", "quarantine", "execution_backed", claimed, "{}", "{}", "none"),
        )

    invalid = receipt(source_id, "00000000-0000-4000-8000-000000000004")
    invalid["test_receipt"]["commands"][0]["exit_code"] = 1  # type: ignore[index]
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="agentic execution receipt schema"):
        import_execution_receipt(paths, registry, path, actor="operator")

    path.write_text(json.dumps(receipt(source_id, trajectory_id)), encoding="utf-8")
    canonical = paths.object_path(imported["receipt_sha256"])
    canonical.chmod(0o600)
    canonical.write_bytes(b"corrupt")
    with pytest.raises(OSError, match="integrity verification"):
        import_execution_receipt(paths, registry, path, actor="operator")
