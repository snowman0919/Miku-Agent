from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import FoundryPaths
from .registry import Registry
from .split import leakage_findings


SNAPSHOT_TABLES = (
    "sources", "audio_samples", "audio_metrics", "text_samples", "persona_samples",
    "agentic_trajectories", "duplex_timelines", "reviews", "split_assignments", "lineage_edges",
)


def _canonical_line(record: dict[str, object]) -> bytes:
    return (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def canonical_manifest(registry: Registry, destination: Path) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = hashlib.sha256()
    count = 0
    with registry.connect() as connection, destination.open("wb") as output:
        query = """
          SELECT 'audio' entity_type, a.sample_id entity_id, a.object_sha256 object_sha256,
                 s.derivative_family group_id, COALESCE(sa.split, 'unassigned') split,
                 a.training_status training_status,
                 lower(hex(sha256(a.raw_text || char(0) || a.spoken_text || char(0) || a.normalized_text))) metadata_sha256
          FROM audio_samples a JOIN sources s ON s.source_id=a.source_id
          LEFT JOIN split_assignments sa ON sa.group_id=s.derivative_family AND sa.policy_version='source-split-v1'
          ORDER BY entity_id
        """
        # SQLite does not guarantee a sha256 SQL function. Compute metadata digest in Python.
        query = """
          SELECT a.sample_id, a.object_sha256, s.derivative_family,
                 COALESCE(sa.split, 'unassigned') split, a.training_status,
                 a.raw_text, a.spoken_text, a.normalized_text
          FROM audio_samples a JOIN sources s ON s.source_id=a.source_id
          LEFT JOIN split_assignments sa ON sa.group_id=s.derivative_family AND sa.policy_version='source-split-v1'
          ORDER BY a.sample_id
        """
        for row in connection.execute(query):
            metadata = "\0".join((row["raw_text"], row["spoken_text"], row["normalized_text"])).encode()
            record = {"entity_id": row["sample_id"], "entity_type": "audio",
                      "group_id": row["derivative_family"], "metadata_sha256": hashlib.sha256(metadata).hexdigest(),
                      "object_sha256": row["object_sha256"], "split": row["split"],
                      "training_status": row["training_status"]}
            line = _canonical_line(record)
            output.write(line)
            digest.update(line)
            count += 1
        for table, id_column in (("text_samples", "sample_id"), ("persona_samples", "sample_id"),
                                 ("agentic_trajectories", "trajectory_id"), ("duplex_timelines", "timeline_id")):
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY {id_column}")
            for row in rows:
                source = connection.execute("SELECT derivative_family FROM sources WHERE source_id=?", (row["source_id"],)).fetchone()
                split_row = connection.execute("SELECT split FROM split_assignments WHERE group_id=? AND policy_version='source-split-v1'", (source["derivative_family"],)).fetchone()
                metadata_dict = {key: row[key] for key in row.keys() if key not in {id_column, "source_id", "training_status"}}
                metadata_bytes = json.dumps(metadata_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                record = {"entity_id": row[id_column], "entity_type": table,
                          "group_id": source["derivative_family"], "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                          "object_sha256": None, "split": split_row["split"] if split_row else "unassigned",
                          "training_status": row["training_status"]}
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
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest_path = output_dir / "canonical-manifest.jsonl"
    root_digest, record_count = canonical_manifest(registry, manifest_path)
    parquet_hashes: dict[str, str] = {}
    duck = duckdb.connect()
    try:
        with registry.connect() as source:
            for table in SNAPSHOT_TABLES:
                destination = output_dir / f"{table}.parquet"
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
    (output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def export_training(registry: Registry, destination: Path, *, split: str, corpus: str) -> dict[str, object]:
    if leakage_findings(registry):
        raise PermissionError("cross-split lineage leakage blocks export")
    count = 0
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    table = {"audio": "audio_samples", "persona": "persona_samples", "agentic": "agentic_trajectories", "duplex": "duplex_timelines", "text": "text_samples"}[corpus]
    id_column = {"audio": "sample_id", "persona": "sample_id", "agentic": "trajectory_id", "duplex": "timeline_id", "text": "sample_id"}[corpus]
    with registry.connect() as connection, destination.open("wb") as output:
        query = f"""SELECT x.*, s.derivative_family FROM {table} x JOIN sources s ON s.source_id=x.source_id
                    JOIN split_assignments a ON a.group_id=s.derivative_family AND a.policy_version='source-split-v1'
                    WHERE x.training_status='accepted' AND a.split=? ORDER BY x.{id_column}"""
        for row in connection.execute(query, (split,)):
            registry.assert_exportable(connection, row["source_id"])
            record = {key: row[key] for key in row.keys()}
            line = _canonical_line(record)
            output.write(line)
            digest.update(line)
            count += 1
    return {"count": count, "sha256": digest.hexdigest(), "path": str(destination)}
