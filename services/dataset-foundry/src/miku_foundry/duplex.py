from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .config import FoundryPaths
from .eligibility import assert_corpus_row_eligible
from .registry import Registry
from .store import ObjectStore


SCHEMA = Path(__file__).resolve().parents[4] / "schemas" / "dataset" / "duplex-timeline.schema.json"
COLUMNS = (
    "timeline_id", "source_id", "scenario", "events_json", "language", "relationship_mode",
    "expected_behavior", "forbidden_behavior", "provenance_json", "training_status",
    "timeline_source", "audio_input_sha256", "audio_output_sha256", "event_alignment_ppm",
    "human_adjudication", "evidence_kind",
)
IMMUTABLE_COLUMNS = tuple(column for column in COLUMNS if column not in {"training_status", "human_adjudication"})


def _already_imported(connection, row: dict[str, Any]) -> bool:
    values = tuple(row[column] for column in IMMUTABLE_COLUMNS)
    previous = connection.execute(
        f"SELECT {','.join(IMMUTABLE_COLUMNS)} FROM duplex_timelines WHERE timeline_id=?", (row["timeline_id"],)
    ).fetchone()
    if previous:
        if tuple(previous) != values:
            raise ValueError("timeline was already imported with different content")
        return True
    # ponytail: JSON scans are bounded by the 20k bundle cap; add an event digest column if imports outgrow it.
    duplicate = connection.execute(
        "SELECT timeline_id FROM duplex_timelines WHERE json(events_json)=json(?)", (row["events_json"],)
    ).fetchone()
    if duplicate:
        raise ValueError("timeline duplicates an existing event sequence")
    return False


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("duplex bundle exceeds 64 MiB")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    rows, ids, bodies = [], set(), set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
        if errors:
            raise ValueError(f"duplex bundle line {number}: {errors[0].message}")
        body = json.dumps(value["events"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if value["timeline_id"] in ids or body in bodies:
            raise ValueError("duplex bundle contains duplicate identity or event sequence")
        ids.add(value["timeline_id"])
        bodies.add(body)
        row = dict(value)
        row["events_json"] = body
        row["provenance_json"] = json.dumps(
            row.pop("provenance"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        row.pop("events")
        assert_corpus_row_eligible("duplex", row)
        rows.append(row)
    if not rows:
        raise ValueError("duplex bundle is empty")
    return rows


def import_duplex_bundle(
    paths: FoundryPaths, registry: Registry, bundle_path: Path, *, actor: str
) -> dict[str, object]:
    if bundle_path.is_symlink() or not isinstance(actor, str) or not actor.strip():
        raise ValueError("invalid duplex bundle import")
    bundle_path = bundle_path.resolve(strict=True)
    if not bundle_path.is_file():
        raise ValueError("duplex bundle must be a regular file")
    rows = _rows(bundle_path)
    source_ids = {row["source_id"] for row in rows}
    if len(source_ids) != 1:
        raise ValueError("duplex bundle must belong to one source")
    source_id = source_ids.pop()
    with registry.connect() as connection:
        if connection.execute("SELECT 1 FROM sources WHERE source_id=?", (source_id,)).fetchone() is None:
            raise KeyError(source_id)
        for row in rows:
            _already_imported(connection, row)
    digest = ObjectStore(paths, registry).ingest(
        bundle_path, source_id, role="duplex:timestamp-bundle", media_type="application/x-ndjson"
    )
    inserted = 0
    with registry.transaction() as connection:
        for row in rows:
            values = tuple(row[column] for column in COLUMNS)
            if _already_imported(connection, row):
                continue
            connection.execute(
                f"INSERT INTO duplex_timelines({','.join(COLUMNS)}) VALUES ({','.join('?' for _ in COLUMNS)})",
                values,
            )
            inserted += 1
        registry.audit(connection, "duplex.bundle_imported", actor, "source", source_id,
                       {"bundle_sha256": digest, "rows": len(rows), "inserted": inserted})
    return {"source_id": source_id, "bundle_sha256": digest, "rows": len(rows),
            "inserted": inserted, "idempotent": inserted == 0}
