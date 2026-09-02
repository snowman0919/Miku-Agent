#!/usr/bin/env python3
"""Benchmark pinned MMS Korean CTC forced alignment on known transcripts."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import librosa
import torch
import torchaudio
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

from benchmark_asr import fixtures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    items = fixtures(args.fixture_root, args.count)
    loaded = time.monotonic()
    processor = Wav2Vec2Processor.from_pretrained(args.model_path, local_files_only=True)
    model = Wav2Vec2ForCTC.from_pretrained(args.model_path, dtype=torch.float16, local_files_only=True)
    processor.tokenizer.set_target_lang("kor")
    model.load_adapter("kor", adapter_kwargs={"cache_dir": str(args.model_path), "local_files_only": True})
    model = model.to("cuda").eval()
    load_seconds = time.monotonic() - loaded
    started = time.monotonic()
    results = []
    failures = 0
    duration_total = 0.0
    torch.cuda.reset_peak_memory_stats()
    for path, transcript in items:
        samples, _ = librosa.load(path, sr=16000, mono=True)
        duration = len(samples) / 16000
        duration_total += duration
        ids = processor.tokenizer(transcript, add_special_tokens=False).input_ids
        values = processor(samples, sampling_rate=16000, return_tensors="pt")
        try:
            with torch.inference_mode():
                emission = model(values.input_values.to("cuda", dtype=torch.float16)).logits.log_softmax(-1)
                aligned, scores = torchaudio.functional.forced_align(
                    emission, torch.tensor([ids], device="cuda"), blank=processor.tokenizer.pad_token_id,
                )
            spans = torchaudio.functional.merge_tokens(aligned[0].cpu(), scores[0].cpu(), blank=processor.tokenizer.pad_token_id)
            tokens = processor.tokenizer.convert_ids_to_tokens(ids)
            frame_seconds = duration / emission.shape[1]
            token_intervals = [
                {"token": tokens[index], "start_seconds": span.start * frame_seconds, "end_seconds": span.end * frame_seconds, "confidence": math.exp(span.score)}
                for index, span in enumerate(spans)
            ]
            words = []
            current = []
            for interval in token_intervals + [{"token": "|"}]:
                if interval["token"] == "|":
                    if current:
                        words.append({"word": "".join(part["token"] for part in current), "start_seconds": current[0]["start_seconds"], "end_seconds": current[-1]["end_seconds"], "confidence": sum(part["confidence"] for part in current) / len(current)})
                        current = []
                else:
                    current.append(interval)
            results.append({"path": path.name, "transcript": transcript, "word_intervals": words, "token_intervals": token_intervals, "unaligned_spans": [], "duration_anomaly": bool(words and words[-1]["end_seconds"] > duration + frame_seconds)})
        except RuntimeError as exc:
            failures += 1
            results.append({"path": path.name, "transcript": transcript, "word_intervals": [], "token_intervals": [], "unaligned_spans": [transcript], "duration_anomaly": False, "error": str(exc)})
    processing_seconds = time.monotonic() - started
    summary = {
        "fixture_kind": "generated_espeak_ng_korean", "backend": "mms-1b-all-ctc",
        "revision": args.revision, "count": len(items), "failed": failures,
        "failure_rate": failures / len(items), "audio_duration_seconds": duration_total,
        "model_load_seconds": load_seconds, "processing_seconds": processing_seconds,
        "rtf": processing_seconds / duration_total,
        "torch_peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024 / 1024,
        "phoneme_timing": False, "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
