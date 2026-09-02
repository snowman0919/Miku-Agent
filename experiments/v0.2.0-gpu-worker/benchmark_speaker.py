#!/usr/bin/env python3
"""Benchmark pinned SpeechBrain speaker embedding candidates."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import librosa
import torch
import torch.nn.functional as functional
import torchaudio

from benchmark_asr import fixtures

if not hasattr(torchaudio, "list_audio_backends"):
    torchaudio.list_audio_backends = lambda: []

from speechbrain.inference.speaker import EncoderClassifier  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    items = fixtures(args.fixture_root, args.count)
    loaded = time.monotonic()
    model = EncoderClassifier.from_hparams(source=str(args.model_path), savedir=None, run_opts={"device": "cuda"})
    load_seconds = time.monotonic() - loaded
    audio = []
    duration = 0.0
    for path, _ in items:
        samples, _ = librosa.load(path, sr=16000, mono=True)
        tensor = torch.tensor(samples)
        audio.append(tensor)
        duration += len(samples) / 16000
    embeddings = []
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    for start in range(0, len(audio), args.batch_size):
        batch = audio[start:start + args.batch_size]
        maximum = max(len(item) for item in batch)
        padded = torch.stack([functional.pad(item, (0, maximum - len(item))) for item in batch]).to("cuda")
        lengths = torch.tensor([len(item) / maximum for item in batch], device="cuda")
        with torch.inference_mode():
            value = model.encode_batch(padded, lengths).squeeze(1)
        embeddings.append(functional.normalize(value, dim=-1).cpu())
    processing_seconds = time.monotonic() - started
    matrix = torch.cat(embeddings)
    centroid = functional.normalize(matrix.mean(0), dim=0)
    similarities = matrix @ matrix.T
    mask = ~torch.eye(len(matrix), dtype=torch.bool)
    centroid_similarity = matrix @ centroid
    result = {
        "fixture_kind": "generated_espeak_ng_single_voice_variations",
        "model_id": args.model_id,
        "revision": args.revision,
        "count": len(items),
        "embedding_dimension": matrix.shape[1],
        "normalization": "l2",
        "audio_duration_seconds": duration,
        "model_load_seconds": load_seconds,
        "processing_seconds": processing_seconds,
        "rtf": processing_seconds / duration,
        "torch_peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024 / 1024,
        "pairwise_similarity_mean": similarities[mask].mean().item(),
        "pairwise_similarity_min": similarities[mask].min().item(),
        "centroid_similarity_mean": centroid_similarity.mean().item(),
        "centroid_similarity_min": centroid_similarity.min().item(),
        "calibration_status": "NOT CALIBRATED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
