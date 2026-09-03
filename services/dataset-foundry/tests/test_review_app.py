from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import wave
from pathlib import Path

import pytest

from conftest import accept_source_review, source
from miku_foundry.export import export_training
from miku_foundry.eligibility import PERSONA_DIMENSIONS
from miku_foundry.review import add_review, gold_requires_double_review, promote_sample
from miku_foundry.review_server import create_server
from miku_foundry.rights import promote_training, register_rights
from miku_foundry.split import assign_group
from miku_foundry.store import ObjectStore


def audio_item(paths, registry, source_id: str, *, sample_id: str = "audio-review-item",
               quality_tier: str = "gold", training_status: str = "quarantine") -> tuple[str, str]:
    incoming = paths.root / "intake" / f"{sample_id}.wav"
    with wave.open(str(incoming), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 16000)
    digest = ObjectStore(paths, registry).ingest(incoming, source_id, media_type="audio/wav")
    with registry.transaction() as connection:
        connection.execute(
            "INSERT INTO audio_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (digest, 16000, 1, 1000, 2, 0, 0, 0, 1000000, "test-fixture", registry.now()),
        )
        connection.execute(
            """INSERT INTO audio_samples(
                 sample_id,source_id,object_sha256,duration_ms,language,raw_text,spoken_text,
                 normalized_text,modality,quality_ppm,alignment_ppm,review_weight_ppm,
                 source_tier_weight_ppm,quality_tier,training_status,parent_object_sha256,
                 segment_start_ms,segment_end_ms,clip_object_sha256,segment_fingerprint
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sample_id, source_id, digest, 1000, "ko-KR", "원문", "발화", "정규화", "speech",
             1000000, 1000000, 1000000, 1000000, quality_tier, training_status,
             digest, 0, 1000, digest, registry.segment_fingerprint(digest, 0, 1000, "정규화")),
        )
    return sample_id, digest


def human_evidence(media_reviewed_ms: int = 1000, *, read_complete: bool = False,
                   adjudication: bool = False) -> dict[str, object]:
    return {"actor_type": "human", "batch_size": 1,
            "media_reviewed_ms": media_reviewed_ms, "read_complete": read_complete,
            "adjudication": adjudication}


def test_gold_audio_requires_full_single_item_review_and_preserves_edits(foundry):
    paths, registry = foundry
    source_id = source(registry)
    sample_id, _ = audio_item(paths, registry, source_id)
    with pytest.raises(PermissionError, match="listened through"):
        add_review(registry, "audio", sample_id, "accept", "alice", "heard",
                   expected_revision=0, evidence=human_evidence(999))
    add_review(
        registry, "audio", sample_id, "quarantine", "alice", "fix transcript",
        expected_revision=0, evidence=human_evidence(0),
        edits={"raw_text": "수정 원문", "spoken_text": "수정 발화", "normalized_text": "수정",
               "segment_start_ms": 100, "segment_end_ms": 900},
    )
    with registry.connect() as connection:
        row = connection.execute("SELECT * FROM audio_samples WHERE sample_id=?", (sample_id,)).fetchone()
        evidence = json.loads(connection.execute(
            "SELECT evidence_json FROM review_evidence"
        ).fetchone()[0])
    assert (row["raw_text"], row["duration_ms"], row["segment_start_ms"], row["segment_end_ms"]) == (
        "수정 원문", 800, 100, 900
    )
    assert row["clip_object_sha256"] is None
    assert evidence["edits_before"]["raw_text"] == "원문"
    assert evidence["edits_after"]["raw_text"] == "수정 원문"


def test_gold_double_review_bucket_blocks_export_until_second_reviewer(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry, training="accepted")
    accept_source_review(registry, source_id)
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user", training_allowed=True)
    assign_group(registry, "family-a", split="train")
    sample_id = next(f"double-review-{i}" for i in range(100) if gold_requires_double_review(f"double-review-{i}"))
    audio_item(paths, registry, source_id, sample_id=sample_id, training_status="accepted")
    add_review(registry, "audio", sample_id, "accept", "alice", "heard",
               expected_revision=0, evidence=human_evidence())
    with pytest.raises(PermissionError, match="two independent"):
        export_training(registry, tmp_path / "blocked.jsonl", split="train", corpus="audio")
    add_review(registry, "audio", sample_id, "reject", "bob", "independent disagreement",
               expected_revision=1, evidence=human_evidence())
    add_review(registry, "audio", sample_id, "accept", "carol", "rechecked",
               expected_revision=2, evidence=human_evidence())
    with pytest.raises(PermissionError, match="adjudication"):
        export_training(registry, tmp_path / "disputed.jsonl", split="train", corpus="audio")
    add_review(registry, "audio", sample_id, "accept", "dave", "adjudicated",
               expected_revision=3, evidence=human_evidence(adjudication=True))
    assert export_training(registry, tmp_path / "accepted.jsonl", split="train", corpus="audio")["count"] == 1


def test_gold_corpus_double_review_coverage_is_at_least_ten_percent(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry, training="accepted")
    accept_source_review(registry, source_id)
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user", training_allowed=True)
    assign_group(registry, "family-a", split="train")
    sample_id = next(f"coverage-review-{i}" for i in range(100)
                     if not gold_requires_double_review(f"coverage-review-{i}"))
    audio_item(paths, registry, source_id, sample_id=sample_id, training_status="accepted")
    add_review(registry, "audio", sample_id, "accept", "alice", "heard",
               expected_revision=0, evidence=human_evidence())
    with pytest.raises(PermissionError, match="double-review coverage"):
        export_training(registry, tmp_path / "blocked.jsonl", split="train", corpus="audio")
    add_review(registry, "audio", sample_id, "accept", "bob", "independent review",
               expected_revision=1, evidence=human_evidence())
    assert export_training(registry, tmp_path / "accepted.jsonl", split="train", corpus="audio")["count"] == 1


def test_gold_persona_requires_human_read_confirmation(foundry):
    _, registry = foundry
    source_id = source(registry)
    with registry.transaction() as connection:
        connection.execute(
            "INSERT INTO persona_samples VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("persona-review-item", source_id, "질문", "답변", "{}", 0, 1000000,
             "gold", "{}", "quarantine"),
        )
    with pytest.raises(PermissionError, match="human actor"):
        add_review(
            registry, "persona", "persona-review-item", "accept", "critic", "scored",
            expected_revision=0,
            evidence={"actor_type": "evaluator", "batch_size": 1, "media_reviewed_ms": 0},
        )
    with pytest.raises(PermissionError, match="must be read"):
        add_review(registry, "persona", "persona-review-item", "accept", "alice", "read",
                   expected_revision=0, evidence=human_evidence(0))
    add_review(registry, "persona", "persona-review-item", "accept", "alice", "read",
               expected_revision=0, evidence=human_evidence(0, read_complete=True))


def test_sample_promotion_rechecks_source_review_and_quality(foundry):
    paths, registry = foundry
    source_id = source(registry)
    register_rights(registry, source_id, "owned", "record", "fixture", "training",
                    reviewer="operator", actor_type="user", training_allowed=True)
    accept_source_review(registry, source_id)
    promote_training(registry, source_id, actor="operator")
    sample_id, _ = audio_item(paths, registry, source_id, quality_tier="silver")
    add_review(
        registry, "audio", sample_id, "accept", "critic", "validated",
        expected_revision=0,
        evidence={"actor_type": "evaluator", "batch_size": 1, "media_reviewed_ms": 0},
    )
    with registry.connect() as connection:
        assert connection.execute(
            "SELECT training_status FROM audio_samples WHERE sample_id=?", (sample_id,)
        ).fetchone()[0] == "quarantine"
    assert promote_sample(registry, "audio", sample_id, actor="operator") is True
    assert promote_sample(registry, "audio", sample_id, actor="operator") is False

    persona_id = next(f"hard-violation-{i}" for i in range(100)
                      if not gold_requires_double_review(f"hard-violation-{i}"))
    annotation = {name: {"score": 1000000, "reason_code": "reviewed", "evaluator_id": "critic",
                         "evaluator_revision": "1", "confidence_ppm": 1000000,
                         "human_override": None} for name in PERSONA_DIMENSIONS}
    with registry.transaction() as connection:
        connection.execute(
            "INSERT INTO persona_samples VALUES (?,?,?,?,?,?,?,?,?,?)",
            (persona_id, source_id, "질문", "위반 응답", json.dumps(annotation), 1, 1000000,
             "gold", "{}", "quarantine"),
        )
    add_review(registry, "persona", persona_id, "accept", "alice", "read",
               expected_revision=0, evidence=human_evidence(0, read_complete=True))
    with pytest.raises(PermissionError, match="hard violation"):
        promote_sample(registry, "persona", persona_id, actor="operator")


def test_local_review_application_serves_detail_range_and_revision_safe_post(foundry):
    paths, registry = foundry
    source_id = source(registry)
    register_rights(registry, source_id, "owned", "record", "fixture", "technical-pilot",
                    reviewer="operator", actor_type="user")
    sample_id, digest = audio_item(paths, registry, source_id, quality_tier="silver")
    server = create_server(paths, registry, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    token = server.review_token  # type: ignore[attr-defined]
    try:
        root = urllib.request.urlopen(base + "/", timeout=2)
        assert b"waveform" in root.read() and "nonce-" in root.headers["Content-Security-Policy"]
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(base + "/api/review-queue?entity_type=audio", timeout=2)
        assert denied.value.code == 403
        request = urllib.request.Request(
            base + "/api/review-items/audio/" + sample_id,
            headers={"X-Review-Token": token},
        )
        detail = json.load(urllib.request.urlopen(request, timeout=2))
        assert detail["playback_sha256"] == digest and detail["rights"]["status"] == "owned"
        request = urllib.request.Request(base + "/objects/" + digest, headers={"Range": "bytes=0-15"})
        response = urllib.request.urlopen(request, timeout=2)
        assert response.status == 206 and len(response.read()) == 16
        payload = json.dumps({
            "entity_type": "audio", "entity_id": sample_id, "decision": "quarantine",
            "reviewer": "alice", "reason": "needs work", "expected_revision": 0,
            "evidence": human_evidence(0),
            "edits": {"raw_text": "수정", "spoken_text": "발화", "normalized_text": "수정",
                      "segment_start_ms": 0, "segment_end_ms": 1000},
        }, ensure_ascii=False).encode()
        request = urllib.request.Request(
            base + "/api/reviews", data=payload, method="POST",
            headers={"Content-Type": "application/json", "X-Review-Token": token},
        )
        assert urllib.request.urlopen(request, timeout=2).status == 201
        with registry.connect() as connection:
            assert connection.execute("SELECT decision FROM reviews").fetchone()[0] == "quarantine"
            assert connection.execute("SELECT raw_text FROM audio_samples").fetchone()[0] == "수정"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
