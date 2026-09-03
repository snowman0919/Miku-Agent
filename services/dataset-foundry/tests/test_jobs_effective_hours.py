from __future__ import annotations

import json
import hashlib
import sqlite3

import pytest

from conftest import accept_source_review, source
from miku_foundry.effective_hours import summarize
from miku_foundry.jobs import authorize_remote_5090, canonical_json, ensure_job, prepare_remote_package
from miku_foundry.review import add_review
from miku_foundry.rights import register_rights
from miku_foundry.store import ObjectStore


def test_remote_job_never_stages_without_job_bound_grant(foundry):
    _, registry = foundry
    manifest = {"inputs": ["a" * 64], "code_commit": "b" * 40}
    job_id = ensure_job(registry, "remote-5090", manifest)
    assert ensure_job(registry, "remote-5090", manifest) == job_id
    with pytest.raises(PermissionError):
        authorize_remote_5090(registry, job_id, None)
    with pytest.raises(PermissionError):
        authorize_remote_5090(registry, job_id, {"job_id": "wrong", "allowed": True,
                                                 "input_digest": "a" * 64, "code_commit": "b" * 40})
    with registry.connect() as connection:
        assert connection.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0] == "prepared"


def test_remote_package_is_waiting_and_contains_no_database_binding(foundry):
    paths, registry = foundry
    source_id = source(registry)
    register_rights(registry, source_id, "owned", "fixture", "test", "technical-pilot",
                    reviewer="operator", actor_type="user")
    input_path = paths.root / "intake" / "input.bin"
    input_path.write_bytes(b"input")
    digest = ObjectStore(paths, registry).ingest(input_path, source_id)
    manifest = {
        "task_type": "audio_quality", "input_object_hashes": [digest],
        "foundry_code_commit": "b" * 40, "created_at": "2026-09-03T00:00:00Z",
        "worker_spec": {"code_commit": "b" * 40, "software_environment": {"python": "3.11"},
                        "determinism": "deterministic", "seed": 0, "model_binding": None},
        "source_binding": {"source_ids": [source_id], "rights_status": "owned"},
        "transform": {"name": "audio_quality", "version": "reference-1", "parameters": {}},
        "resource_request": {"gpu_count": 0, "min_vram_bytes": 0,
                             "cpu_threads": 1, "ram_bytes": 1024},
    }
    job_id, state = prepare_remote_package(paths, registry, manifest)
    assert state == "waiting_for_lease"
    package = paths.root / "jobs" / "remote-5090" / job_id
    assert {path.name for path in package.iterdir()} == {
        "job.json", "input-manifest.json", "worker-spec.json", "source-binding.json",
        "expected-output.schema.json", "inputs",
    }
    texts = "".join(path.read_text(encoding="utf-8").lower() for path in package.iterdir() if path.is_file())
    assert "sqlite" not in texts
    authorize_remote_5090(registry, job_id, {
        "job_id": job_id, "allowed": True,
        "input_digest": hashlib.sha256(canonical_json([digest]).encode()).hexdigest(),
        "code_commit": "b" * 40,
    })


def test_singing_stt_and_unknown_rights_never_inflate_target_speech_hours(foundry):
    _, registry = foundry
    cleared = source(registry, family="cleared", training="accepted")
    unknown = source(registry, family="unknown", training="accepted")
    singing = source(registry, family="singing", training="accepted")
    stt = source(registry, family="stt", training="accepted")
    with registry.transaction() as connection:
        connection.execute("UPDATE sources SET source_type='stt',character_id='non-target' WHERE source_id=?", (stt,))
    register_rights(registry, cleared, "owned", "record", "fixture", "training", reviewer="op", actor_type="user", training_allowed=True)
    register_rights(registry, unknown, "unknown", "discovery", "unverified", "none", reviewer="op", actor_type="user")
    register_rights(registry, singing, "owned", "record", "fixture", "auxiliary", reviewer="op", actor_type="user", training_allowed=True)
    register_rights(registry, stt, "owned", "record", "fixture", "stt training", reviewer="op", actor_type="user", training_allowed=True)
    accept_source_review(registry, cleared)
    accept_source_review(registry, singing)
    accept_source_review(registry, stt)
    accepted_samples = []
    with registry.transaction() as connection:
        for index, (source_id, modality, duration) in enumerate(((cleared, "speech", 3600000),
                                                                  (unknown, "speech", 1800000),
                                                                  (singing, "singing_aux", 7200000),
                                                                  (stt, "speech", 3600000))):
            digest = f"{index + 1:064x}"
            now = registry.now()
            connection.execute("INSERT INTO objects VALUES (?,?,?,?,?)", (digest, 1, None, now, now))
            sample_id = registry.new_id()
            connection.execute(
                "INSERT INTO audio_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (digest, 16000, 1, duration, 2, 0, 0, 0, 0, "test-fixture", now),
            )
            connection.execute(
                """INSERT INTO audio_samples(
                     sample_id,source_id,object_sha256,duration_ms,language,raw_text,spoken_text,
                     normalized_text,modality,quality_ppm,alignment_ppm,review_weight_ppm,
                     source_tier_weight_ppm,quality_tier,training_status,parent_object_sha256,
                     segment_start_ms,segment_end_ms,clip_object_sha256,segment_fingerprint
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sample_id, source_id, digest, duration, "ko-KR", "x", "x", "x", modality,
                 1000000, 1000000, 1000000, 1000000,
                 "auxiliary" if modality == "singing_aux" else "silver" if source_id == stt else "gold", "accepted",
                 digest, 0, duration, digest, registry.segment_fingerprint(digest, 0, duration, "x")),
            )
            if source_id != unknown:
                accepted_samples.append((sample_id, duration, modality, source_id))
    for sample_id, duration, modality, source_id in accepted_samples:
        add_review(
            registry, "audio", sample_id, "accept", "operator", "audio checked", expected_revision=0,
            evidence={"actor_type": "evaluator" if source_id == stt or modality == "singing_aux" else "human",
                      "batch_size": 1, "media_reviewed_ms": duration},
        )
    result = summarize(registry)
    assert result["raw_speech_ms"] == 9000000
    assert result["accepted_physical_speech_ms"] == 3600000
    assert result["effective_speech_ms"] == 3600000
    assert result["accepted_stt_ms"] == 3600000
    assert result["raw_singing_ms"] == 7200000
    assert result["accepted_auxiliary_singing_ms"] == 7200000


def test_duplicate_and_overlapping_segments_do_not_inflate_physical_duration(foundry):
    _, registry = foundry
    source_id = source(registry)
    digest = "a" * 64
    with registry.transaction() as connection:
        now = registry.now()
        connection.execute("INSERT INTO objects VALUES (?,?,?,?,?)", (digest, 1, None, now, now))
        connection.execute(
            "INSERT INTO audio_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (digest, 16000, 1, 1500, 2, 0, 0, 0, 0, "test-fixture", now),
        )
        for index, (start, end) in enumerate(((0, 1000), (0, 1000), (500, 1500))):
            connection.execute(
                """INSERT INTO audio_samples(
                     sample_id,source_id,object_sha256,duration_ms,language,raw_text,spoken_text,
                     normalized_text,modality,quality_ppm,alignment_ppm,review_weight_ppm,
                     source_tier_weight_ppm,quality_tier,training_status,parent_object_sha256,
                     segment_start_ms,segment_end_ms,clip_object_sha256,segment_fingerprint
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (registry.new_id(), source_id, digest, end - start, "ko-KR", "", "", "",
                 "speech", 0, 0, 0, 0, "quarantine", "quarantine", digest, start, end, None,
                 registry.segment_fingerprint(digest, start, end, "")),
            )
    result = summarize(registry)
    assert result["row_count"] == 3
    assert result["unique_sample_count"] == 2
    assert result["referenced_duration_ms"] == 3000
    assert result["unique_physical_interval_ms"] == 1500
    with registry.connect() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE audio_samples SET duration_ms=duration_ms+1 "
            "WHERE sample_id=(SELECT sample_id FROM audio_samples LIMIT 1)"
        )
    with registry.connect() as connection, pytest.raises(sqlite3.IntegrityError, match="unverified parent"):
        connection.execute(
            "UPDATE audio_samples SET duration_ms=1600,segment_end_ms=1600 "
            "WHERE sample_id=(SELECT sample_id FROM audio_samples WHERE segment_start_ms=0 LIMIT 1)"
        )
