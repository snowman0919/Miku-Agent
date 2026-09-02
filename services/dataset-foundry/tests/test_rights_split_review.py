from __future__ import annotations

import pytest

from conftest import source
from miku_foundry.review import ReviewConflict, add_review
from miku_foundry.rights import promote_training, register_rights
from miku_foundry.split import assign_group, deterministic_split


def test_rights_gate_rejects_unknown_and_agent_self_promotion(foundry):
    _, registry = foundry
    source_id = source(registry)
    register_rights(registry, source_id, "unknown", "discovery", "unverified", "none",
                    reviewer="agent", actor_type="agent")
    with pytest.raises(PermissionError):
        promote_training(registry, source_id, actor="agent")
    with pytest.raises(PermissionError):
        register_rights(registry, source_id, "permitted", "license", "license text", "training",
                        reviewer="agent", actor_type="agent")
    with registry.connect() as connection:
        row = connection.execute("SELECT training_status FROM sources WHERE source_id=?", (source_id,)).fetchone()
        assert row[0] == "quarantine"


def test_cleared_rights_require_evidence_and_all_gates(foundry):
    _, registry = foundry
    source_id = source(registry)
    with pytest.raises(ValueError):
        register_rights(registry, source_id, "owned", "record", "", "training",
                        reviewer="operator", actor_type="user-delegated")
    register_rights(registry, source_id, "owned", "record", "fixture generation record", "training",
                    reviewer="operator", actor_type="user-delegated")
    promote_training(registry, source_id, actor="operator")
    with registry.connect() as connection:
        assert connection.execute("SELECT training_status FROM sources WHERE source_id=?", (source_id,)).fetchone()[0] == "accepted"


def test_split_is_stable_and_frozen_assignment_cannot_move(foundry):
    _, registry = foundry
    expected = deterministic_split("source-family")
    assert expected == deterministic_split("source-family")
    assert assign_group(registry, "source-family", freeze=True) == expected
    different = next(value for value in ("train", "validation", "test") if value != expected)
    with pytest.raises(PermissionError):
        assign_group(registry, "source-family", split=different)


def test_review_revision_conflict_never_overwrites_prior_decision(foundry):
    _, registry = foundry
    entity_id = source(registry)
    add_review(registry, "source", entity_id, "quarantine", "alice", "needs evidence", expected_revision=0)
    with pytest.raises(ReviewConflict):
        add_review(registry, "source", entity_id, "accept", "bob", "stale edit", expected_revision=0)
    with registry.connect() as connection:
        reviews = list(connection.execute("SELECT decision,reviewer,revision FROM reviews ORDER BY revision"))
        assert [tuple(row) for row in reviews] == [("quarantine", "alice", 1)]
        assert connection.execute("SELECT count(*) FROM audit_events WHERE event_type='review.conflict'").fetchone()[0] == 1
