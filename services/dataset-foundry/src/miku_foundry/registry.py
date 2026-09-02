from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 2
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
  notes TEXT NOT NULL DEFAULT '',
  corpus_class TEXT NOT NULL DEFAULT 'quarantine_real_corpus',
  evaluation_status TEXT
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
  quality_tier TEXT NOT NULL, training_status TEXT NOT NULL,
  parent_object_sha256 TEXT NOT NULL REFERENCES objects(sha256),
  segment_start_ms INTEGER NOT NULL CHECK(segment_start_ms>=0),
  segment_end_ms INTEGER NOT NULL CHECK(segment_end_ms>segment_start_ms),
  clip_object_sha256 TEXT REFERENCES objects(sha256),
  segment_fingerprint TEXT NOT NULL CHECK(length(segment_fingerprint)=64)
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
  provenance_json TEXT NOT NULL, training_status TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'unverified',
  execution_receipt_sha256 TEXT, environment_binding_json TEXT,
  test_receipt_json TEXT, side_effect_class TEXT NOT NULL DEFAULT 'none'
);
CREATE TABLE IF NOT EXISTS duplex_timelines(
  timeline_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id), scenario TEXT NOT NULL,
  events_json TEXT NOT NULL, language TEXT NOT NULL, relationship_mode TEXT NOT NULL,
  expected_behavior TEXT NOT NULL, forbidden_behavior TEXT NOT NULL, provenance_json TEXT NOT NULL,
  training_status TEXT NOT NULL, timeline_source TEXT NOT NULL,
  audio_input_sha256 TEXT, audio_output_sha256 TEXT,
  event_alignment_ppm INTEGER NOT NULL DEFAULT 0,
  human_adjudication TEXT, evidence_kind TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS worker_result_imports(
  job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
  result_sha256 TEXT UNIQUE NOT NULL, output_manifest_sha256 TEXT NOT NULL,
  transform_fingerprint TEXT NOT NULL, environment_sha256 TEXT NOT NULL,
  model_binding_json TEXT, imported_outputs_json TEXT NOT NULL, imported_at INTEGER NOT NULL
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

TRIGGERS_V2 = """
CREATE TRIGGER IF NOT EXISTS audio_segment_insert_guard
BEFORE INSERT ON audio_samples
BEGIN
  SELECT CASE WHEN NEW.segment_start_ms < 0 OR NEW.segment_end_ms <= NEW.segment_start_ms
    OR NEW.duration_ms != NEW.segment_end_ms - NEW.segment_start_ms
    THEN RAISE(ABORT, 'invalid audio segment interval') END;
  SELECT CASE WHEN NEW.training_status = 'accepted'
    AND NEW.clip_object_sha256 IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM audio_metrics
      WHERE object_sha256 = NEW.parent_object_sha256
        AND NEW.segment_end_ms <= duration_ms
    )
    THEN RAISE(ABORT, 'accepted audio requires immutable clip or verified interval') END;
  SELECT CASE WHEN NEW.training_status = 'accepted'
    AND EXISTS (
      SELECT 1 FROM audio_samples
      WHERE segment_fingerprint = NEW.segment_fingerprint
        AND training_status = 'accepted'
    )
    THEN RAISE(ABORT, 'duplicate accepted audio segment') END;
END;
CREATE TRIGGER IF NOT EXISTS audio_segment_update_guard
BEFORE UPDATE ON audio_samples
BEGIN
  SELECT CASE WHEN NEW.segment_start_ms < 0 OR NEW.segment_end_ms <= NEW.segment_start_ms
    OR NEW.duration_ms != NEW.segment_end_ms - NEW.segment_start_ms
    THEN RAISE(ABORT, 'invalid audio segment interval') END;
  SELECT CASE WHEN NEW.training_status = 'accepted'
    AND NEW.clip_object_sha256 IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM audio_metrics
      WHERE object_sha256 = NEW.parent_object_sha256
        AND NEW.segment_end_ms <= duration_ms
    )
    THEN RAISE(ABORT, 'accepted audio requires immutable clip or verified interval') END;
  SELECT CASE WHEN NEW.training_status = 'accepted'
    AND EXISTS (
      SELECT 1 FROM audio_samples
      WHERE segment_fingerprint = NEW.segment_fingerprint
        AND training_status = 'accepted'
        AND sample_id != NEW.sample_id
    )
    THEN RAISE(ABORT, 'duplicate accepted audio segment') END;
END;
CREATE TRIGGER IF NOT EXISTS agentic_execution_insert_guard
BEFORE INSERT ON agentic_trajectories
WHEN NEW.execution_backed = 1
BEGIN
  SELECT CASE WHEN NEW.verification_status != 'execution_backed'
    OR NEW.execution_receipt_sha256 IS NULL
    OR length(NEW.execution_receipt_sha256) != 64
    OR NEW.environment_binding_json IS NULL
    OR NEW.test_receipt_json IS NULL
    THEN RAISE(ABORT, 'execution-backed trajectory requires receipts') END;
END;
CREATE TRIGGER IF NOT EXISTS agentic_execution_update_guard
BEFORE UPDATE ON agentic_trajectories
WHEN NEW.execution_backed = 1
BEGIN
  SELECT CASE WHEN NEW.verification_status != 'execution_backed'
    OR NEW.execution_receipt_sha256 IS NULL
    OR length(NEW.execution_receipt_sha256) != 64
    OR NEW.environment_binding_json IS NULL
    OR NEW.test_receipt_json IS NULL
    THEN RAISE(ABORT, 'execution-backed trajectory requires receipts') END;
END;
"""

MIGRATION_V2 = (
    "ALTER TABLE sources ADD COLUMN corpus_class TEXT NOT NULL DEFAULT 'quarantine_real_corpus'",
    "ALTER TABLE sources ADD COLUMN evaluation_status TEXT",
    "ALTER TABLE audio_samples ADD COLUMN parent_object_sha256 TEXT REFERENCES objects(sha256)",
    "ALTER TABLE audio_samples ADD COLUMN segment_start_ms INTEGER",
    "ALTER TABLE audio_samples ADD COLUMN segment_end_ms INTEGER",
    "ALTER TABLE audio_samples ADD COLUMN clip_object_sha256 TEXT REFERENCES objects(sha256)",
    "ALTER TABLE audio_samples ADD COLUMN segment_fingerprint TEXT",
    "ALTER TABLE agentic_trajectories ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'unverified'",
    "ALTER TABLE agentic_trajectories ADD COLUMN execution_receipt_sha256 TEXT",
    "ALTER TABLE agentic_trajectories ADD COLUMN environment_binding_json TEXT",
    "ALTER TABLE agentic_trajectories ADD COLUMN test_receipt_json TEXT",
    "ALTER TABLE agentic_trajectories ADD COLUMN side_effect_class TEXT NOT NULL DEFAULT 'none'",
    "ALTER TABLE duplex_timelines ADD COLUMN timeline_source TEXT",
    "ALTER TABLE duplex_timelines ADD COLUMN audio_input_sha256 TEXT",
    "ALTER TABLE duplex_timelines ADD COLUMN audio_output_sha256 TEXT",
    "ALTER TABLE duplex_timelines ADD COLUMN event_alignment_ppm INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE duplex_timelines ADD COLUMN human_adjudication TEXT",
    "ALTER TABLE duplex_timelines ADD COLUMN evidence_kind TEXT",
)


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
            else:
                version = connection.execute("SELECT version FROM schema_meta").fetchone()[0]
                if version == 1:
                    self._migrate_v2(connection)
                elif version != SCHEMA_VERSION:
                    raise RuntimeError("unsupported registry schema version")
            connection.executescript(TRIGGERS_V2)
        self.path.chmod(0o600)

    def _migrate_v2(self, connection: sqlite3.Connection) -> None:
        backup_dir = self.path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup_path = backup_dir / f"registry-v1-{self.now()}.sqlite3"
        with sqlite3.connect(backup_path) as backup:
            connection.backup(backup)
        backup_path.chmod(0o600)
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in MIGRATION_V2:
                connection.execute(statement)
            connection.execute(
                """UPDATE sources
                   SET corpus_class=CASE
                     WHEN training_status='holdout' THEN 'evaluation_corpus'
                     WHEN origin='locally-generated-foundry-pilot' THEN 'infrastructure_fixture'
                     WHEN training_status='accepted' THEN 'accepted_corpus'
                     ELSE 'quarantine_real_corpus' END,
                       evaluation_status=CASE
                         WHEN training_status='holdout' THEN 'reserved_group'
                         ELSE NULL END"""
            )
            rows = connection.execute(
                "SELECT sample_id,object_sha256,duration_ms,normalized_text FROM audio_samples"
            )
            for row in rows:
                fingerprint = self.segment_fingerprint(
                    row["object_sha256"], 0, row["duration_ms"], row["normalized_text"]
                )
                connection.execute(
                    """UPDATE audio_samples
                       SET parent_object_sha256=?,segment_start_ms=0,segment_end_ms=?,
                           segment_fingerprint=?
                       WHERE sample_id=?""",
                    (row["object_sha256"], row["duration_ms"], fingerprint, row["sample_id"]),
                )
            connection.execute(
                """UPDATE agentic_trajectories
                   SET verification_status=CASE
                     WHEN execution_backed=1 THEN 'unverified'
                     WHEN verified=1 THEN 'synthetic_expected'
                     WHEN failure_recovery=1 THEN 'failed'
                     ELSE 'unverified' END"""
            )
            connection.execute(
                """UPDATE duplex_timelines
                   SET timeline_source='locally-generated-foundry-pilot',
                       evidence_kind='synthetic'"""
            )
            connection.execute("UPDATE schema_meta SET version=2")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    @staticmethod
    def segment_fingerprint(
        parent_object_sha256: str, start_ms: int, end_ms: int, normalized_text: str
    ) -> str:
        body = f"{parent_object_sha256}\0{start_ms}\0{end_ms}\0{normalized_text}".encode()
        return hashlib.sha256(body).hexdigest()

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
