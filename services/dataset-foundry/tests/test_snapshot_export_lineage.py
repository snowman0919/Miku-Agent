from __future__ import annotations

from pathlib import Path

import pytest

from conftest import source
from miku_foundry.export import canonical_manifest, export_training
from miku_foundry.lineage import add_lineage, plan_transform
from miku_foundry.rights import register_rights
from miku_foundry.split import assign_group, leakage_findings
from miku_foundry.store import ObjectStore


def _audio_row(registry, source_id: str, digest: str, training_status: str = "accepted") -> None:
    with registry.transaction() as connection:
        connection.execute(
            """INSERT INTO audio_samples(
                 sample_id,source_id,object_sha256,duration_ms,language,raw_text,spoken_text,
                 normalized_text,modality,quality_ppm,alignment_ppm,review_weight_ppm,
                 source_tier_weight_ppm,quality_tier,training_status,parent_object_sha256,
                 segment_start_ms,segment_end_ms,clip_object_sha256,segment_fingerprint
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (registry.new_id(), source_id, digest, 1000, "ko-KR", "안녕", "안녕", "안녕", "speech",
             1000000, 1000000, 1000000, 1000000, "gold", training_status,
             digest, 0, 1000, digest, registry.segment_fingerprint(digest, 0, 1000, "안녕")),
        )


def test_canonical_manifest_is_byte_stable_for_same_registry(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry, training="accepted")
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user")
    assign_group(registry, "family-a", split="train")
    payload = tmp_path / "input.bin"
    payload.write_bytes(b"sample")
    digest = ObjectStore(paths, registry).ingest(payload, source_id)
    _audio_row(registry, source_id, digest)
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    assert canonical_manifest(registry, first) == canonical_manifest(registry, second)
    assert first.read_bytes() == second.read_bytes()


def test_current_rights_revocation_blocks_export(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry, training="accepted")
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user")
    assign_group(registry, "family-a", split="train")
    payload = tmp_path / "input.bin"
    payload.write_bytes(b"sample")
    digest = ObjectStore(paths, registry).ingest(payload, source_id)
    _audio_row(registry, source_id, digest)
    register_rights(registry, source_id, "restricted", "revocation", "operator decision", "none",
                    reviewer="operator", actor_type="user")
    with pytest.raises(PermissionError):
        export_training(registry, tmp_path / "export.jsonl", split="train", corpus="audio")


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
