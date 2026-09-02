#!/usr/bin/env python3
"""Generate known mixtures, run pinned Demucs, and report stem SI-SDR."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
import wave
from pathlib import Path

import numpy as np
import soundfile as sf

from benchmark_asr import PHRASES


def read_mono(path: Path, sample_rate: int = 44100) -> np.ndarray:
    data, rate = sf.read(path, dtype="float32", always_2d=True)
    if rate != sample_rate:
        raise ValueError(f"unexpected sample rate for {path}: {rate}")
    return data.mean(axis=1)


def si_sdr(reference: np.ndarray, estimate: np.ndarray) -> float:
    length = min(len(reference), len(estimate))
    reference, estimate = reference[:length], estimate[:length]
    reference = reference - reference.mean()
    estimate = estimate - estimate.mean()
    target = np.dot(estimate, reference) * reference / max(np.dot(reference, reference), 1e-12)
    noise = estimate - target
    return 10 * math.log10(max(np.dot(target, target), 1e-12) / max(np.dot(noise, noise), 1e-12))


def generate(root: Path, count: int) -> list[tuple[Path, Path, Path]]:
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for index in range(count):
        item = root / f"mix-{index:02d}"
        item.mkdir(exist_ok=True)
        raw_voice = item / "voice-raw.wav"
        voice, music = item / "voice.wav", item / "music.wav"
        mixture = item / f"mixture-{index:02d}.wav"
        subprocess.run(["espeak-ng", "-v", "ko", "-s", str(130 + index * 7), "-p", str(35 + index * 4), "-w", str(raw_voice), PHRASES[index % len(PHRASES)]], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw_voice), "-ar", "44100", "-ac", "2", str(voice)], check=True)
        with wave.open(str(voice), "rb") as stream:
            duration = stream.getnframes() / stream.getframerate()
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={180 + index * 31}:duration={duration}:sample_rate=44100", "-filter:a", "volume=0.08", "-ac", "2", str(music)], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(voice), "-i", str(music), "-filter_complex", "amix=inputs=2:duration=shortest:normalize=0", str(mixture)], check=True)
        raw_voice.unlink()
        result.append((mixture, voice, music))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--model", default="htdemucs")
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    items = generate(args.root / "fixtures", args.count)
    output_root = args.root / "outputs"
    started = time.monotonic()
    subprocess.run(["python", "-m", "demucs", "--two-stems", "vocals", "-n", args.model, "-o", str(output_root), *(str(item[0]) for item in items)], check=True)
    processing_seconds = time.monotonic() - started
    rows = []
    duration = 0.0
    for mixture, voice, music in items:
        vocals = output_root / args.model / mixture.stem / "vocals.wav"
        residual = output_root / args.model / mixture.stem / "no_vocals.wav"
        reference_voice, reference_music = read_mono(voice), read_mono(music)
        duration += len(reference_voice) / 44100
        rows.append({"fixture": mixture.stem, "vocal_si_sdr_db": si_sdr(reference_voice, read_mono(vocals)), "instrument_si_sdr_db": si_sdr(reference_music, read_mono(residual))})
    result = {
        "fixture_kind": "generated_espeak_ng_known_mixture",
        "model": args.model,
        "revision": args.revision,
        "count": len(rows),
        "audio_duration_seconds": duration,
        "processing_seconds": processing_seconds,
        "rtf": processing_seconds / duration,
        "vocal_si_sdr_db_mean": float(np.mean([row["vocal_si_sdr_db"] for row in rows])),
        "instrument_si_sdr_db_mean": float(np.mean([row["instrument_si_sdr_db"] for row in rows])),
        "items": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "items"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
