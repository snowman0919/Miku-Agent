from __future__ import annotations

import gzip
import hashlib
import json
import uuid
from pathlib import Path

import pytest

from miku_foundry.effective_hours import summarize
from miku_foundry.ingest import register_source
from miku_foundry.rights import promote_training, register_rights
from miku_foundry.review import add_review
from miku_foundry.split import assign_group
from miku_foundry.stt import ARCHIVE_SHA256, POLICY, POLICY_SHA256, import_zeroth_stt


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_zeroth_stt_import_is_bound_validated_and_idempotent(foundry, tmp_path: Path):
    paths, registry = foundry
    audio_root = tmp_path / "audio"
    audio = audio_root / "train_data_01" / "003" / "194" / "194_003_0001.flac"
    audio.parent.mkdir(parents=True)
    packed = (16000 << 44) | (15 << 36) | 16000
    audio.write_bytes(b"fLaC" + b"\x80\x00\x00\x22" + b"\x10\x00\x10\x00" + b"\0" * 6
                      + packed.to_bytes(8, "big") + b"\0" * 16)
    digest = _sha256(audio)
    archive_sha256 = ARCHIVE_SHA256
    text = "안녕하세요"
    row = {
        "sample_id": str(uuid.uuid5(
            uuid.NAMESPACE_URL, f"openslr:40\0{archive_sha256}\0{audio.stem}\0{digest}"
        )),
        "utterance_id": audio.stem, "speaker_id": "194", "path": audio.relative_to(audio_root).as_posix(),
        "audio_sha256": digest, "size_bytes": audio.stat().st_size,
        "raw_text": text, "spoken_text": text, "normalized_text": text,
        "audio_metrics": {
            "sample_rate_hz": 16000, "channels": 1, "bits_per_sample": 16,
            "total_samples": 16000, "duration_ms": 1000, "peak_ppm": 500000,
            "clipping_ppm": 0, "dc_offset_ppm": 0, "silence_ppm": 100000,
            "decode_status": "passed",
        },
        "asr": {"status": "passed", "hypothesis": text, "cer_ppm": 0},
        "alignment": {"status": "passed", "word_intervals": 1, "phone_intervals": 1,
                      "spn_intervals": 0, "boundary_anomalies": 0, "coverage_ppm": 900000,
                      "tiers": {"words": [[0.0, 0.9, text]], "phones": [[0.0, 0.9, "a"]]}},
    }
    bundle = tmp_path / "zeroth.jsonl.gz"
    canonical_row = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with bundle.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
        stream.write((canonical_row + "\n").encode())
    bindings = {
        "asr": {"model_id": "openai/whisper-large-v3-turbo",
                "revision": "41f01f3fe87f28c78e2fbf8b568835947dd65ed9",
                "weight_sha256": "542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1",
                "config_sha256": "c5b526b3e3cd64cd8940dabb45e8ba726629e22d8ed389c29b552f9140daf04a"},
        "alignment": {"model_id": "montreal-forced-aligner/korean_mfa-3.0.0",
                      "revision": "f76a59f7491eadda0fee212b329521e20e349e75",
                      "acoustic_sha256": "46f7a73ab46828c679562b160e0577beecfb4a9a827efe5ab392aee947451a4d",
                      "dictionary_sha256": "75683f4dc2a7dd95295a068206d248a30bd2f4f2231fd4449210c91d1e78150b"},
    }
    manifest = {
        "format": "miku-zeroth-korean-stt-bundle-v1", "policy": POLICY,
        "policy_sha256": POLICY_SHA256, "processor_revision": "1" * 40,
        "archive": {"url": "https://openslr.org/40/", "license": "CC-BY-4.0",
                    "sha256": archive_sha256, "size_bytes": 10339720618},
        "bundle": bundle.name, "bundle_sha256": _sha256(bundle),
        "evaluation_transcript_sha256": [hashlib.sha256("평가 문장".encode()).hexdigest()],
        "bindings": bindings,
        **{f"{name}_binding_sha256": hashlib.sha256(json.dumps(
            binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest() for name, binding in bindings.items()},
        "decoder": "flac-test/1", "stats": {"accepted_rows": 1,
            "accepted_duration_ms": 1000, "accepted_audio_bytes": audio.stat().st_size},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    source_id = register_source(
        registry, source_id=None, source_type="stt", title="Zeroth fixture",
        origin="https://openslr.org/40/", acquisition_method="verified official corpus",
        language="ko-KR", character_id="non-target", derivative_family="zeroth-fixture",
        quality_status="passed", review_status="reviewed",
    )
    register_rights(registry, source_id, "licensed", "license", "CC BY 4.0 fixture",
                    "private ML training", reviewer="operator", actor_type="user",
                    training_allowed=True)
    add_review(registry, "source", source_id, "accept", "operator", "source reviewed",
               expected_revision=0, evidence={"actor_type": "evaluator", "batch_size": 1})
    promote_training(registry, source_id, actor="operator")
    assign_group(registry, "zeroth-fixture", split="train", freeze=True)

    with pytest.raises(PermissionError, match="exact manifest"):
        import_zeroth_stt(paths, registry, manifest_path, audio_root, source_id,
                          actor="operator", dry_run=True)
    add_review(registry, "source", source_id, "accept", "operator", "exact STT bundle reviewed",
               expected_revision=1, evidence={"actor_type": "evaluator", "batch_size": 1,
                                               "stt_manifest_sha256": _sha256(manifest_path)})
    assert import_zeroth_stt(paths, registry, manifest_path, audio_root, source_id,
                             actor="operator", dry_run=True)["count"] == 1
    row["asr"]["cer_ppm"] = 1
    with bundle.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
        stream.write((json.dumps(row, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n").encode())
    manifest["bundle_sha256"] = _sha256(bundle)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="baseline or alignment"):
        import_zeroth_stt(paths, registry, manifest_path, audio_root, source_id,
                          actor="operator", dry_run=True)

    row["asr"]["cer_ppm"] = 0
    row["alignment"]["tiers"]["phones"][0][1] = 1.5
    with bundle.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
        stream.write((json.dumps(row) + "\n").encode())
    manifest["bundle_sha256"] = _sha256(bundle)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid STT alignment interval"):
        import_zeroth_stt(paths, registry, manifest_path, audio_root, source_id,
                          actor="operator", dry_run=True)
    with bundle.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
        stream.write((canonical_row + "\n").encode())
    manifest["bundle_sha256"] = _sha256(bundle)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = import_zeroth_stt(paths, registry, manifest_path, audio_root, source_id, actor="operator")
    assert result["count"] == 1 and result["duration_ms"] == 1000
    assert import_zeroth_stt(paths, registry, manifest_path, audio_root, source_id,
                             actor="operator")["idempotent"] is True
    totals = summarize(registry)
    assert totals["accepted_stt_ms"] == 1000
    assert totals["accepted_physical_speech_ms"] == totals["effective_speech_ms"] == 0
    with registry.connect() as connection:
        assert connection.execute("SELECT count(*) FROM review_evidence").fetchone()[0] == 3
    manifest["stats"]["accepted_duration_ms"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="different STT import"):
        import_zeroth_stt(paths, registry, manifest_path, audio_root, source_id, actor="operator")
