from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import source
from miku_foundry.duplex import import_duplex_bundle


def row(source_id: str, timeline_id: str, *, scenario: str = "normal_turn") -> dict[str, object]:
    events = [
        {"time_ms": 0, "end_ms": 800, "actor": "user", "type": "speech.user", "text": "상태를 알려 줘."},
        {"time_ms": 800, "end_ms": 950, "actor": "agent", "type": "agent.processing"},
        {"time_ms": 950, "end_ms": 1700, "actor": "agent", "type": "speech.agent", "text": "확인해서 알려 줄게."},
        {"time_ms": 1700, "end_ms": 1700, "actor": "agent", "type": "turn.closed"},
    ]
    return {
        "timeline_id": timeline_id,
        "source_id": source_id,
        "scenario": scenario,
        "events": events,
        "language": "ko-KR",
        "relationship_mode": "best_friend_collaborator",
        "expected_behavior": "확인된 상태를 설명한다",
        "forbidden_behavior": "완료를 추측하지 않는다",
        "timeline_source": "local-test",
        "audio_input_sha256": None,
        "audio_output_sha256": None,
        "event_alignment_ppm": 1000000,
        "human_adjudication": None,
        "evidence_kind": "synthetic",
        "provenance": {
            "timestamp_backed": True,
            "duration_ms": 1700,
            "overlap_ms": 0,
            "silence_ms": 0,
            "generator_sha256": "a" * 64,
            "template_family": "normal:0",
        },
        "training_status": "quarantine",
    }


def test_duplex_bundle_import_is_validated_and_idempotent(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry)
    path = tmp_path / "duplex.jsonl"
    value = row(source_id, "00000000-0000-4000-8000-000000000010")
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
    result = import_duplex_bundle(paths, registry, path, actor="operator")
    assert result["inserted"] == 1 and result["idempotent"] is False
    assert import_duplex_bundle(paths, registry, path, actor="operator")["idempotent"] is True
    with registry.transaction() as connection:
        connection.execute("UPDATE duplex_timelines SET training_status='accepted'")
    assert import_duplex_bundle(paths, registry, path, actor="operator")["idempotent"] is True
    with registry.connect() as connection:
        assert connection.execute("SELECT count(*) FROM duplex_timelines").fetchone()[0] == 1
        assert connection.execute(
            "SELECT role FROM source_objects WHERE sha256=?", (result["bundle_sha256"],)
        ).fetchone()[0] == "duplex:timestamp-bundle"

    duplicate = row(source_id, "00000000-0000-4000-8000-000000000011")
    path.write_text(json.dumps(duplicate, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicates an existing"):
        import_duplex_bundle(paths, registry, path, actor="operator")

    value["provenance"]["duration_ms"] = 1699  # type: ignore[index]
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="inconsistent"):
        import_duplex_bundle(paths, registry, path, actor="operator")
