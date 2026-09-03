#!/usr/bin/env python3
"""Prepare the official OpenSLR SLR40 train corpus for canonical STT import."""

from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import json
import math
import os
import re
import subprocess
import tarfile
import time
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath


ARCHIVE_SIZE = 10_339_720_618
ARCHIVE_PAGE = "https://openslr.org/40/"
ASR_BINDING = {
    "model_id": "openai/whisper-large-v3-turbo",
    "revision": "41f01f3fe87f28c78e2fbf8b568835947dd65ed9",
    "weight_sha256": "542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1",
    "config_sha256": "c5b526b3e3cd64cd8940dabb45e8ba726629e22d8ed389c29b552f9140daf04a",
    "dtype": "float16",
    "language": "ko",
    "task": "transcribe",
}
ALIGNMENT_BINDING = {
    "model_id": "montreal-forced-aligner/korean_mfa-3.0.0",
    "revision": "f76a59f7491eadda0fee212b329521e20e349e75",
    "acoustic_sha256": "46f7a73ab46828c679562b160e0577beecfb4a9a827efe5ab392aee947451a4d",
    "dictionary_sha256": "75683f4dc2a7dd95295a068206d248a30bd2f4f2231fd4449210c91d1e78150b",
    "beam": 100,
    "retry_beam": 400,
}
POLICY = {
    "id": "openslr-zeroth-korean-stt-v1",
    "audio": "original lossless FLAC bytes; full worker decode required",
    "format": {"bits_per_sample": 16, "channels": 1, "sample_rate_hz": 16000},
    "transcript": "Unicode NFC and collapsed whitespace",
    "split": "official speaker-disjoint train/test; exclude normalized test transcripts from train",
    "asr": "pinned independent baseline required; CER measured but not used as an automatic threshold",
    "alignment": "pinned Korean MFA word and phone timing required with bounded intervals",
}
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def asr_text(value: str) -> str:
    return "".join(TOKEN_RE.findall(normalize(value).casefold()))


def cer_ppm(reference: str, hypothesis: str) -> int:
    left, right = asr_text(reference), asr_text(hypothesis)
    if not left:
        raise ValueError("empty normalized transcript")
    previous = list(range(len(right) + 1))
    for index, char in enumerate(left, 1):
        current = [index]
        for offset, other in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[offset] + 1,
                               previous[offset - 1] + (char != other)))
        previous = current
    return previous[-1] * 1_000_000 // len(left)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def validate_and_extract(archive: Path, extracted: Path, expected_sha256: str) -> None:
    if archive.stat().st_size != ARCHIVE_SIZE or sha256(archive) != expected_sha256:
        raise ValueError("archive size or SHA-256 mismatch")
    marker = extracted / ".archive-sha256"
    if marker.is_file():
        if marker.read_text(encoding="ascii").strip() != expected_sha256:
            raise ValueError("extraction belongs to another archive")
        return
    extracted.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as stream:
        members = stream.getmembers()
        selected = []
        for member in members:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or ".." in relative.parts or not relative.parts
                    or not (member.isfile() or member.isdir())):
                raise ValueError(f"unsafe archive member: {member.name}")
            if relative.parts[0] in {"AUDIO_INFO", "train_data_01", "test_data_01"}:
                selected.append(member)
        stream.extractall(extracted, members=selected, filter="data")
    marker.write_text(expected_sha256 + "\n", encoding="ascii")


def transcripts(root: Path, split: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.joinpath(split).rglob("*.trans.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            utterance, separator, text = line.partition(" ")
            text = normalize(text)
            if not separator or not text or utterance in result:
                raise ValueError(f"invalid duplicate transcript: {utterance}")
            result[utterance] = text
    return result


def analyze_one(root: Path, path: Path, text: str) -> dict[str, object]:
    import numpy as np
    import soundfile as sf

    info = sf.info(path)
    samples, rate = sf.read(path, dtype="float32", always_2d=True)
    if (info.format != "FLAC" or info.subtype != "PCM_16" or rate != 16000
            or samples.shape[1] != 1 or len(samples) != info.frames):
        raise ValueError(f"unsupported or inconsistent FLAC: {path}")
    values = np.abs(samples[:, 0])
    relative = path.relative_to(root).as_posix()
    return {
        "utterance_id": path.stem,
        "speaker_id": path.relative_to(root).parts[2],
        "path": relative,
        "audio_sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "raw_text": text,
        "audio_metrics": {
            "sample_rate_hz": rate,
            "channels": 1,
            "bits_per_sample": 16,
            "total_samples": len(samples),
            "duration_ms": len(samples) * 1000 // rate,
            "peak_ppm": round(float(values.max(initial=0)) * 1_000_000),
            "clipping_ppm": round(float(np.mean(values >= 0.999)) * 1_000_000),
            "dc_offset_ppm": round(abs(float(np.mean(samples[:, 0]))) * 1_000_000),
            "silence_ppm": round(float(np.mean(values <= 0.001)) * 1_000_000),
            "decode_status": "passed",
        },
    }


def analyze(extracted: Path, work: Path, jobs: int) -> list[dict[str, object]]:
    output = work / "inventory.jsonl"
    if output.is_file():
        return read_jsonl(output)
    train = transcripts(extracted, "train_data_01")
    audio = sorted(extracted.joinpath("train_data_01").rglob("*.flac"))
    train_speakers = {path.relative_to(extracted).parts[2] for path in audio}
    test_speakers = {path.relative_to(extracted).parts[2]
                     for path in extracted.joinpath("test_data_01").rglob("*.flac")}
    if not train_speakers or not test_speakers or train_speakers & test_speakers:
        raise ValueError("official train/test speakers overlap or are missing")
    if set(path.stem for path in audio) != set(train):
        raise ValueError("train audio and transcript identities differ")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(lambda path: analyze_one(extracted, path, train[path.stem]), audio))
    output.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    return rows


def make_mfa_corpus(extracted: Path, work: Path, rows: list[dict[str, object]]) -> Path:
    corpus = work / "mfa-corpus"
    corpus.mkdir(exist_ok=True)
    for row in rows:
        directory = corpus / str(row["speaker_id"])
        directory.mkdir(exist_ok=True)
        audio = directory / f'{row["utterance_id"]}.flac'
        if not audio.exists():
            os.link(extracted / str(row["path"]), audio)
        lab = audio.with_suffix(".lab")
        if not lab.exists():
            lab.write_text(str(row["raw_text"]) + "\n", encoding="utf-8")
    return corpus


def align(extracted: Path, work: Path, rows: list[dict[str, object]], mfa_root: Path, jobs: int) -> Path:
    output = work / "mfa-output"
    if len(list(output.rglob("*.json"))) == len(rows):
        return output
    corpus = make_mfa_corpus(extracted, work, rows)
    executable = mfa_root / "environments/mfa-3.4.2/bin/mfa"
    model = mfa_root / "models/mfa-korean-3.0.0"
    environment = os.environ.copy()
    environment["MFA_ROOT_DIR"] = str(mfa_root / "cache/mfa")
    environment["PATH"] = str(executable.parent) + os.pathsep + environment.get("PATH", "")
    subprocess.run([
        str(executable), "align", str(corpus),
        str(model / "korean_mfa_dictionary_v3.0.0.dict"),
        str(model / "korean_mfa_acoustic_v3.0.0.zip"), str(output),
        "--output_format", "json", "--beam", "100", "--retry_beam", "400",
        "--temporary_directory", str(work / "mfa-tmp"), "--num_jobs", str(jobs),
        "--use_mp", "--no_use_postgres", "--clean", "--final_clean", "--quiet", "--overwrite",
    ], check=True, env=environment)
    return output


def transcribe(extracted: Path, work: Path, rows: list[dict[str, object]],
               model_path: Path, batch_size: int, gpu_lock: Path) -> dict[str, str]:
    output = work / "asr.jsonl"
    completed = {str(row["utterance_id"]): str(row["hypothesis"]) for row in read_jsonl(output)}
    pending = [row for row in rows if str(row["utterance_id"]) not in completed]
    if not pending:
        return completed
    import soundfile as sf
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    gpu_lock.parent.mkdir(parents=True, exist_ok=True)
    with gpu_lock.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_path, dtype=torch.float16, local_files_only=True
        ).to("cuda").eval()
        with output.open("a", encoding="utf-8") as stream:
            offset = 0
            while offset < len(pending):
                batch = pending[offset:offset + batch_size]
                audio = [sf.read(extracted / str(row["path"]), dtype="float32")[0] for row in batch]
                try:
                    values = processor(audio, sampling_rate=16000, return_tensors="pt", padding=True,
                                       return_attention_mask=True)
                    kwargs = ({"attention_mask": values.attention_mask.to("cuda")}
                              if "attention_mask" in values else {})
                    with torch.inference_mode():
                        ids = model.generate(values.input_features.to("cuda", dtype=torch.float16),
                                             language="ko", task="transcribe", **kwargs)
                    hypotheses = processor.batch_decode(ids, skip_special_tokens=True)
                except torch.OutOfMemoryError:
                    if batch_size == 1:
                        raise
                    batch_size = max(1, batch_size // 2)
                    torch.cuda.empty_cache()
                    continue
                for row, hypothesis in zip(batch, hypotheses, strict=True):
                    utterance = str(row["utterance_id"])
                    completed[utterance] = hypothesis
                    stream.write(canonical({"utterance_id": utterance, "hypothesis": hypothesis}) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                offset += len(batch)
    return completed


def alignment_summary(path: Path, duration_ms: int) -> dict[str, object] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    words = value.get("tiers", {}).get("words", {}).get("entries", [])
    phones = value.get("tiers", {}).get("phones", {}).get("entries", [])
    if not words or not phones:
        return None
    anomalies = 0
    for entries in (words, phones):
        previous = 0.0
        for start, end, label in entries:
            if (not isinstance(label, str) or not label or start < previous - 1e-6
                    or not math.isfinite(start) or not math.isfinite(end)
                    or end <= start or end * 1000 > duration_ms + 1):
                anomalies += 1
            previous = end
    coverage = sum(max(0.0, end - start) for start, end, _ in phones)
    return {
        "status": "passed" if anomalies == 0 else "failed",
        "word_intervals": len(words), "phone_intervals": len(phones),
        "spn_intervals": sum(label == "spn" for _, _, label in phones),
        "boundary_anomalies": anomalies,
        "coverage_ppm": min(1_000_000, round(coverage * 1_000_000_000 / duration_ms)),
        "tiers": {"words": words, "phones": phones},
    }


def finalize(extracted: Path, work: Path, rows: list[dict[str, object]], hypotheses: dict[str, str],
             alignments: Path, archive: Path, archive_sha256: str, processor_revision: str) -> dict[str, object]:
    test_hashes = sorted({hashlib.sha256(text.encode()).hexdigest()
                          for text in transcripts(extracted, "test_data_01").values()})
    test_set = set(test_hashes)
    seen_audio: set[str] = set()
    accepted = []
    exclusions: dict[str, int] = {}
    for row in rows:
        utterance = str(row["utterance_id"])
        transcript = normalize(str(row["raw_text"]))
        reason = None
        alignment = alignment_summary(
            alignments / str(row["speaker_id"]) / f"{utterance}.json",
            int(row["audio_metrics"]["duration_ms"]),
        )
        if hashlib.sha256(transcript.encode()).hexdigest() in test_set:
            reason = "evaluation_transcript_overlap"
        elif str(row["audio_sha256"]) in seen_audio:
            reason = "duplicate_audio"
        elif utterance not in hypotheses:
            reason = "missing_asr"
        elif not alignment or alignment["status"] != "passed" or not alignment["coverage_ppm"]:
            reason = "failed_alignment"
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue
        seen_audio.add(str(row["audio_sha256"]))
        accepted.append(row | {
            "sample_id": str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"openslr:40\0{archive_sha256}\0{utterance}\0{row['audio_sha256']}",
            )),
            "spoken_text": transcript, "normalized_text": transcript,
            "asr": {"status": "passed", "hypothesis": hypotheses[utterance],
                    "cer_ppm": cer_ppm(transcript, hypotheses[utterance])},
            "alignment": alignment,
        })
    bundle = work / "zeroth-korean-train.jsonl.gz"
    with bundle.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
        for row in accepted:
            stream.write((canonical(row) + "\n").encode())
    manifest = {
        "format": "miku-zeroth-korean-stt-bundle-v1", "policy": POLICY,
        "policy_sha256": hashlib.sha256(canonical(POLICY).encode()).hexdigest(),
        "processor_revision": processor_revision,
        "archive": {"url": ARCHIVE_PAGE, "license": "CC-BY-4.0",
                    "sha256": archive_sha256, "size_bytes": archive.stat().st_size},
        "bundle": bundle.name, "bundle_sha256": sha256(bundle),
        "evaluation_transcript_sha256": test_hashes,
        "asr_binding_sha256": hashlib.sha256(canonical(ASR_BINDING).encode()).hexdigest(),
        "alignment_binding_sha256": hashlib.sha256(canonical(ALIGNMENT_BINDING).encode()).hexdigest(),
        "decoder": "soundfile-0.14.0/libsndfile-full-decode",
        "bindings": {"asr": ASR_BINDING, "alignment": ALIGNMENT_BINDING},
        "stats": {
            "source_rows": len(rows), "accepted_rows": len(accepted),
            "accepted_duration_ms": sum(int(row["audio_metrics"]["duration_ms"]) for row in accepted),
            "accepted_audio_bytes": sum(int(row["size_bytes"]) for row in accepted),
            "official_test_transcripts": len(test_hashes), "exclusions": exclusions,
        },
    }
    manifest_path = work / "zeroth-korean-train.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    return manifest | {"manifest_path": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--processor-revision", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--worker-root", type=Path, required=True)
    parser.add_argument("--gpu-lock", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if (not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha256)
            or not re.fullmatch(r"[0-9a-f]{40}", args.processor_revision)
            or not 1 <= args.jobs <= 64 or not 1 <= args.batch_size <= 64):
        raise ValueError("invalid immutable binding or concurrency")
    started = time.monotonic()
    args.work.mkdir(parents=True, exist_ok=True)
    mfa_model = args.worker_root / "models/mfa-korean-3.0.0"
    for path, expected in (
        (args.model_path / "model.safetensors", ASR_BINDING["weight_sha256"]),
        (args.model_path / "config.json", ASR_BINDING["config_sha256"]),
        (mfa_model / "korean_mfa_acoustic_v3.0.0.zip", ALIGNMENT_BINDING["acoustic_sha256"]),
        (mfa_model / "korean_mfa_dictionary_v3.0.0.dict", ALIGNMENT_BINDING["dictionary_sha256"]),
    ):
        if sha256(path) != expected:
            raise ValueError(f"pinned model hash mismatch: {path.name}")
    extracted = args.work / "extracted"
    validate_and_extract(args.archive, extracted, args.expected_sha256)
    rows = analyze(extracted, args.work, args.jobs)
    alignments = align(extracted, args.work, rows, args.worker_root, args.jobs)
    hypotheses = transcribe(extracted, args.work, rows, args.model_path, args.batch_size, args.gpu_lock)
    result = finalize(extracted, args.work, rows, hypotheses, alignments, args.archive,
                      args.expected_sha256, args.processor_revision)
    result["elapsed_seconds"] = time.monotonic() - started
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
