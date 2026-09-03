from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from .config import FoundryPaths
from .eligibility import assert_corpus_row_eligible
from .registry import Registry
from .review import assert_gold_double_review_coverage, assert_review_accepted
from .split import leakage_findings


SNAPSHOT_TABLES = (
    "sources", "objects", "source_objects", "rights_records", "transforms",
    "worker_result_imports", "audio_samples", "audio_metrics", "text_samples", "persona_samples",
    "agentic_trajectories", "duplex_timelines", "reviews", "review_evidence",
    "split_assignments", "lineage_edges",
)


def _canonical_line(record: dict[str, object]) -> bytes:
    return (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _record_digest(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode()).hexdigest()


def _lineage_digest(connection, *object_hashes: str | None) -> str:
    hashes = sorted({value for value in object_hashes if value})
    if not hashes:
        return _record_digest([])
    placeholders = ",".join("?" for _ in hashes)
    rows = [tuple(row) for row in connection.execute(
        f"""SELECT e.parent_sha256,e.child_sha256,t.spec_sha256
            FROM lineage_edges e JOIN transforms t USING(transform_id)
            WHERE e.parent_sha256 IN ({placeholders}) OR e.child_sha256 IN ({placeholders})
            ORDER BY e.parent_sha256,e.child_sha256,t.spec_sha256""",
        (*hashes, *hashes),
    )]
    return _record_digest(rows)


def _source_state(connection, source_id: str, entity_type: str, entity_id: str) -> dict[str, object]:
    source = connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
    rights = connection.execute(
        """SELECT * FROM rights_records WHERE source_id=?
           ORDER BY created_at DESC,rights_id DESC LIMIT 1""",
        (source_id,),
    ).fetchone()
    review = connection.execute(
        """SELECT r.*,e.actor_type review_actor_type,e.media_reviewed_ms,e.read_complete,
                  e.batch_size,e.evidence_json,e.created_at evidence_created_at
           FROM reviews r LEFT JOIN review_evidence e USING(review_id)
           WHERE r.entity_type=? AND r.entity_id=? ORDER BY r.revision DESC LIMIT 1""",
        (entity_type, entity_id),
    ).fetchone()
    source_review = connection.execute(
        """SELECT r.*,e.actor_type review_actor_type,e.media_reviewed_ms,e.read_complete,
                  e.batch_size,e.evidence_json,e.created_at evidence_created_at
           FROM reviews r LEFT JOIN review_evidence e USING(review_id)
           WHERE r.entity_type='source' AND r.entity_id=? ORDER BY r.revision DESC LIMIT 1""",
        (source_id,),
    ).fetchone()
    return {
        "group_id": source["derivative_family"],
        "corpus_class": source["corpus_class"],
        "source_metadata_sha256": _record_digest(dict(source)),
        "source_review_record_sha256": _record_digest(dict(source_review)) if source_review else None,
        "rights_status": rights["status"] if rights else "unknown",
        "rights_training_allowed": bool(rights["training_allowed"]) if rights else False,
        "rights_evidence_sha256": _record_digest(dict(rights)) if rights else None,
        "review_status": review["decision"] if review else source["review_status"],
        "review_evidence_sha256": hashlib.sha256(review["evidence_json"].encode()).hexdigest()
        if review and review["evidence_json"] else None,
        "review_record_sha256": _record_digest(dict(review)) if review else None,
    }


def canonical_manifest(registry: Registry, destination: Path) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = hashlib.sha256()
    count = 0
    with registry.connect() as connection, destination.open("wb") as output:
        query = """
          SELECT a.*, COALESCE(sa.split, 'unassigned') split
          FROM audio_samples a JOIN sources s ON s.source_id=a.source_id
          LEFT JOIN split_assignments sa ON sa.group_id=s.derivative_family AND sa.policy_version='source-split-v1'
          ORDER BY a.sample_id
        """
        for row in connection.execute(query):
            state = _source_state(connection, row["source_id"], "audio", row["sample_id"])
            metadata = {key: row[key] for key in (
                "duration_ms", "language", "raw_text", "spoken_text", "normalized_text", "modality",
                "quality_ppm", "alignment_ppm", "review_weight_ppm", "source_tier_weight_ppm", "quality_tier",
            )}
            record = {
                "entity_id": row["sample_id"],
                "entity_type": "audio",
                "group_id": state["group_id"],
                "metadata_sha256": _record_digest(metadata),
                "object_sha256": row["object_sha256"],
                "parent_object_sha256": row["parent_object_sha256"],
                "segment_start_ms": row["segment_start_ms"],
                "segment_end_ms": row["segment_end_ms"],
                "clip_object_sha256": row["clip_object_sha256"],
                "segment_fingerprint": row["segment_fingerprint"],
                "lineage_sha256": _lineage_digest(
                    connection, row["object_sha256"], row["parent_object_sha256"], row["clip_object_sha256"]
                ),
                "corpus_class": state["corpus_class"],
                "source_metadata_sha256": state["source_metadata_sha256"],
                "source_review_record_sha256": state["source_review_record_sha256"],
                "rights_status": state["rights_status"],
                "rights_training_allowed": state["rights_training_allowed"],
                "rights_evidence_sha256": state["rights_evidence_sha256"],
                "review_status": state["review_status"],
                "review_evidence_sha256": state["review_evidence_sha256"],
                "review_record_sha256": state["review_record_sha256"],
                "split": row["split"],
                "training_status": row["training_status"],
            }
            line = _canonical_line(record)
            output.write(line)
            digest.update(line)
            count += 1
        for table, id_column in (("text_samples", "sample_id"), ("persona_samples", "sample_id"),
                                 ("agentic_trajectories", "trajectory_id"), ("duplex_timelines", "timeline_id")):
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY {id_column}")
            for row in rows:
                entity_type = table.removesuffix("_samples").removesuffix("_trajectories").removesuffix("_timelines")
                state = _source_state(connection, row["source_id"], entity_type, row[id_column])
                split_row = connection.execute("SELECT split FROM split_assignments WHERE group_id=? AND policy_version='source-split-v1'", (state["group_id"],)).fetchone()
                metadata_dict = {key: row[key] for key in row.keys() if key not in {id_column, "source_id", "training_status"}}
                metadata_bytes = json.dumps(metadata_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                record = {
                    "entity_id": row[id_column],
                    "entity_type": table,
                    "group_id": state["group_id"],
                    "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                    "object_sha256": None,
                    "lineage_sha256": _lineage_digest(connection, None),
                    "corpus_class": state["corpus_class"],
                    "source_metadata_sha256": state["source_metadata_sha256"],
                    "source_review_record_sha256": state["source_review_record_sha256"],
                    "rights_status": state["rights_status"],
                    "rights_training_allowed": state["rights_training_allowed"],
                    "rights_evidence_sha256": state["rights_evidence_sha256"],
                    "review_status": state["review_status"],
                    "review_evidence_sha256": state["review_evidence_sha256"],
                    "review_record_sha256": state["review_record_sha256"],
                    "split": split_row["split"] if split_row else "unassigned",
                    "training_status": row["training_status"],
                }
                line = _canonical_line(record)
                output.write(line)
                digest.update(line)
                count += 1
    return digest.hexdigest(), count


def snapshot(registry: Registry, paths: FoundryPaths, snapshot_id: str) -> dict[str, object]:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required for Parquet snapshots") from exc
    output_dir = paths.snapshots / snapshot_id
    if output_dir.exists():
        raise FileExistsError(output_dir)
    temporary_dir = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}.", dir=paths.snapshots))
    try:
        manifest_path = temporary_dir / "canonical-manifest.jsonl"
        root_digest, record_count = canonical_manifest(registry, manifest_path)
        parquet_hashes: dict[str, str] = {}
        duck = duckdb.connect()
        try:
            with registry.connect() as source:
                for table in SNAPSHOT_TABLES:
                    destination = temporary_dir / f"{table}.parquet"
                    columns = list(source.execute(f"PRAGMA table_info({table})"))
                    type_map = {"INTEGER": "BIGINT", "REAL": "DOUBLE", "BLOB": "BLOB"}
                    declaration = ",".join(
                        f'"{column[1]}" {type_map.get(str(column[2]).upper(), "VARCHAR")}' for column in columns
                    )
                    duck.execute(f'CREATE OR REPLACE TABLE "{table}" ({declaration})')
                    rows = [tuple(row) for row in source.execute(f"SELECT * FROM {table}")]
                    if rows:
                        placeholders = ",".join("?" for _ in columns)
                        duck.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
                    dest_path = str(destination).replace("'", "''")
                    duck.execute(f"COPY (SELECT * FROM \"{table}\") TO '{dest_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
                    parquet_hashes[destination.name] = hashlib.sha256(destination.read_bytes()).hexdigest()
        finally:
            duck.close()
        receipt = {"snapshot_id": snapshot_id, "dataset_root_sha256": root_digest,
                   "record_count": record_count, "parquet_sha256": parquet_hashes}
        (temporary_dir / "receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if output_dir.exists():
            raise FileExistsError(output_dir)
        os.replace(temporary_dir, output_dir)
        return receipt
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)


def export_training(registry: Registry, destination: Path, *, split: str, corpus: str) -> dict[str, object]:
    if leakage_findings(registry):
        raise PermissionError("cross-split lineage leakage blocks export")
    count = 0
    digest = hashlib.sha256()
    table = {"audio": "audio_samples", "persona": "persona_samples", "agentic": "agentic_trajectories", "duplex": "duplex_timelines", "text": "text_samples"}[corpus]
    id_column = {"audio": "sample_id", "persona": "sample_id", "agentic": "trajectory_id", "duplex": "timeline_id", "text": "sample_id"}[corpus]
    seen_audio: set[str] = set()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(handle, "wb") as output, registry.connect() as connection:
            entity_type = table.removesuffix("_samples").removesuffix("_trajectories").removesuffix("_timelines")
            query = f"""SELECT x.*, s.derivative_family FROM {table} x JOIN sources s ON s.source_id=x.source_id
                        JOIN split_assignments a ON a.group_id=s.derivative_family AND a.policy_version='source-split-v1'
                        WHERE x.training_status='accepted' AND a.split=? ORDER BY x.{id_column}"""
            for row in connection.execute(query, (split,)):
                registry.assert_exportable(connection, row["source_id"])
                assert_review_accepted(
                    connection, entity_type, row[id_column],
                    quality_tier=row["quality_tier"] if "quality_tier" in row.keys() else None,
                    duration_ms=row["duration_ms"] if "duration_ms" in row.keys() else None,
                )
                assert_corpus_row_eligible(corpus, row)
                if corpus == "audio":
                    if row["duration_ms"] != row["segment_end_ms"] - row["segment_start_ms"]:
                        raise PermissionError("audio segment duration differs from its interval")
                    if row["segment_fingerprint"] in seen_audio:
                        raise PermissionError("duplicate audio segment blocks training export")
                    seen_audio.add(row["segment_fingerprint"])
                    if row["clip_object_sha256"] is None:
                        metrics = connection.execute(
                            "SELECT duration_ms FROM audio_metrics WHERE object_sha256=?",
                            (row["parent_object_sha256"],),
                        ).fetchone()
                        if not metrics or row["segment_end_ms"] > metrics["duration_ms"]:
                            raise PermissionError("audio interval is outside the verified parent")
                record = {key: row[key] for key in row.keys()}
                line = _canonical_line(record)
                output.write(line)
                digest.update(line)
                count += 1
            assert_gold_double_review_coverage(connection, entity_type)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        try:
            os.close(handle)
        except OSError:
            pass
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return {"count": count, "sha256": digest.hexdigest(), "path": str(destination)}
