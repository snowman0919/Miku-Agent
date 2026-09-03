from __future__ import annotations

import hashlib
import json
import sqlite3

from .eligibility import assert_corpus_row_eligible
from .registry import Registry


class ReviewConflict(RuntimeError):
    pass


SAMPLE_TABLES = {
    "audio": ("audio_samples", "sample_id"),
    "text": ("text_samples", "sample_id"),
    "persona": ("persona_samples", "sample_id"),
    "agentic": ("agentic_trajectories", "trajectory_id"),
    "duplex": ("duplex_timelines", "timeline_id"),
}
DECISIONS = {"accept", "quarantine", "reject"}


def gold_requires_double_review(entity_id: str) -> bool:
    return int(hashlib.sha256(entity_id.encode()).hexdigest(), 16) % 10 == 0


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _prepare_audio_edits(
    connection: sqlite3.Connection, row: sqlite3.Row, edits: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    allowed = {"raw_text", "spoken_text", "normalized_text", "segment_start_ms", "segment_end_ms"}
    if set(edits) - allowed:
        raise ValueError("unsupported audio edit field")
    before = {key: row[key] for key in allowed} | {"clip_object_sha256": row["clip_object_sha256"]}
    after = {key: before[key] for key in allowed} | edits
    for key in ("raw_text", "spoken_text", "normalized_text"):
        if not isinstance(after[key], str) or len(after[key]) > 10000:
            raise ValueError(f"{key} must be a string of at most 10000 characters")
    start = _integer(after["segment_start_ms"], "segment_start_ms")
    end = _integer(after["segment_end_ms"], "segment_end_ms")
    if start < 0 or end <= start:
        raise ValueError("invalid segment interval")
    parent = connection.execute(
        "SELECT duration_ms FROM audio_metrics WHERE object_sha256=?",
        (row["parent_object_sha256"],),
    ).fetchone()
    if parent is None or end > parent["duration_ms"]:
        raise ValueError("segment is outside the verified parent")
    after["duration_ms"] = end - start
    after["clip_object_sha256"] = row["clip_object_sha256"] if (
        start == row["segment_start_ms"] and end == row["segment_end_ms"]
    ) else None
    after["segment_fingerprint"] = Registry.segment_fingerprint(
        row["parent_object_sha256"], start, end, str(after["normalized_text"])
    )
    return before, after


def _validated_evidence(
    entity_type: str, row: sqlite3.Row | None, decision: str,
    evidence: dict[str, object] | None, edits: dict[str, object] | None,
) -> dict[str, object] | None:
    if evidence is None:
        if decision == "accept" and entity_type in {*SAMPLE_TABLES, "source"}:
            raise ValueError("accepted samples and sources require review evidence")
        if edits:
            raise ValueError("sample edits require review evidence")
        return None
    if not isinstance(evidence, dict):
        raise ValueError("review evidence must be an object")
    value = dict(evidence)
    if value.get("actor_type") not in {"human", "evaluator", "system"}:
        raise ValueError("invalid review actor type")
    value["batch_size"] = _integer(value.get("batch_size"), "batch_size")
    value["media_reviewed_ms"] = _integer(value.get("media_reviewed_ms", 0), "media_reviewed_ms")
    if value["batch_size"] != 1 or value["media_reviewed_ms"] < 0:
        raise ValueError("reviews must be submitted one item at a time")
    for name in ("read_complete", "adjudication"):
        if not isinstance(value.get(name, False), bool):
            raise ValueError(f"{name} must be a boolean")
        value[name] = value.get(name, False)
    if (decision == "accept" and row is not None and "quality_tier" in row.keys()
            and str(row["quality_tier"]).lower() == "gold"):
        if value["actor_type"] != "human":
            raise PermissionError("Gold review requires a human actor")
        if entity_type == "audio" and value["media_reviewed_ms"] < row["duration_ms"]:
            raise PermissionError("Gold audio must be listened through before acceptance")
        if entity_type == "persona" and not value["read_complete"]:
            raise PermissionError("Gold persona must be read before acceptance")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode()) > 65536:
        raise ValueError("review evidence is too large")
    return value


def add_review(
    registry: Registry, entity_type: str, entity_id: str, decision: str,
    reviewer: str, reason: str, *, expected_revision: int,
    evidence: dict[str, object] | None = None, edits: dict[str, object] | None = None,
) -> str:
    if decision not in DECISIONS:
        raise ValueError("invalid review decision")
    if not isinstance(reviewer, str) or not isinstance(reason, str) or not reviewer.strip() or not reason.strip():
        raise ValueError("reviewer and reason are required")
    if (not isinstance(entity_id, str) or not entity_id or isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int) or expected_revision < 0):
        raise ValueError("invalid review identity or revision")
    if edits is not None and not isinstance(edits, dict):
        raise ValueError("sample edits must be an object")
    if entity_type not in {*SAMPLE_TABLES, "source", "worker_result"}:
        raise ValueError("invalid review entity type")
    conflict: tuple[int, int] | None = None
    review_id = ""
    with registry.transaction() as connection:
        latest = connection.execute(
            "SELECT * FROM reviews WHERE entity_type=? AND entity_id=? ORDER BY revision DESC LIMIT 1",
            (entity_type, entity_id),
        ).fetchone()
        actual_revision = latest["revision"] if latest else 0
        if actual_revision != expected_revision:
            registry.audit(connection, "review.conflict", reviewer, entity_type, entity_id,
                           {"expected_revision": expected_revision, "actual_revision": actual_revision})
            conflict = (expected_revision, actual_revision)
        else:
            row = None
            if entity_type in SAMPLE_TABLES:
                table, id_column = SAMPLE_TABLES[entity_type]
                row = connection.execute(
                    f"SELECT * FROM {table} WHERE {id_column}=?", (entity_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(entity_id)
            elif entity_type == "source":
                row = connection.execute("SELECT * FROM sources WHERE source_id=?", (entity_id,)).fetchone()
                if row is None:
                    raise KeyError(entity_id)
            audio_update = None
            if edits:
                if entity_type != "audio" or row is None:
                    raise ValueError("only audio review fields are editable")
                if row["training_status"] == "accepted":
                    raise PermissionError("accepted audio must be quarantined before editing")
                before, audio_update = _prepare_audio_edits(connection, row, edits)
                evidence = dict(evidence or {}) | {"edits_before": before, "edits_after": audio_update}
                row = dict(row) | audio_update
            checked_evidence = _validated_evidence(entity_type, row, decision, evidence, edits)
            review_id = registry.new_id()
            connection.execute(
                "INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)",
                (review_id, entity_type, entity_id, actual_revision + 1, reviewer,
                 latest["decision"] if latest else None, decision, reason, registry.now()),
            )
            if audio_update is not None:
                connection.execute(
                    """UPDATE audio_samples SET raw_text=?,spoken_text=?,normalized_text=?,duration_ms=?,
                       segment_start_ms=?,segment_end_ms=?,clip_object_sha256=?,segment_fingerprint=?
                       WHERE sample_id=?""",
                    (audio_update["raw_text"], audio_update["spoken_text"], audio_update["normalized_text"],
                     audio_update["duration_ms"], audio_update["segment_start_ms"],
                     audio_update["segment_end_ms"], audio_update["clip_object_sha256"],
                     audio_update["segment_fingerprint"], entity_id),
                )
            if checked_evidence is not None:
                connection.execute(
                    "INSERT INTO review_evidence VALUES (?,?,?,?,?,?,?)",
                    (review_id, checked_evidence["actor_type"], checked_evidence["media_reviewed_ms"],
                     int(checked_evidence["read_complete"]), checked_evidence["batch_size"],
                     json.dumps(checked_evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    registry.now()),
                )
            if entity_type == "source":
                connection.execute(
                    "UPDATE sources SET review_status=? WHERE source_id=?",
                    ("reviewed" if decision in {"accept", "reject"} else "unreviewed", entity_id),
                )
            registry.audit(connection, "review.revised", reviewer, entity_type, entity_id,
                           {"previous": latest["decision"] if latest else None, "new": decision,
                            "revision": actual_revision + 1, "evidence": checked_evidence is not None,
                            "edited": audio_update is not None})
    if conflict:
        raise ReviewConflict(f"expected revision {conflict[0]}, found {conflict[1]}")
    return review_id


def assert_review_accepted(
    connection: sqlite3.Connection, entity_type: str, entity_id: str,
    *, quality_tier: str | None = None, duration_ms: int | None = None,
) -> None:
    latest = connection.execute(
        """SELECT r.*,e.actor_type,e.media_reviewed_ms,e.read_complete,e.evidence_json
           FROM reviews r LEFT JOIN review_evidence e USING(review_id)
           WHERE r.entity_type=? AND r.entity_id=? ORDER BY r.revision DESC LIMIT 1""",
        (entity_type, entity_id),
    ).fetchone()
    if latest is None or latest["decision"] != "accept" or latest["evidence_json"] is None:
        raise PermissionError("sample lacks an evidence-backed accepted review")
    if (quality_tier or "").lower() != "gold":
        return
    if latest["actor_type"] != "human":
        raise PermissionError("Gold sample lacks human review")
    if entity_type == "audio" and latest["media_reviewed_ms"] < (duration_ms or 0):
        raise PermissionError("Gold audio review did not cover the full segment")
    if entity_type == "persona" and not latest["read_complete"]:
        raise PermissionError("Gold persona review was not completed")
    if gold_requires_double_review(entity_id):
        reviewers = connection.execute(
            """SELECT count(DISTINCT r.reviewer) FROM reviews r JOIN review_evidence e USING(review_id)
               WHERE r.entity_type=? AND r.entity_id=? AND r.decision='accept' AND e.actor_type='human'""",
            (entity_type, entity_id),
        ).fetchone()[0]
        if reviewers < 2:
            raise PermissionError("Gold double-review sample needs two independent reviewers")
        decisions = connection.execute(
            "SELECT count(DISTINCT decision) FROM reviews WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        ).fetchone()[0]
        if decisions > 1 and not json.loads(latest["evidence_json"]).get("adjudication"):
            raise PermissionError("Gold review disagreement requires adjudication")


def assert_gold_double_review_coverage(connection: sqlite3.Connection, entity_type: str) -> None:
    if entity_type not in {"audio", "persona"}:
        return
    table, id_column = SAMPLE_TABLES[entity_type]
    ids = [row[0] for row in connection.execute(
        f"SELECT {id_column} FROM {table} WHERE training_status='accepted' AND lower(quality_tier)='gold'"
    )]
    required = (len(ids) + 9) // 10
    completed = 0
    for entity_id in ids:
        latest = connection.execute(
            """SELECT r.decision,e.actor_type,e.evidence_json FROM reviews r
               LEFT JOIN review_evidence e USING(review_id)
               WHERE r.entity_type=? AND r.entity_id=? ORDER BY r.revision DESC LIMIT 1""",
            (entity_type, entity_id),
        ).fetchone()
        reviewers = connection.execute(
            """SELECT count(DISTINCT r.reviewer) FROM reviews r JOIN review_evidence e USING(review_id)
               WHERE r.entity_type=? AND r.entity_id=? AND r.decision='accept' AND e.actor_type='human'""",
            (entity_type, entity_id),
        ).fetchone()[0]
        decisions = connection.execute(
            "SELECT count(DISTINCT decision) FROM reviews WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        ).fetchone()[0]
        adjudicated = latest and latest["evidence_json"] and json.loads(latest["evidence_json"]).get("adjudication")
        if (latest and latest["decision"] == "accept" and latest["actor_type"] == "human"
                and reviewers >= 2 and (decisions == 1 or adjudicated)):
            completed += 1
    if completed < required:
        raise PermissionError(
            f"Gold double-review coverage is {completed}/{len(ids)}; at least {required} is required"
        )


def promote_sample(registry: Registry, entity_type: str, entity_id: str, *, actor: str) -> bool:
    if entity_type not in SAMPLE_TABLES or not isinstance(actor, str) or not actor.strip():
        raise ValueError("invalid sample promotion request")
    table, id_column = SAMPLE_TABLES[entity_type]
    with registry.transaction() as connection:
        row = connection.execute(f"SELECT * FROM {table} WHERE {id_column}=?", (entity_id,)).fetchone()
        if row is None:
            raise KeyError(entity_id)
        if row["training_status"] == "accepted":
            return False
        registry.assert_exportable(connection, row["source_id"])
        assert_review_accepted(
            connection, entity_type, entity_id,
            quality_tier=row["quality_tier"] if "quality_tier" in row.keys() else None,
            duration_ms=row["duration_ms"] if "duration_ms" in row.keys() else None,
        )
        assert_corpus_row_eligible(entity_type, row)
        connection.execute(f"UPDATE {table} SET training_status='accepted' WHERE {id_column}=?", (entity_id,))
        registry.audit(connection, "sample.training_promoted", actor, entity_type, entity_id,
                       {"source_id": row["source_id"]})
    return True
