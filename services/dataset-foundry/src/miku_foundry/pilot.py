from __future__ import annotations

import json
import math
import struct
import uuid
import wave
from pathlib import Path

from .config import FoundryPaths
from .ingest import register_source
from .registry import Registry
from .rights import register_rights
from .split import assign_group
from .store import ObjectStore
from .workers.audio_probe import probe_pcm_wave


NAMESPACE = uuid.UUID("694acf62-941d-4f85-9af4-d3abcda2e921")
DIMENSIONS = ("purity", "liveliness", "warmth", "optimism", "curiosity", "creativity",
              "playfulness", "supportiveness", "independence", "digital_identity", "friendship", "helpfulness")


def stable_id(kind: str, index: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{index}"))


def _tone(path: Path, frequency: float, seconds: float = 1.0, sample_rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = bytearray()
        for index in range(int(seconds * sample_rate)):
            envelope = min(1.0, index / 400, (seconds * sample_rate - index) / 400)
            value = int(2500 * envelope * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", value))
        output.writeframes(frames)


def _ensure_source(registry: Registry, kind: str, index: int, *, source_type: str,
                   title: str, family: str) -> str:
    source_id = stable_id(kind, index)
    with registry.connect() as connection:
        if connection.execute("SELECT 1 FROM sources WHERE source_id=?", (source_id,)).fetchone():
            return source_id
    register_source(registry, source_id=source_id, source_type=source_type, title=title,
                    origin="locally-generated-foundry-pilot", creator="Miku-Agent Dataset Foundry",
                    acquisition_method="deterministic local generation", language="ko-KR", character_id="miku",
                    derivative_family=family, notes="Synthetic infrastructure pilot; not target-voice evidence")
    register_rights(registry, source_id, "owned", "generation-record",
                    "local deterministic generator in repository", "private research and pipeline validation",
                    reviewer="dataset-operator", actor_type="user-delegated")
    assign_group(registry, family)
    return source_id


def build(paths: FoundryPaths, registry: Registry) -> dict[str, int]:
    store = ObjectStore(paths, registry)
    intake = paths.root / "intake" / "pilot"
    intake.mkdir(parents=True, exist_ok=True, mode=0o700)
    for source_index in range(10):
        family = f"pilot-audio-family-{source_index:02d}"
        source_id = _ensure_source(registry, "audio-source", source_index, source_type="speech",
                                   title=f"Synthetic audio pipeline probe {source_index:02d}", family=family)
        audio_path = intake / f"probe-{source_index:02d}.wav"
        if not audio_path.exists():
            _tone(audio_path, 180 + source_index * 23)
        digest = store.ingest(audio_path, source_id, media_type="audio/wav")
        probe_pcm_wave(registry, digest, paths.object_path(digest))
        with registry.transaction() as connection:
            for segment_index in range(10):
                sample_id = stable_id(f"audio-sample-{source_index}", segment_index)
                connection.execute(
                    "INSERT OR IGNORE INTO audio_samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (sample_id, source_id, digest, 1000, "ko-KR", "", "", "", "speech",
                     500000, 0, 0, 500000, "quarantine", "quarantine"),
                )

    text_source = _ensure_source(registry, "text-source", 0, source_type="text",
                                 title="Korean speech-like script pilot", family="pilot-script-template-v1")
    endings = ("확인했어.", "같이 살펴보자.", "천천히 설명해 줄게.", "지금 시작할까?", "실패 원인을 찾았어.", "다음 단계로 넘어가자.")
    domains = ("기술", "일상", "질문", "확인", "위로", "도구")
    with registry.transaction() as connection:
        for index in range(256):
            raw = f"RTX {3000 + index} 장치의 온도는 {20 + index % 60}도야. {endings[index % len(endings)]}"
            spoken = f"알티엑스 {3000 + index} 장치의 온도는 {20 + index % 60}도야. {endings[index % len(endings)]}"
            connection.execute("INSERT OR IGNORE INTO text_samples VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (stable_id("text", index), text_source, "01_language_text", raw, spoken, spoken,
                                "ko-KR", json.dumps(["number", "unit", domains[index % len(domains)]], ensure_ascii=False),
                                json.dumps({"generator": "deterministic-template-v1", "index": index}, sort_keys=True),
                                "quarantine"))

    persona_source = _ensure_source(registry, "persona-source", 0, source_type="interaction",
                                    title="Miku persona deterministic pilot", family="pilot-persona-template-v1")
    with registry.transaction() as connection:
        for index in range(1000):
            dimensions = json.dumps({name: 600000 + ((index * 7919 + position * 997) % 300001)
                                     for position, name in enumerate(DIMENSIONS)}, sort_keys=True)
            prompt = f"작업 {index}의 진행 상황을 알려줘."
            response = f"작업 {index}은 아직 검증 중이야. 확인된 결과만 정리하고, 다음 안전한 단계를 같이 진행할게."
            connection.execute("INSERT OR IGNORE INTO persona_samples VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (stable_id("persona", index), persona_source, prompt, response, dimensions, 0,
                                750000, "quarantine", json.dumps({"generator": "deterministic-template-v1", "index": index}),
                                "quarantine"))

    agentic_source = _ensure_source(registry, "agentic-source", 0, source_type="interaction",
                                    title="Agentic trajectory deterministic pilot", family="pilot-agentic-template-v1")
    task_types = ("file.read", "repository.inspect", "tool.failure", "permission.request", "result.verify")
    with registry.transaction() as connection:
        for index in range(500):
            task_type = task_types[index % len(task_types)]
            failed = index % 5 == 2
            events = [{"type": "user.request", "index": index}, {"type": "tool.select", "tool": task_type},
                      {"type": "tool.result", "status": "failed" if failed else "ok"},
                      {"type": "result.verify", "verified": not failed},
                      {"type": "assistant.report", "honest_failure": failed}]
            connection.execute("INSERT OR IGNORE INTO agentic_trajectories VALUES (?,?,?,?,?,?,?,?,?)",
                               (stable_id("agentic", index), agentic_source, task_type,
                                json.dumps(events, sort_keys=True), 0, int(failed), int(not failed),
                                json.dumps({"generator": "deterministic-template-v1", "index": index}), "quarantine"))

    duplex_source = _ensure_source(registry, "duplex-source", 0, source_type="interaction",
                                   title="Duplex timeline deterministic pilot", family="pilot-duplex-template-v1")
    scenarios = ("normal", "backchannel", "interruption", "self-correction", "tool-waiting")
    with registry.transaction() as connection:
        for index in range(500):
            scenario = scenarios[index % len(scenarios)]
            events = [{"time_ms": 0, "actor": "user", "type": "speech.started"},
                      {"time_ms": 700 + index % 200, "actor": "agent", "type": scenario},
                      {"time_ms": 1800 + index % 400, "actor": "user", "type": "speech.ended"}]
            connection.execute("INSERT OR IGNORE INTO duplex_timelines VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (stable_id("duplex", index), duplex_source, scenario, json.dumps(events, sort_keys=True),
                                "ko-KR", "best_friend_collaborator", "acknowledge and preserve user control",
                                "do not fabricate completion", json.dumps({"generator": "deterministic-template-v1", "index": index}),
                                "quarantine"))

    holdout_ids = []
    for index, corpus in enumerate(("persona", "tts", "stt", "agentic", "duplex", "normalization")):
        family = f"pilot-{corpus}-eval-holdout-v1"
        source_id = stable_id("eval-source", index)
        with registry.connect() as connection:
            exists = connection.execute("SELECT 1 FROM sources WHERE source_id=?", (source_id,)).fetchone()
        if not exists:
            register_source(registry, source_id=source_id, source_type="interaction" if corpus in {"persona", "agentic", "duplex"} else "text",
                            title=f"Reserved {corpus} evaluation source group", origin="locally-generated-foundry-pilot",
                            creator="Miku-Agent Dataset Foundry", acquisition_method="deterministic local generation",
                            language="ko-KR", character_id="miku", derivative_family=family,
                            notes="Frozen empty holdout reservation; no training use", training_status="holdout")
            register_rights(registry, source_id, "owned", "generation-record",
                            "local deterministic generator in repository", "private evaluation only",
                            reviewer="dataset-operator", actor_type="user-delegated")
            assign_group(registry, family, split="eval", freeze=True)
        holdout_ids.append({"corpus": corpus, "source_id": source_id, "group_id": family})
    holdout_path = paths.root / "indexes" / "eval-holdouts-v1.json"
    holdout_body = json.dumps({"version": "eval-holdouts-v1", "sources": holdout_ids}, indent=2, sort_keys=True) + "\n"
    if not holdout_path.exists():
        holdout_path.write_text(holdout_body, encoding="utf-8")
        holdout_path.chmod(0o400)
    elif holdout_path.read_text(encoding="utf-8") != holdout_body:
        raise RuntimeError("frozen evaluation holdout manifest differs from deterministic reservation")
    with registry.connect() as connection:
        return {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("sources", "objects", "audio_samples", "text_samples", "persona_samples",
                              "agentic_trajectories", "duplex_timelines")}
