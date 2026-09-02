#!/usr/bin/env python3
"""Benchmark pinned ASR candidates on generated, permitted Korean speech."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import librosa
import torch
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
    Wav2Vec2ForCTC,
    Wav2Vec2Processor,
)

PHRASES = (
    "안녕하세요. 오늘도 함께 즐겁게 작업해 봐요.",
    "파일의 해시를 확인한 다음 결과를 저장해 주세요.",
    "실패한 작업은 원인을 기록하고 다시 검증합니다.",
    "한국어 음성 인식 품질을 정확하게 비교합니다.",
    "지금은 짧은 문장입니다.",
    "권리 상태와 기술 품질은 서로 다른 판단이므로 작업자가 임의로 승인하면 안 됩니다.",
    "메모리를 검색하고 도구 실행 결과를 확인해 주세요.",
    "네트워크 오류가 발생하면 제한된 횟수만 다시 시도합니다.",
    "모델 버전과 가중치 해시는 재현성에 꼭 필요합니다.",
    "좋은 아침이에요. 오늘 계획을 차근차근 시작합시다.",
)


def normalize(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, a in enumerate(left, 1):
        current = [row]
        for column, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (a != b)))
        previous = current
    return previous[-1]


def fixtures(root: Path, count: int) -> list[tuple[Path, str]]:
    root.mkdir(parents=True, exist_ok=True)
    result = []
    speeds = (125, 145, 165, 185, 205)
    for index in range(count):
        text = PHRASES[index % len(PHRASES)]
        path = root / f"ko-{index:03d}.wav"
        subprocess.run(
            ["espeak-ng", "-v", "ko", "-s", str(speeds[index % len(speeds)]), "-p", str(35 + index % 4 * 8), "-w", str(path), text],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        result.append((path, text))
    return result


def load_audio(items: list[tuple[Path, str]]) -> tuple[list[object], float]:
    audio = []
    duration = 0.0
    for path, _ in items:
        samples, _ = librosa.load(path, sr=16000, mono=True)
        audio.append(samples)
        duration += len(samples) / 16000
    return audio, duration


def whisper(model_path: Path, audio: list[object], batch_size: int) -> tuple[list[str], float, float]:
    loaded = time.monotonic()
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(model_path, dtype=torch.float16, local_files_only=True).to("cuda").eval()
    load_seconds = time.monotonic() - loaded
    started = time.monotonic()
    hypotheses = []
    for start in range(0, len(audio), batch_size):
        values = processor(audio[start:start + batch_size], sampling_rate=16000, return_tensors="pt", padding=True, return_attention_mask=True)
        kwargs = {"attention_mask": values.attention_mask.to("cuda")} if "attention_mask" in values else {}
        with torch.inference_mode():
            ids = model.generate(values.input_features.to("cuda", dtype=torch.float16), language="ko", task="transcribe", **kwargs)
        hypotheses.extend(processor.batch_decode(ids, skip_special_tokens=True))
    return hypotheses, load_seconds, time.monotonic() - started


def mms(model_path: Path, audio: list[object], batch_size: int) -> tuple[list[str], float, float]:
    loaded = time.monotonic()
    processor = Wav2Vec2Processor.from_pretrained(model_path, local_files_only=True)
    model = Wav2Vec2ForCTC.from_pretrained(model_path, dtype=torch.float16, local_files_only=True)
    processor.tokenizer.set_target_lang("kor")
    model.load_adapter("kor", adapter_kwargs={"cache_dir": str(model_path), "local_files_only": True})
    model = model.to("cuda").eval()
    load_seconds = time.monotonic() - loaded
    started = time.monotonic()
    hypotheses = []
    for start in range(0, len(audio), batch_size):
        values = processor(audio[start:start + batch_size], sampling_rate=16000, return_tensors="pt", padding=True)
        with torch.inference_mode():
            logits = model(values.input_values.to("cuda", dtype=torch.float16), attention_mask=values.attention_mask.to("cuda")).logits
        hypotheses.extend(processor.batch_decode(torch.argmax(logits, dim=-1)))
    return hypotheses, load_seconds, time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=("whisper", "mms"), required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=5)
    args = parser.parse_args()
    items = fixtures(args.fixture_root, args.count)
    audio, duration = load_audio(items)
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
    hypotheses, load_seconds, processing_seconds = (whisper if args.family == "whisper" else mms)(args.model_path, audio, args.batch_size)
    references = [text for _, text in items]
    errors = sum(edit_distance(normalize(reference), normalize(hypothesis)) for reference, hypothesis in zip(references, hypotheses))
    characters = sum(len(normalize(reference)) for reference in references)
    result = {
        "fixture_kind": "generated_espeak_ng_korean",
        "family": args.family,
        "revision": args.revision,
        "count": len(items),
        "audio_duration_seconds": duration,
        "model_load_seconds": load_seconds,
        "processing_seconds": processing_seconds,
        "processed_audio_seconds_per_wall_second": duration / processing_seconds,
        "rtf": processing_seconds / duration,
        "character_error_rate": errors / characters,
        "torch_peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024 / 1024,
        "hypotheses": [{"reference": reference, "hypothesis": hypothesis} for reference, hypothesis in zip(references, hypotheses)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "hypotheses"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
