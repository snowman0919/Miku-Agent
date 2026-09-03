#!/usr/bin/env python3
"""Build a deterministic, review-pending render bundle from curated public seeds."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import uuid
from pathlib import Path


TIMES = (
    "오늘", "오늘 아침", "오늘 오후", "조금 전", "방금", "어제", "이번 주에",
    "다음 단계에서", "회의 전에", "작업을 시작하기 전에", "검토를 마친 뒤",
    "잠시 후", "필요한 순간에",
)
FRAMES = {
    "emotion": (
        "마음을 차분히 전하면서,", "상대의 표정을 살피면서,", "조금 밝은 목소리로,",
        "진심을 담아 말하자면,", "잠시 숨을 고른 다음,", "친근하게 말을 건네며,",
        "부드러운 어조로,", "상대의 이야기를 들은 뒤,",
    ),
    "technical": (
        "작업 상태를 확인해 보니,", "기록을 다시 살펴보니,", "결과부터 정리하면,",
        "다음 조치를 안내하자면,", "원인을 하나씩 확인하면서,", "변경 사항을 검토한 뒤,",
        "실행 전에 확인할 내용은,", "현재 확인된 범위에서는,",
    ),
    "precision": (
        "내용을 정확히 전달하려고,", "표기를 다시 확인한 다음,", "읽는 방법까지 고려하면,",
        "숫자와 이름을 구분해서,", "헷갈리지 않게 말하자면,", "한 글자씩 확인하면서,",
        "발음을 분명히 하려고,", "기록과 대조해 보니,",
    ),
    "general": (
        "상황을 간단히 정리하면,", "한 가지 더 말씀드리면,", "대화를 이어 가면서,",
        "지금 생각나는 건,", "조금 다르게 표현하면,", "상대에게 확인하듯,",
        "자연스럽게 말을 꺼내며,", "앞선 내용을 돌아보면,",
    ),
}
TECHNICAL = {"기술 설명", "도구 작업 안내", "실패 보고", "코드와 파일 경로"}
PRECISION = {"숫자와 단위", "날짜와 시간", "영어 약어", "제품명", "한영 code switch", "고유명사"}
EMOTION = {"감탄", "격려", "위로", "짧은 맞장구"}
ABBREVIATIONS = {
    "A/B": "에이 비", "API": "에이피아이", "CI": "씨아이", "CV": "씨브이",
    "HR": "에이치알", "IT": "아이티", "NASA": "나사", "OTA": "오티에이",
    "PM": "피엠", "SNS": "에스엔에스", "SSL": "에스에스엘", "TCP": "티씨피",
    "URL": "유알엘", "JSON": "제이슨",
}


def spoken(text: str) -> str:
    for raw, reading in ABBREVIATIONS.items():
        text = re.sub(rf"(?<![A-Za-z]){re.escape(raw)}(?![A-Za-z])", reading, text)
    return re.sub(r"\s+", " ", text.replace("/", " 슬래시 ")).strip()


def coverage(text: str) -> dict[str, list[str]]:
    decomposed = unicodedata.normalize("NFD", text)
    return {
        "initials": sorted({char for char in decomposed if "\u1100" <= char <= "\u115f"}),
        "vowels": sorted({char for char in decomposed if "\u1160" <= char <= "\u11a7"}),
        "finals": sorted({char for char in decomposed if "\u11a8" <= char <= "\u11ff"}),
    }


def build(seeds_path: Path, output: Path, count: int) -> dict[str, object]:
    seed_document = json.loads(seeds_path.read_text(encoding="utf-8"))
    window = json.loads((seeds_path.parent / "accepted-window.json").read_text(encoding="utf-8"))
    generation_models = {
        item["job_id"]: item["model"] for item in window["accepted_jobs"]
        if item["provider"] == "command_code"
    }
    critic_models = sorted({
        item["model"] for item in window["accepted_jobs"]
        if item["provider"] == "opencode"
    })
    seeds = [item for item in seed_document["seeds"] if item["review_status"] == "candidate"]
    if not seeds:
        raise ValueError("no candidate seeds")
    contexts = [(time, frame) for time in TIMES for frame in range(8)]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    digest = hashlib.sha256()
    exact: set[str] = set()
    template_counts: dict[str, int] = {}
    duration_ms = 0
    with temporary.open("wb") as stream:
        for index in range(count):
            seed = seeds[index % len(seeds)]
            cycle = index // len(seeds)
            time_phrase, frame_index = contexts[cycle % len(contexts)]
            category = seed["category"]
            group = "emotion" if category in EMOTION else "technical" if category in TECHNICAL else "precision" if category in PRECISION else "general"
            raw_text = f"{time_phrase} {FRAMES[group][frame_index]} {seed['raw_text']}"
            spoken_text = spoken(raw_text)
            normalized = unicodedata.normalize("NFC", re.sub(r"\s+", " ", spoken_text)).strip()
            utterance_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"miku-render-v0.2\0{normalized}"))
            rate = ("slow", "normal", "bright", "deliberate")[index % 4]
            estimated = max(1500, round(len(re.sub(r"\s", "", spoken_text)) * 235 * {"slow": 1.12, "normal": 1.0, "bright": .9, "deliberate": 1.08}[rate]))
            record = {
                "utterance_id": utterance_id, "raw_text": raw_text,
                "spoken_text": spoken_text, "normalized_text": normalized,
                "grapheme_coverage": coverage(spoken_text),
                "coverage_targets": seed["coverage_targets"], "scenario": seed["scenario"],
                "emotion": "supportive" if category in EMOTION else "neutral",
                "speaking_rate": rate, "target_duration_ms_estimate": estimated,
                "template_family": seed["seed_id"], "generation_job_id": seed["generation_job_id"],
                "generation_model": generation_models[seed["generation_job_id"]],
                "critic_window_id": "window-001", "critic_models": critic_models,
                "human_review": "pending",
                "training_status": "quarantine", "expected_filename": f"{utterance_id}.wav",
                "expected_sample_rate_hz": 48000,
            }
            line = (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
            stream.write(line); digest.update(line); exact.add(normalized); duration_ms += estimated
            template_counts[seed["seed_id"]] = template_counts.get(seed["seed_id"], 0) + 1
    temporary.replace(output)
    manifest = {
        "bundle_id": "miku-speech-render-d0.2.0-alpha1", "row_count": count,
        "exact_unique_rows": len(exact), "template_family_count": len(template_counts),
        "largest_template_family_rows": max(template_counts.values()),
        "estimated_render_hours": duration_ms / 3_600_000,
        "actual_render_hours": 0, "human_reviewed_rows": 0,
        "training_accepted_rows": 0, "jsonl_sha256": digest.hexdigest(),
        "expected_sample_rate_hz": 48000,
        "warning": "Duration is an estimate; rendered audio duration and human review are authoritative.",
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=20_000)
    args = parser.parse_args()
    if args.count < 1:
        raise SystemExit("--count must be positive")
    print(json.dumps(build(args.seeds, args.output, args.count), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
