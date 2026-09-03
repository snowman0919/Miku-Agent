from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import shutil
import unicodedata
import uuid
from pathlib import Path, PurePosixPath
from typing import Iterator

from .config import FoundryPaths
from .registry import Registry
from .store import ObjectStore


POLICY = {
    "id": "openslr-zeroth-korean-stt-v1",
    "audio": "original lossless FLAC bytes; full worker decode required",
    "format": {"bits_per_sample": 16, "channels": 1, "sample_rate_hz": 16000},
    "transcript": "Unicode NFC and collapsed whitespace",
    "split": "official speaker-disjoint train/test; exclude normalized test transcripts from train",
    "asr": "pinned independent baseline required; CER measured but not used as an automatic threshold",
    "alignment": "pinned Korean MFA word and phone timing required with bounded intervals",
}
POLICY_SHA256 = hashlib.sha256(
    json.dumps(POLICY, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
ARCHIVE_SHA256 = "6e109897f4d866eb1a3d31cbb2220c0b5e3dc74704208189ecc3bec787740e5f"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def _asr_text(value: str) -> str:
    return "".join(TOKEN_RE.findall(_normalize(value).casefold()))


def _cer_ppm(reference: str, hypothesis: str) -> int:
    left, right = _asr_text(reference), _asr_text(hypothesis)
    if not left:
        raise ValueError("empty normalized STT reference")
    previous = list(range(len(right) + 1))
    for index, char in enumerate(left, 1):
        current = [index]
        for offset, other in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[offset] + 1,
                               previous[offset - 1] + (char != other)))
        previous = current
    return previous[-1] * 1_000_000 // len(left)


def _flac_streaminfo(path: Path) -> dict[str, int]:
    with path.open("rb") as stream:
        if stream.read(4) != b"fLaC":
            raise ValueError("audio is not FLAC")
        header = stream.read(4)
        if len(header) != 4 or header[0] & 0x7f or int.from_bytes(header[1:], "big") != 34:
            raise ValueError("FLAC STREAMINFO is missing")
        value = stream.read(34)
    if len(value) != 34:
        raise ValueError("truncated FLAC STREAMINFO")
    packed = int.from_bytes(value[10:18], "big")
    sample_rate = packed >> 44
    channels = ((packed >> 41) & 7) + 1
    bits = ((packed >> 36) & 31) + 1
    samples = packed & ((1 << 36) - 1)
    if not sample_rate or not samples:
        raise ValueError("invalid FLAC duration")
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "bits_per_sample": bits,
        "total_samples": samples,
        "duration_ms": samples * 1000 // sample_rate,
    }


def _audio_path(root: Path, value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("STT audio path is required")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".flac":
        raise ValueError("invalid STT audio path")
    candidate = root.joinpath(*relative.parts)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("STT audio must be a regular non-symlink file")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("STT audio path escapes its root")
    return resolved


def _check_alignment(value: dict[str, object], duration_ms: int) -> None:
    tiers = value.get("tiers")
    if not isinstance(tiers, dict):
        raise ValueError("STT alignment lacks interval evidence")
    for name, count in (("words", "word_intervals"), ("phones", "phone_intervals")):
        entries = tiers.get(name)
        if not isinstance(entries, list) or not entries or len(entries) != value[count]:
            raise ValueError("STT alignment interval count differs")
        previous = 0.0
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 3:
                raise ValueError("invalid STT alignment interval")
            start, end, label = entry
            if (type(start) not in (int, float) or type(end) not in (int, float)
                    or not math.isfinite(start) or not math.isfinite(end)
                    or start < previous - 1e-6 or end <= start or end * 1000 > duration_ms + 1
                    or not isinstance(label, str) or not label):
                raise ValueError("invalid STT alignment interval")
            previous = end
    phones = tiers["phones"]
    coverage = min(1_000_000, round(sum(end - start for start, end, _ in phones)
                                  * 1_000_000_000 / duration_ms))
    if (coverage != value["coverage_ppm"]
            or sum(label == "spn" for _, _, label in phones) != value["spn_intervals"]):
        raise ValueError("STT alignment summary differs from intervals")


def _assert_manifest_review(connection, source_id: str, digest: str) -> None:
    row = connection.execute(
        """SELECT e.evidence_json FROM reviews r JOIN review_evidence e USING(review_id)
           WHERE r.entity_type='source' AND r.entity_id=?
           ORDER BY r.revision DESC LIMIT 1""", (source_id,),
    ).fetchone()
    evidence = json.loads(row[0]) if row else {}
    if evidence.get("stt_manifest_sha256") != digest:
        raise PermissionError("STT source review does not approve this exact manifest")


def _records(manifest: dict[str, object], bundle: Path, audio_root: Path) -> Iterator[dict[str, object]]:
    seen_ids: set[str] = set()
    seen_audio: set[str] = set()
    test_hashes = set(manifest["evaluation_transcript_sha256"])
    with gzip.open(bundle, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            required = {
                "sample_id", "utterance_id", "speaker_id", "path", "audio_sha256", "size_bytes",
                "raw_text", "spoken_text", "normalized_text", "audio_metrics", "asr", "alignment",
            }
            if not isinstance(row, dict) or set(row) != required:
                raise ValueError("invalid STT row fields")
            sample_id, digest = row["sample_id"], row["audio_sha256"]
            if (not isinstance(sample_id, str) or not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    or any(not isinstance(row[key], str) or not row[key].strip()
                           for key in ("utterance_id", "speaker_id", "raw_text", "spoken_text",
                                       "normalized_text"))
                    or sample_id in seen_ids or digest in seen_audio):
                raise ValueError("invalid or duplicate STT identity")
            path = _audio_path(audio_root, row["path"])
            actual_digest, size = ObjectStore.hash_file(path)
            info = _flac_streaminfo(path)
            metrics = row["audio_metrics"]
            if (actual_digest != digest or size != row["size_bytes"] or not isinstance(metrics, dict)
                    or any(info[key] != expected for key, expected in POLICY["format"].items())
                    or info != {key: metrics.get(key) for key in info}
                    or any(not isinstance(metrics.get(key), int) or isinstance(metrics.get(key), bool)
                           or not 0 <= metrics[key] <= 1_000_000
                           for key in ("peak_ppm", "clipping_ppm", "dc_offset_ppm", "silence_ppm"))
                    or metrics.get("decode_status") != "passed"):
                raise ValueError("STT audio hash, stream metadata, or decode evidence differs")
            transcript = _normalize(str(row["raw_text"]))
            if (not transcript or row["spoken_text"] != transcript or row["normalized_text"] != transcript
                    or hashlib.sha256(transcript.encode()).hexdigest() in test_hashes):
                raise ValueError("invalid or evaluation-overlapping STT transcript")
            asr, alignment = row["asr"], row["alignment"]
            if (not isinstance(asr, dict) or asr.get("status") != "passed"
                    or not isinstance(asr.get("hypothesis"), str)
                    or asr.get("cer_ppm") != _cer_ppm(transcript, asr["hypothesis"])
                    or not isinstance(alignment, dict) or alignment.get("status") != "passed"
                    or any(not isinstance(alignment.get(key), int) or isinstance(alignment.get(key), bool)
                           or alignment[key] < 0 for key in ("word_intervals", "phone_intervals", "spn_intervals"))
                    or alignment["word_intervals"] == 0 or alignment["phone_intervals"] == 0
                    or alignment.get("boundary_anomalies") != 0
                    or not isinstance(alignment.get("coverage_ppm"), int)
                    or not 0 < alignment["coverage_ppm"] <= 1_000_000):
                raise ValueError("STT baseline or alignment evidence is invalid")
            _check_alignment(alignment, info["duration_ms"])
            expected_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"openslr:40\0{manifest['archive']['sha256']}\0{row['utterance_id']}\0{digest}",
            ))
            relative = PurePosixPath(row["path"])
            if (sample_id != expected_id or len(relative.parts) != 4
                    or relative.parts[0] != "train_data_01" or relative.parts[2] != row["speaker_id"]
                    or relative.stem != row["utterance_id"]
                    or not relative.stem.startswith(f"{row['speaker_id']}_{relative.parts[1]}_")):
                raise ValueError("STT sample provenance does not match its source path")
            seen_ids.add(sample_id)
            seen_audio.add(digest)
            yield row | {"_path": path}


def import_zeroth_stt(
    paths: FoundryPaths, registry: Registry, manifest_path: Path, audio_root: Path,
    source_id: str, *, actor: str, dry_run: bool = False,
) -> dict[str, object]:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("actor is required")
    manifest_path = manifest_path.resolve(strict=True)
    audio_root = audio_root.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict)
            or manifest.get("format") != "miku-zeroth-korean-stt-bundle-v1"
            or manifest.get("policy") != POLICY or manifest.get("policy_sha256") != POLICY_SHA256
            or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("processor_revision", "")))):
        raise ValueError("unsupported or altered STT policy")
    archive = manifest.get("archive")
    if (not isinstance(archive, dict) or archive.get("url") != "https://openslr.org/40/"
            or archive.get("license") != "CC-BY-4.0"
            or archive.get("sha256") != ARCHIVE_SHA256
            or archive.get("size_bytes") != 10_339_720_618):
        raise ValueError("invalid Zeroth-Korean source identity")
    bundle_name = manifest.get("bundle")
    stats = manifest.get("stats")
    transcript_hashes = manifest.get("evaluation_transcript_sha256")
    required_hashes = ("bundle_sha256", "asr_binding_sha256", "alignment_binding_sha256")
    if (not isinstance(bundle_name, str) or Path(bundle_name).name != bundle_name
            or not isinstance(stats, dict)
            or any(not isinstance(stats.get(key), int) or isinstance(stats.get(key), bool)
                   or stats[key] <= 0 for key in
                   ("accepted_rows", "accepted_duration_ms", "accepted_audio_bytes"))
            or not isinstance(transcript_hashes, list)
            or not transcript_hashes
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in transcript_hashes)
            or len(set(transcript_hashes)) != len(transcript_hashes)
            or any(not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get(key, "")))
                   for key in required_hashes)
            or not isinstance(manifest.get("decoder"), str) or not manifest["decoder"].strip()):
        raise ValueError("invalid STT manifest bindings or totals")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("STT model bindings are missing")
    expected_models = {
        "asr": ("openai/whisper-large-v3-turbo", "41f01f3fe87f28c78e2fbf8b568835947dd65ed9"),
        "alignment": ("montreal-forced-aligner/korean_mfa-3.0.0", "f76a59f7491eadda0fee212b329521e20e349e75"),
    }
    for name, (model_id, revision) in expected_models.items():
        binding = bindings.get(name)
        if (not isinstance(binding, dict) or binding.get("model_id") != model_id
                or binding.get("revision") != revision
                or hashlib.sha256(_canonical(binding).encode()).hexdigest() != manifest[f"{name}_binding_sha256"]):
            raise ValueError("STT model binding mismatch")
    for name, key, expected in (
        ("asr", "weight_sha256", "542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1"),
        ("asr", "config_sha256", "c5b526b3e3cd64cd8940dabb45e8ba726629e22d8ed389c29b552f9140daf04a"),
        ("alignment", "acoustic_sha256", "46f7a73ab46828c679562b160e0577beecfb4a9a827efe5ab392aee947451a4d"),
        ("alignment", "dictionary_sha256", "75683f4dc2a7dd95295a068206d248a30bd2f4f2231fd4449210c91d1e78150b"),
    ):
        if bindings[name].get(key) != expected:
            raise ValueError("STT pinned model hash mismatch")
    manifest_digest, manifest_size = ObjectStore.hash_file(manifest_path)
    bundle = manifest_path.parent / bundle_name
    bundle_digest, bundle_size = ObjectStore.hash_file(bundle)
    if bundle_digest != manifest.get("bundle_sha256"):
        raise ValueError("STT bundle SHA-256 mismatch")
    with registry.connect() as connection:
        registry.assert_exportable(connection, source_id)
        source = connection.execute(
            "SELECT * FROM sources WHERE source_id=?", (source_id,)
        ).fetchone()
        if source is None:
            raise KeyError(source_id)
        split = connection.execute(
            "SELECT split,frozen FROM split_assignments WHERE group_id=? AND policy_version='source-split-v1'",
            (source["derivative_family"],),
        ).fetchone()
        if (source["source_type"] != "stt" or source["character_id"] != "non-target"
                or source["origin"] != archive["url"] or source["language"] != "ko-KR"
                or source["quality_status"] != "passed" or source["review_status"] != "reviewed"
                or source["corpus_class"] != "accepted_corpus"
                or not split or split["split"] != "train" or not split["frozen"]):
            raise PermissionError("STT source requires a frozen train split")
        existing = connection.execute(
            "SELECT count(*) FROM audio_samples WHERE source_id=?", (source_id,)
        ).fetchone()[0]
        binding = connection.execute(
            "SELECT 1 FROM source_objects WHERE source_id=? AND sha256=? AND role='stt:manifest'",
            (source_id, manifest_digest),
        ).fetchone()
        if existing:
            if existing == stats["accepted_rows"] and binding:
                return {"count": existing, "duration_ms": stats["accepted_duration_ms"],
                        "idempotent": True}
            raise RuntimeError("source already has a different STT import")
    rows = list(_records(manifest, bundle, audio_root))
    duration = sum(row["audio_metrics"]["duration_ms"] for row in rows)
    size = sum(row["size_bytes"] for row in rows)
    if (len(rows) != stats["accepted_rows"]
            or duration != stats["accepted_duration_ms"]
            or size != stats["accepted_audio_bytes"]):
        raise ValueError("STT bundle totals differ from its manifest")
    with registry.connect() as connection:
        _assert_manifest_review(connection, source_id, manifest_digest)
    missing_bytes = sum(
        row["size_bytes"] for row in rows if not paths.object_path(row["audio_sha256"]).is_file()
    )
    if not paths.object_path(bundle_digest).is_file():
        missing_bytes += bundle_size
    missing_bytes += manifest_size + max(row["size_bytes"] for row in rows)
    if shutil.disk_usage(paths.root).free - missing_bytes < 50 * 1024**3:
        raise OSError("STT import would cross the 50 GiB canonical reserve")
    if dry_run:
        return {"count": len(rows), "duration_ms": duration, "idempotent": False, "dry_run": True}
    store = ObjectStore(paths, registry)
    for row in rows:
        if store.ingest(row["_path"], source_id, role="audio:raw_flac", media_type="audio/flac") != row["audio_sha256"]:
            raise ValueError("canonical STT object hash differs")
    bundle_sha256 = store.ingest(bundle, source_id, role="stt:bundle", media_type="application/gzip")
    if bundle_sha256 != bundle_digest:
        raise ValueError("STT bundle changed during import")
    if store.ingest(manifest_path, source_id, role="stt:manifest", media_type="application/json") != manifest_digest:
        raise ValueError("STT manifest changed during import")
    evidence = _canonical({
        "actor_type": "evaluator", "batch_size": 1, "media_reviewed_ms": 0,
        "read_complete": False, "policy_sha256": POLICY_SHA256,
        "asr_binding_sha256": manifest["asr_binding_sha256"],
        "alignment_binding_sha256": manifest["alignment_binding_sha256"],
    })
    created_at = registry.now()
    with registry.transaction() as connection:
        registry.assert_exportable(connection, source_id)
        _assert_manifest_review(connection, source_id, manifest_digest)
        audio, metrics, reviews, review_evidence = [], [], [], []
        for row in rows:
            sample_id, digest = row["sample_id"], row["audio_sha256"]
            duration_ms = row["audio_metrics"]["duration_ms"]
            transcript = row["normalized_text"]
            audio.append((
                sample_id, source_id, digest, duration_ms, "ko-KR", transcript, transcript, transcript,
                "speech", 1_000_000, row["alignment"]["coverage_ppm"], 1_000_000, 1_000_000,
                "validated_stt", "accepted", digest, 0, duration_ms, digest,
                registry.segment_fingerprint(digest, 0, duration_ms, transcript),
            ))
            value = row["audio_metrics"]
            metrics.append((
                digest, value["sample_rate_hz"], value["channels"], duration_ms, 2,
                value["peak_ppm"], value["clipping_ppm"], value["dc_offset_ppm"], value["silence_ppm"],
                manifest["decoder"], created_at,
            ))
            review_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"miku-stt-review\0{sample_id}\0{POLICY_SHA256}"))
            reviews.append((review_id, "audio", sample_id, 1, POLICY["id"], None, "accept",
                            "source, decode, ASR, alignment, split and rights gates passed", created_at))
            review_evidence.append((review_id, "evaluator", 0, 0, 1, evidence, created_at))
        for value in metrics:
            existing_metric = connection.execute(
                "SELECT * FROM audio_metrics WHERE object_sha256=?", (value[0],)
            ).fetchone()
            if existing_metric and tuple(existing_metric)[1:10] != value[1:10]:
                raise ValueError("existing STT audio metrics differ")
        connection.executemany("INSERT OR IGNORE INTO audio_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)", metrics)
        connection.executemany(
            """INSERT INTO audio_samples(
                 sample_id,source_id,object_sha256,duration_ms,language,raw_text,spoken_text,
                 normalized_text,modality,quality_ppm,alignment_ppm,review_weight_ppm,
                 source_tier_weight_ppm,quality_tier,training_status,parent_object_sha256,
                 segment_start_ms,segment_end_ms,clip_object_sha256,segment_fingerprint
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", audio,
        )
        connection.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", reviews)
        connection.executemany("INSERT INTO review_evidence VALUES (?,?,?,?,?,?,?)", review_evidence)
        registry.audit(connection, "stt_bundle.training_promoted", actor, "source", source_id,
                       {"bundle_sha256": bundle_sha256, "count": len(rows), "duration_ms": duration,
                        "policy_sha256": POLICY_SHA256})
    return {"bundle_sha256": bundle_sha256, "count": len(rows), "duration_ms": duration,
            "idempotent": False}
