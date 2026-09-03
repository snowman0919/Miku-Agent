from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from collections import Counter
from pathlib import Path


SCENARIOS = (
    "normal_turn", "short_backchannel", "hesitation", "self_correction",
    "user_interruption", "agent_cancellation", "simultaneous_speech", "long_silence",
    "tool_waiting", "tool_completion", "topic_switch", "reconnect",
)
SUBJECTS = (("빌드", "빌드를"), ("데이터셋", "데이터셋을"), ("오디오", "오디오를"), ("권한", "권한을"),
            ("테스트", "테스트를"), ("문서", "문서를"), ("메모리", "메모리를"), ("스케줄", "스케줄을"),
            ("도구", "도구를"), ("모델", "모델을"), ("리포트", "리포트를"), ("브랜치", "브랜치를"))
ACTIONS = ("{object} 확인해 줘", "{object} 다시 검증해 줘", "{topic} 작업을 잠시 멈춰 줘", "{topic} 결과를 설명해 줘",
           "{topic} 실패 원인을 찾아 줘", "{topic} 작업을 안전하게 이어 가 줘", "{topic} 변경 사항을 비교해 줘",
           "{topic} 진행 상황을 알려 줘", "{topic} 작업을 취소해 줘", "{topic} 완료 여부를 점검해 줘",
           "{topic}에 다른 방법을 제안해 줘", "{topic} 작업 기록을 남겨 줘")
CONTEXTS = ("지금", "다음 단계 전에", "오류가 난 뒤", "권한을 바꾸지 말고", "기존 파일을 보존하면서", "검수 결과를 반영해서",
            "네트워크가 끊겼다가 돌아온 뒤", "사용자가 말하는 도중", "도구를 기다리는 동안", "주제가 바뀌었을 때", "긴 침묵 뒤", "동시에 말하게 되면")
RESPONSES = ("확인된 상태부터 말할게.", "멈추고 새 요청을 우선할게.", "실패를 숨기지 않고 원인부터 볼게.", "기존 결과를 보존한 채 다시 검사할게.",
             "완료로 단정하지 않고 증거를 확인할게.", "도구가 끝날 때까지 기다렸다가 알려 줄게.", "끊긴 지점부터 안전하게 이어 갈게.",
             "말을 끊지 않고 짧게 반응할게.", "동시에 말하면 내가 먼저 멈출게.", "새 주제로 전환했음을 확인할게.",
             "취소된 작업을 계속하지 않을게.", "검증 결과와 남은 작업을 나눠 말할게.")
POLICIES = {
    "normal_turn": ("요청을 확인하고 차례대로 답한다", "완료되지 않은 작업을 완료로 말하지 않는다"),
    "short_backchannel": ("짧은 맞장구 뒤 사용자의 발화를 계속 듣는다", "맞장구 때문에 사용자 발화를 중단시키지 않는다"),
    "hesitation": ("망설임이 끝날 때까지 기다린 뒤 의도를 확인한다", "침묵을 즉시 발화 종료로 오판하지 않는다"),
    "self_correction": ("수정된 표현을 최종 의도로 사용한다", "수정 전 표현으로 작업을 계속하지 않는다"),
    "user_interruption": ("진행 중 발화를 취소하고 새 사용자 발화를 듣는다", "취소된 응답을 끝까지 재생하지 않는다"),
    "agent_cancellation": ("취소를 확인하고 진행 중 작업을 중단한다", "취소 뒤 외부 작업을 계속하지 않는다"),
    "simultaneous_speech": ("겹침을 감지하면 agent가 양보하고 재개 여부를 묻는다", "동시 발화를 무시하고 말을 덮지 않는다"),
    "long_silence": ("긴 침묵 뒤 부담 없는 확인만 제공한다", "침묵을 동의나 완료로 해석하지 않는다"),
    "tool_waiting": ("도구 대기 상태와 완료를 구분해 알린다", "대기 중 결과를 만들어 내지 않는다"),
    "tool_completion": ("검증된 도구 결과만 요약한다", "exit code를 확인하지 않고 성공이라 하지 않는다"),
    "topic_switch": ("새 주제로 전환하고 이전 작업 상태를 보존한다", "이전 주제의 답을 새 요청에 이어 붙이지 않는다"),
    "reconnect": ("재연결 뒤 마지막 확인 상태부터 복구한다", "연결 중단 중의 결과를 추측하지 않는다"),
}


def event(actor: str, kind: str, start: int, end: int, text: str = "") -> dict[str, object]:
    value: dict[str, object] = {"time_ms": start, "end_ms": end, "actor": actor, "type": kind}
    if text:
        value["text"] = text
    return value


def timeline_events(scenario: str, index: int, user_text: str, agent_text: str) -> list[dict[str, object]]:
    user_ms = 700 + index % 7 * 90
    agent_ms = 650 + (index // 7) % 6 * 100
    gap = 120 + index % 5 * 70
    overlap = 80 + index % 6 * 45
    pause = 280 + index % 5 * 110
    if scenario == "normal_turn":
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("agent", "agent.processing", user_ms, user_ms + gap),
                event("agent", "speech.agent", user_ms + gap, user_ms + gap + agent_ms, agent_text),
                event("agent", "turn.closed", user_ms + gap + agent_ms, user_ms + gap + agent_ms)]
    elif scenario == "short_backchannel":
        rows = [event("user", "speech.user", 0, user_ms + 500, user_text),
                event("agent", "agent.backchannel", user_ms // 2, user_ms // 2 + 160, "응."),
                event("user", "speech.user", user_ms, user_ms + 500, "그리고 검증 결과도 알려 줘."),
                event("agent", "speech.agent", user_ms + 500 + gap, user_ms + 500 + gap + agent_ms, agent_text)]
    elif scenario == "hesitation":
        half = user_ms // 2
        rows = [event("user", "speech.user", 0, half, "음, "), event("user", "user.hesitation", half, half + pause),
                event("user", "speech.user", half + pause, user_ms + pause, user_text),
                event("agent", "speech.agent", user_ms + pause + gap, user_ms + pause + gap + agent_ms, agent_text)]
    elif scenario == "self_correction":
        rows = [event("user", "speech.user", 0, user_ms // 2, "빌드를 배포해 줘."),
                event("user", "user.self_correction", user_ms // 2, user_ms // 2 + pause, "아니, 배포 말고 검증만 해 줘."),
                event("user", "speech.user", user_ms // 2 + pause, user_ms + pause, user_text),
                event("agent", "speech.agent", user_ms + pause + gap, user_ms + pause + gap + agent_ms, agent_text)]
    elif scenario == "user_interruption":
        agent_start = user_ms + gap
        interrupt_at = agent_start + agent_ms // 3
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("agent", "speech.agent", agent_start, interrupt_at + 40, agent_text),
                event("user", "user.interruption", interrupt_at, interrupt_at + 260, "잠깐, 먼저 멈춰 줘."),
                event("agent", "agent.cancelled", interrupt_at + 40, interrupt_at + 40),
                event("agent", "speech.agent", interrupt_at + 260 + gap, interrupt_at + 620 + gap, "응, 멈췄어. 새 요청을 들을게.")]
    elif scenario == "agent_cancellation":
        cancel_at = user_ms + gap + agent_ms // 2
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("agent", "speech.agent", user_ms + gap, cancel_at, agent_text),
                event("user", "user.cancel_request", cancel_at - 120, cancel_at + 120, "그 작업은 취소해 줘."),
                event("agent", "agent.cancelled", cancel_at, cancel_at),
                event("agent", "speech.agent", cancel_at + gap, cancel_at + gap + 360, "취소했어. 추가 실행은 하지 않을게.")]
    elif scenario == "simultaneous_speech":
        rows = [event("user", "speech.user", 0, user_ms, user_text),
                event("agent", "speech.agent", user_ms - overlap, user_ms - overlap + agent_ms, agent_text),
                event("tool", "overlap.detected", user_ms - overlap, user_ms, ""),
                event("agent", "speech.agent", user_ms - overlap + agent_ms + gap, user_ms - overlap + agent_ms + gap + 420, "내가 멈출게. 먼저 말해 줘.")]
    elif scenario == "long_silence":
        silence = 2500 + index % 8 * 300
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("agent", "silence", user_ms, user_ms + silence),
                event("agent", "speech.agent", user_ms + silence, user_ms + silence + 450, "괜찮아, 준비되면 이어서 말해 줘."),
                event("agent", "silence", user_ms + silence + 450, user_ms + silence + 450 + pause),
                event("user", "speech.user", user_ms + silence + 450 + pause, user_ms + silence + 900 + pause, "응, 계속할게.")]
    elif scenario == "tool_waiting":
        tool_start = user_ms + gap + 300
        tool_end = tool_start + 900 + index % 7 * 170
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("agent", "speech.agent", user_ms + gap, user_ms + gap + 300, "확인하고 알려 줄게."),
                event("tool", "tool.started", tool_start, tool_start), event("agent", "agent.waiting", tool_start, tool_end),
                event("tool", "tool.completed", tool_end, tool_end), event("agent", "speech.agent", tool_end + gap, tool_end + gap + agent_ms, agent_text)]
    elif scenario == "tool_completion":
        tool_start = user_ms + gap
        tool_end = tool_start + 500 + index % 9 * 120
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("tool", "tool.started", tool_start, tool_start),
                event("tool", "tool.completed", tool_end, tool_end), event("agent", "speech.agent", tool_end + gap, tool_end + gap + agent_ms, agent_text)]
    elif scenario == "topic_switch":
        switch = user_ms + gap + agent_ms // 2
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("agent", "speech.agent", user_ms + gap, switch + 40, agent_text),
                event("user", "user.topic_switch", switch, switch + 300, "그보다 다음 일정부터 보자."),
                event("agent", "agent.cancelled", switch + 40, switch + 40),
                event("agent", "speech.agent", switch + 300 + gap, switch + 300 + gap + 480, "좋아, 이전 상태를 보존하고 일정으로 전환할게.")]
    else:
        lost = user_ms + gap
        restored = lost + 800 + index % 6 * 200
        rows = [event("user", "speech.user", 0, user_ms, user_text), event("tool", "connection.lost", lost, lost),
                event("agent", "silence", lost, restored), event("tool", "connection.restored", restored, restored),
                event("agent", "speech.agent", restored + gap, restored + gap + agent_ms, "다시 연결됐어. 마지막 확인 상태부터 이어 갈게.")]
    rows.sort(key=lambda value: value["time_ms"])
    return rows


def overlap_ms(events: list[dict[str, object]]) -> int:
    speech = [(row["actor"], row["time_ms"], row["end_ms"]) for row in events if str(row["type"]).startswith("speech.")]
    return sum(max(0, min(ae, be) - max(astart, bstart)) for i, (aa, astart, ae) in enumerate(speech)
               for ba, bstart, be in speech[i + 1:] if aa != ba)


def build(source_id: str, count: int, generator_sha256: str) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        topic, object_form = SUBJECTS[(index * 5) % len(SUBJECTS)]
        action = ACTIONS[(index * 7 + index // 13) % len(ACTIONS)].format(topic=topic, object=object_form)
        user_text = f"{CONTEXTS[(index // 12) % len(CONTEXTS)]} {action}"
        agent_text = RESPONSES[(index * 5 + index // 11) % len(RESPONSES)]
        events = timeline_events(scenario, index, user_text, agent_text)
        duration = max(row["end_ms"] for row in events)
        provenance = {
            "generator": "deterministic-combinatorial-duplex-v1",
            "generator_sha256": generator_sha256,
            "template_family": f"{scenario}:{(index // 12) % 16}",
            "timestamp_backed": True,
            "duration_ms": duration,
            "overlap_ms": overlap_ms(events),
            "silence_ms": sum(row["end_ms"] - row["time_ms"] for row in events if row["type"] == "silence"),
            "sequence_index": index,
        }
        row = {
            "timeline_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"miku-duplex-v1:{source_id}:{index}")),
            "source_id": source_id,
            "scenario": scenario,
            "events": events,
            "language": "ko-KR",
            "relationship_mode": "best_friend_collaborator",
            "expected_behavior": POLICIES[scenario][0],
            "forbidden_behavior": POLICIES[scenario][1],
            "timeline_source": "locally-generated-timestamp-backed-v1",
            "audio_input_sha256": None,
            "audio_output_sha256": None,
            "event_alignment_ppm": 1000000,
            "human_adjudication": None,
            "evidence_kind": "synthetic",
            "provenance": provenance,
            "training_status": "quarantine",
        }
        rows.append(row)
    bodies = {json.dumps(row["events"], ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in rows}
    if len(bodies) != count:
        raise RuntimeError("generated duplicate event sequence")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.count <= 0 or args.count > 20000 or args.output.exists():
        raise ValueError("count must be 1..20000 and output must not exist")
    generator_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    rows = build(args.source_id, args.count, generator_hash)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    args.output.write_text(body, encoding="utf-8")
    families = Counter(row["provenance"]["template_family"] for row in rows)
    print(json.dumps({"rows": len(rows), "sha256": hashlib.sha256(body.encode()).hexdigest(),
                      "scenario_counts": Counter(row["scenario"] for row in rows),
                      "event_count_distribution": Counter(len(row["events"]) for row in rows),
                      "template_families": len(families), "largest_template_family": max(families.values()),
                      "overlap_rows": sum(row["provenance"]["overlap_ms"] > 0 for row in rows),
                      "silence_rows": sum(row["provenance"]["silence_ms"] > 0 for row in rows)},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
