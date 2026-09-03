from __future__ import annotations

from pathlib import Path

import pytest

from conftest import accept_source_review, source
import miku_foundry.export as export_module
from miku_foundry.export import canonical_manifest, export_training
from miku_foundry.lineage import add_lineage, plan_transform
from miku_foundry.review import add_review
from miku_foundry.rights import register_rights
from miku_foundry.split import assign_group, leakage_findings
from miku_foundry.store import ObjectStore


def _audio_row(registry, source_id: str, digest: str, training_status: str = "accepted") -> str:
    sample_id = registry.new_id()
    with registry.transaction() as connection:
        connection.execute(
            "INSERT INTO audio_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (digest, 16000, 1, 1000, 2, 0, 0, 0, 0, "test-fixture", registry.now()),
        )
        connection.execute(
            """INSERT INTO audio_samples(
                 sample_id,source_id,object_sha256,duration_ms,language,raw_text,spoken_text,
                 normalized_text,modality,quality_ppm,alignment_ppm,review_weight_ppm,
                 source_tier_weight_ppm,quality_tier,training_status,parent_object_sha256,
                 segment_start_ms,segment_end_ms,clip_object_sha256,segment_fingerprint
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sample_id, source_id, digest, 1000, "ko-KR", "안녕", "안녕", "안녕", "speech",
             1000000, 1000000, 1000000, 1000000, "silver", training_status,
             digest, 0, 1000, digest, registry.segment_fingerprint(digest, 0, 1000, "안녕")),
        )
    return sample_id


def test_canonical_manifest_is_byte_stable_for_same_registry(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry, training="accepted")
    accept_source_review(registry, source_id)
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user", training_allowed=True)
    assign_group(registry, "family-a", split="train")
    payload = tmp_path / "input.bin"
    payload.write_bytes(b"sample")
    digest = ObjectStore(paths, registry).ingest(payload, source_id)
    _audio_row(registry, source_id, digest)
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first_result = canonical_manifest(registry, first)
    assert first_result == canonical_manifest(registry, second)
    assert first.read_bytes() == second.read_bytes()
    register_rights(
        registry, source_id, "owned", "record", "scope changed", "not for training",
        reviewer="operator", actor_type="user", training_allowed=False,
    )
    rights_changed = tmp_path / "rights-changed.jsonl"
    rights_result = canonical_manifest(registry, rights_changed)
    assert rights_result[0] != first_result[0]
    with registry.transaction() as connection:
        connection.execute("UPDATE audio_samples SET quality_ppm=900000 WHERE source_id=?", (source_id,))
    metadata_changed = tmp_path / "metadata-changed.jsonl"
    metadata_result = canonical_manifest(registry, metadata_changed)
    assert metadata_result[0] != rights_result[0]
    add_review(
        registry, "source", source_id, "reject", "operator", "source review revoked",
        expected_revision=1,
        evidence={"actor_type": "evaluator", "batch_size": 1, "media_reviewed_ms": 0},
    )
    source_review_changed = tmp_path / "source-review-changed.jsonl"
    assert canonical_manifest(registry, source_review_changed)[0] != metadata_result[0]


def test_failed_snapshot_leaves_no_final_or_staging_directory(foundry, monkeypatch):
    paths, registry = foundry

    def fail_manifest(*_args):
        raise RuntimeError("injected snapshot failure")

    monkeypatch.setattr(export_module, "canonical_manifest", fail_manifest)
    with pytest.raises(RuntimeError, match="injected snapshot failure"):
        export_module.snapshot(registry, paths, "failed-snapshot")
    assert not (paths.snapshots / "failed-snapshot").exists()
    assert not list(paths.snapshots.glob(".failed-snapshot.*"))


def test_current_rights_revocation_blocks_export(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry, training="accepted")
    accept_source_review(registry, source_id)
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user", training_allowed=True)
    assign_group(registry, "family-a", split="train")
    payload = tmp_path / "input.bin"
    payload.write_bytes(b"sample")
    digest = ObjectStore(paths, registry).ingest(payload, source_id)
    _audio_row(registry, source_id, digest)
    register_rights(registry, source_id, "restricted", "revocation", "operator decision", "none",
                    reviewer="operator", actor_type="user")
    with pytest.raises(PermissionError):
        export_training(registry, tmp_path / "export.jsonl", split="train", corpus="audio")


def test_training_export_requires_evidence_backed_sample_review(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry, training="accepted")
    accept_source_review(registry, source_id)
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user", training_allowed=True)
    assign_group(registry, "family-a", split="train")
    payload = tmp_path / "input.bin"
    payload.write_bytes(b"sample")
    digest = ObjectStore(paths, registry).ingest(payload, source_id)
    sample_id = _audio_row(registry, source_id, digest)
    blocked = tmp_path / "blocked.jsonl"
    blocked.write_bytes(b"preserve existing export")
    with pytest.raises(PermissionError, match="evidence-backed"):
        export_training(registry, blocked, split="train", corpus="audio")
    assert blocked.read_bytes() == b"preserve existing export"
    add_review(
        registry, "audio", sample_id, "accept", "reviewer-a", "quality checked",
        expected_revision=0,
        evidence={"actor_type": "evaluator", "batch_size": 1, "media_reviewed_ms": 0},
    )
    assert export_training(registry, tmp_path / "accepted.jsonl", split="train", corpus="audio")["count"] == 1
    add_review(
        registry, "source", source_id, "reject", "operator", "source review revoked",
        expected_revision=1,
        evidence={"actor_type": "evaluator", "batch_size": 1, "media_reviewed_ms": 0},
    )
    with pytest.raises(PermissionError, match="source lacks"):
        export_training(registry, tmp_path / "revoked.jsonl", split="train", corpus="audio")


def test_transitive_lineage_group_mismatch_is_reported(foundry, tmp_path: Path):
    paths, registry = foundry
    parent_source = source(registry, family="train-family")
    child_source = source(registry, family="eval-family")
    assign_group(registry, "train-family", split="train")
    assign_group(registry, "eval-family", split="eval", freeze=True)
    parent_file = tmp_path / "parent.bin"
    child_file = tmp_path / "child.bin"
    parent_file.write_bytes(b"parent")
    child_file.write_bytes(b"child")
    store = ObjectStore(paths, registry)
    parent = store.ingest(parent_file, parent_source)
    child = store.ingest(child_file, child_source)
    transform = plan_transform(registry, "test", [parent], {"operation": "derive"}, tool="fixture", tool_version="1")
    add_lineage(registry, transform, [parent], child)
    assert leakage_findings(registry) == [{"parent_group": "train-family", "child_group": "eval-family",
                                           "parent_split": "train", "child_split": "eval"}]
