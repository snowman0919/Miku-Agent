from __future__ import annotations

import json

import pytest

from conftest import source
from miku_foundry.effective_hours import summarize
from miku_foundry.jobs import authorize_remote_5090, ensure_job
from miku_foundry.rights import register_rights


def test_remote_job_never_stages_without_job_bound_grant(foundry):
    _, registry = foundry
    manifest = {"inputs": ["a" * 64], "code_commit": "b" * 40}
    job_id = ensure_job(registry, "remote-5090", manifest)
    assert ensure_job(registry, "remote-5090", manifest) == job_id
    with pytest.raises(PermissionError):
        authorize_remote_5090(registry, job_id, None)
    with pytest.raises(PermissionError):
        authorize_remote_5090(registry, job_id, {"job_id": "wrong", "allowed": True,
                                                 "input_digest": "a" * 64, "code_commit": "b" * 40})
    with registry.connect() as connection:
        assert connection.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0] == "prepared"


def test_singing_and_unknown_rights_never_inflate_speech_effective_hours(foundry):
    _, registry = foundry
    cleared = source(registry, family="cleared", training="accepted")
    unknown = source(registry, family="unknown", training="accepted")
    singing = source(registry, family="singing", training="accepted")
    register_rights(registry, cleared, "owned", "record", "fixture", "training", reviewer="op", actor_type="user")
    register_rights(registry, unknown, "unknown", "discovery", "unverified", "none", reviewer="op", actor_type="user")
    register_rights(registry, singing, "owned", "record", "fixture", "auxiliary", reviewer="op", actor_type="user")
    with registry.transaction() as connection:
        for index, (source_id, modality, duration) in enumerate(((cleared, "speech", 3600000),
                                                                  (unknown, "speech", 1800000),
                                                                  (singing, "singing_aux", 7200000))):
            digest = f"{index + 1:064x}"
            now = registry.now()
            connection.execute("INSERT INTO objects VALUES (?,?,?,?,?)", (digest, 1, None, now, now))
            connection.execute("INSERT INTO audio_samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (registry.new_id(), source_id, digest, duration, "ko-KR", "x", "x", "x", modality,
                                1000000, 1000000, 1000000, 1000000,
                                "auxiliary" if modality == "singing_aux" else "gold", "accepted"))
    result = summarize(registry)
    assert result["raw_speech_ms"] == 5400000
    assert result["accepted_physical_speech_ms"] == 3600000
    assert result["effective_speech_ms"] == 3600000
    assert result["raw_singing_ms"] == 7200000
    assert result["accepted_auxiliary_singing_ms"] == 7200000
