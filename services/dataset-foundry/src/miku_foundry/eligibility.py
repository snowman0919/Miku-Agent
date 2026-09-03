from __future__ import annotations

import json
import re
from collections.abc import Mapping


PERSONA_DIMENSIONS = {
    "purity", "liveliness", "warmth", "optimism", "curiosity", "creativity",
    "playfulness", "supportiveness", "independence", "digital_identity", "friendship", "helpfulness",
}
DUPLEX_SCENARIOS = {
    "normal_turn", "short_backchannel", "hesitation", "self_correction",
    "user_interruption", "agent_cancellation", "simultaneous_speech", "long_silence",
    "tool_waiting", "tool_completion", "topic_switch", "reconnect",
}


def _ppm(value: object, *, signed: bool = False) -> bool:
    lower = -1000000 if signed else 0
    return isinstance(value, int) and not isinstance(value, bool) and lower <= value <= 1000000


def _sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def assert_corpus_row_eligible(corpus: str, row: Mapping[str, object]) -> None:
    if corpus == "persona":
        if row["hard_violation"]:
            raise PermissionError("persona hard violation blocks training")
        dimensions = json.loads(str(row["dimensions_json"]))
        if set(dimensions) != PERSONA_DIMENSIONS:
            raise PermissionError("persona annotations do not cover all dimensions")
        for value in dimensions.values():
            if (not isinstance(value, dict) or not _ppm(value.get("score"), signed=True)
                    or not _ppm(value.get("confidence_ppm"))
                    or not isinstance(value.get("evaluator_id"), str) or not value["evaluator_id"]
                    or not isinstance(value.get("evaluator_revision"), str) or not value["evaluator_revision"]
                    or not (value.get("evidence_span") or value.get("reason_code"))
                    or (value.get("human_override") is not None
                        and not _ppm(value.get("human_override"), signed=True))):
                raise PermissionError("persona annotations lack valid evidence")
    elif corpus == "agentic" and row["execution_backed"]:
        if (row["verification_status"] != "execution_backed"
                or not row["execution_receipt_sha256"]
                or not row["environment_binding_json"]
                or not row["test_receipt_json"]):
            raise PermissionError("execution-backed trajectory lacks receipts")
    elif corpus == "duplex":
        events = json.loads(str(row["events_json"]))
        provenance = json.loads(str(row["provenance_json"]))
        if row["scenario"] not in DUPLEX_SCENARIOS or not isinstance(events, list) or not 4 <= len(events) <= 12:
            raise PermissionError("duplex timeline lacks a supported varied event sequence")
        if not isinstance(provenance, dict) or provenance.get("timestamp_backed") is not True:
            raise PermissionError("duplex timeline lacks timestamp provenance")
        starts, actors, speech = [], set(), []
        silence_ms = 0
        types = set()
        for event in events:
            if not isinstance(event, dict):
                raise PermissionError("duplex event must be an object")
            start, end = event.get("time_ms"), event.get("end_ms")
            if (not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int)
                    or isinstance(end, bool) or start < 0 or end < start
                    or event.get("actor") not in {"user", "agent", "tool"}
                    or not isinstance(event.get("type"), str) or not event["type"]):
                raise PermissionError("duplex event has invalid timestamp or identity")
            starts.append(start)
            actors.add(event["actor"])
            types.add(event["type"])
            if str(event["type"]).startswith("speech."):
                if end == start:
                    raise PermissionError("duplex speech event must have duration")
                speech.append((event["actor"], start, end))
            if event["type"] == "silence":
                silence_ms += end - start
        if starts != sorted(starts) or not {"user", "agent"} <= actors:
            raise PermissionError("duplex events must be ordered and include both speakers")
        overlap_ms = sum(
            max(0, min(left_end, right_end) - max(left_start, right_start))
            for index, (left_actor, left_start, left_end) in enumerate(speech)
            for right_actor, right_start, right_end in speech[index + 1:]
            if left_actor != right_actor
        )
        duration_ms = max(event["end_ms"] for event in events)
        if (duration_ms <= 0 or duration_ms > 60000
                or provenance.get("duration_ms") != duration_ms
                or provenance.get("overlap_ms") != overlap_ms
                or provenance.get("silence_ms") != silence_ms
                or not _sha256(provenance.get("generator_sha256"))
                or not isinstance(provenance.get("template_family"), str)
                or not provenance["template_family"]
                or not _ppm(row["event_alignment_ppm"])
                or not row["timeline_source"] or not row["language"] or not row["relationship_mode"]
                or not row["expected_behavior"] or not row["forbidden_behavior"]
                or row["expected_behavior"] == row["forbidden_behavior"]):
            raise PermissionError("duplex timing or policy provenance is inconsistent")
        required = {
            "user_interruption": {"user.interruption", "agent.cancelled"},
            "agent_cancellation": {"agent.cancelled"},
            "simultaneous_speech": {"speech.user", "speech.agent"},
            "long_silence": {"silence"},
            "tool_waiting": {"tool.started", "agent.waiting", "tool.completed"},
            "tool_completion": {"tool.started", "tool.completed"},
            "topic_switch": {"user.topic_switch"},
            "reconnect": {"connection.lost", "connection.restored"},
            "hesitation": {"user.hesitation"},
            "self_correction": {"user.self_correction"},
            "short_backchannel": {"agent.backchannel"},
        }.get(str(row["scenario"]), set())
        if not required <= types or (row["scenario"] == "simultaneous_speech" and overlap_ms <= 0):
            raise PermissionError("duplex events do not substantiate the scenario")
        if row["evidence_kind"] not in {"synthetic", "recorded", "rendered"}:
            raise PermissionError("duplex evidence kind is invalid")
        if (row["evidence_kind"] == "synthetic"
                and (row["audio_input_sha256"] is not None or row["audio_output_sha256"] is not None
                     or row["event_alignment_ppm"] != 1000000)):
            raise PermissionError("timestamp-backed synthetic duplex evidence is inconsistent")
        if (row["evidence_kind"] in {"recorded", "rendered"}
                and not (_sha256(row["audio_input_sha256"]) or _sha256(row["audio_output_sha256"]))):
            raise PermissionError("audio-backed duplex evidence lacks an object hash")
