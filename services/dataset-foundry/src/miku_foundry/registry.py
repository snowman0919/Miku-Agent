from __future__ import annotations

import contextlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
RIGHTS_CLEARED = {"owned", "licensed", "permitted"}

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_meta(version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS objects(
  sha256 TEXT PRIMARY KEY CHECK(length(sha256)=64), size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),
  media_type TEXT, created_at INTEGER NOT NULL, verified_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sources(
  source_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, title TEXT NOT NULL, origin TEXT NOT NULL,
  creator TEXT, acquisition_method TEXT NOT NULL, discovered_at INTEGER NOT NULL,
  acquired_at INTEGER, language TEXT NOT NULL, character_id TEXT NOT NULL,
  parent_work TEXT, derivative_family TEXT NOT NULL, intake_status TEXT NOT NULL,
  quality_status TEXT NOT NULL, review_status TEXT NOT NULL, training_status TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS source_objects(
  source_id TEXT NOT NULL REFERENCES sources(source_id), sha256 TEXT NOT NULL REFERENCES objects(sha256),
  original_name TEXT NOT NULL, role TEXT NOT NULL, PRIMARY KEY(source_id, sha256, role)
);
CREATE TABLE IF NOT EXISTS rights_records(
  rights_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id), status TEXT NOT NULL,
  evidence_type TEXT NOT NULL, evidence_ref TEXT NOT NULL, evidence_sha256 TEXT,
  allowed_use TEXT NOT NULL, restrictions TEXT NOT NULL, expires_at INTEGER,
  reviewer TEXT NOT NULL, actor_type TEXT NOT NULL, created_at INTEGER NOT NULL,
  CHECK(status IN ('owned','licensed','permitted','unknown','restricted','rejected'))
);
CREATE TABLE IF NOT EXISTS transforms(
  transform_id TEXT PRIMARY KEY, kind TEXT NOT NULL, spec_json TEXT NOT NULL,
  spec_sha256 TEXT UNIQUE NOT NULL, tool TEXT NOT NULL, tool_version TEXT NOT NULL,
  status TEXT NOT NULL, created_at INTEGER NOT NULL, completed_at INTEGER
);
CREATE TABLE IF NOT EXISTS lineage_edges(
  parent_sha256 TEXT NOT NULL REFERENCES objects(sha256), child_sha256 TEXT NOT NULL REFERENCES objects(sha256),
  transform_id TEXT NOT NULL REFERENCES transforms(transform_id),
  PRIMARY KEY(parent_sha256, child_sha256, transform_id), CHECK(parent_sha256<>child_sha256)
);
CREATE TABLE IF NOT EXISTS audio_samples(
  sample_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id),
  object_sha256 TEXT NOT NULL REFERENCES objects(sha256), duration_ms INTEGER NOT NULL CHECK(duration_ms>0),
  language TEXT NOT NULL, raw_text TEXT NOT NULL, spoken_text TEXT NOT NULL, normalized_text TEXT NOT NULL,
  modality TEXT NOT NULL CHECK(modality IN ('speech','singing_aux')),
  quality_ppm INTEGER NOT NULL CHECK(quality_ppm BETWEEN 0 AND 1000000),
  alignment_ppm INTEGER NOT NULL CHECK(alignment_ppm BETWEEN 0 AND 1000000),
  review_weight_ppm INTEGER NOT NULL CHECK(review_weight_ppm BETWEEN 0 AND 1000000),
  source_tier_weight_ppm INTEGER NOT NULL CHECK(source_tier_weight_ppm BETWEEN 0 AND 1000000),
  quality_tier TEXT NOT NULL, training_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audio_metrics(
  object_sha256 TEXT PRIMARY KEY REFERENCES objects(sha256), sample_rate_hz INTEGER NOT NULL,
  channels INTEGER NOT NULL, duration_ms INTEGER NOT NULL, sample_width_bytes INTEGER NOT NULL,
  peak_ppm INTEGER NOT NULL, clipping_ppm INTEGER NOT NULL, dc_offset_ppm INTEGER NOT NULL,
  silence_ppm INTEGER NOT NULL, decoder TEXT NOT NULL, measured_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS text_samples(
  sample_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id), corpus TEXT NOT NULL,
  raw_text TEXT NOT NULL, spoken_text TEXT NOT NULL, normalized_text TEXT NOT NULL,
  language TEXT NOT NULL, coverage_tags_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
  training_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS persona_samples(
  sample_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id), prompt TEXT NOT NULL,
  response TEXT NOT NULL, dimensions_json TEXT NOT NULL, hard_violation INTEGER NOT NULL CHECK(hard_violation IN (0,1)),
  cosine_ppm INTEGER NOT NULL, quality_tier TEXT NOT NULL, provenance_json TEXT NOT NULL,
  training_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agentic_trajectories(
  trajectory_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id), task_type TEXT NOT NULL,
  events_json TEXT NOT NULL, execution_backed INTEGER NOT NULL CHECK(execution_backed IN (0,1)),
  failure_recovery INTEGER NOT NULL CHECK(failure_recovery IN (0,1)), verified INTEGER NOT NULL CHECK(verified IN (0,1)),
  provenance_json TEXT NOT NULL, training_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS duplex_timelines(
  timeline_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id), scenario TEXT NOT NULL,
  events_json TEXT NOT NULL, language TEXT NOT NULL, relationship_mode TEXT NOT NULL,
  expected_behavior TEXT NOT NULL, forbidden_behavior TEXT NOT NULL, provenance_json TEXT NOT NULL,
  training_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews(
  review_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, revision INTEGER NOT NULL,
  reviewer TEXT NOT NULL, previous_decision TEXT, decision TEXT NOT NULL, reason TEXT NOT NULL,
  created_at INTEGER NOT NULL, UNIQUE(entity_type, entity_id, revision)
);
CREATE TABLE IF NOT EXISTS split_assignments(
  group_id TEXT NOT NULL, policy_version TEXT NOT NULL, split TEXT NOT NULL,
  frozen INTEGER NOT NULL DEFAULT 0 CHECK(frozen IN (0,1)), assigned_at INTEGER NOT NULL,
  PRIMARY KEY(group_id, policy_version), CHECK(split IN ('train','validation','test','eval'))
);
CREATE TABLE IF NOT EXISTS jobs(
  job_id TEXT PRIMARY KEY, kind TEXT NOT NULL, idempotency_key TEXT UNIQUE NOT NULL, state TEXT NOT NULL,
  input_manifest_json TEXT NOT NULL, output_manifest_json TEXT, error_json TEXT,
  created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS dataset_versions(
  dataset_id TEXT NOT NULL, version TEXT NOT NULL, schema_version TEXT NOT NULL,
  manifest_sha256 TEXT, state TEXT NOT NULL, created_at INTEGER NOT NULL,
  PRIMARY KEY(dataset_id, version)
);
CREATE TABLE IF NOT EXISTS pending_ingests(
  ingest_id TEXT PRIMARY KEY, staged_path TEXT NOT NULL, sha256 TEXT, source_id TEXT,
  state TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events(
  event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, actor TEXT NOT NULL,
  subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, details_json TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
"""


class Registry:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as connection:
            connection.executescript(DDL)
            count = connection.execute("SELECT count(*) FROM schema_meta").fetchone()[0]
            if count == 0:
                connection.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
            elif connection.execute("SELECT version FROM schema_meta").fetchone()[0] != SCHEMA_VERSION:
                raise RuntimeError("unsupported registry schema version")
        self.path.chmod(0o600)

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    @staticmethod
    def now() -> int:
        return time.time_ns()

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    def audit(self, connection: sqlite3.Connection, event_type: str, actor: str,
              subject_type: str, subject_id: str, details: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?)",
            (self.new_id(), event_type, actor, subject_type, subject_id,
             json.dumps(details, sort_keys=True, separators=(",", ":")), self.now()),
        )

    def current_rights(self, connection: sqlite3.Connection, source_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM rights_records WHERE source_id=? ORDER BY created_at DESC, rights_id DESC LIMIT 1",
            (source_id,),
        ).fetchone()

    def assert_exportable(self, connection: sqlite3.Connection, source_id: str) -> None:
        rights = self.current_rights(connection, source_id)
        if not rights or rights["status"] not in RIGHTS_CLEARED or not rights["evidence_ref"]:
            raise PermissionError("current rights evidence does not permit training export")
        if rights["expires_at"] is not None and rights["expires_at"] <= self.now():
            raise PermissionError("rights evidence has expired")
        source = connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
        if not source or source["training_status"] != "accepted":
            raise PermissionError("source is not training accepted")
