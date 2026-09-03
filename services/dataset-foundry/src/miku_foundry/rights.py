from __future__ import annotations

import re

from .registry import RIGHTS_CLEARED, Registry
from .review import assert_review_accepted


def register_rights(registry: Registry, source_id: str, status: str, evidence_type: str,
                    evidence_ref: str, allowed_use: str, *, reviewer: str,
                    actor_type: str, restrictions: str = "", evidence_sha256: str | None = None,
                    expires_at: int | None = None, training_allowed: bool = False) -> str:
    if not isinstance(training_allowed, bool):
        raise ValueError("training_allowed must be a boolean")
    if status in RIGHTS_CLEARED and not evidence_ref.strip():
        raise ValueError("cleared rights require evidence")
    if evidence_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None:
        raise ValueError("rights evidence SHA-256 is invalid")
    with registry.transaction() as connection:
        if evidence_sha256 is not None and not connection.execute(
            "SELECT 1 FROM source_objects WHERE source_id=? AND sha256=?",
            (source_id, evidence_sha256),
        ).fetchone():
            raise PermissionError("rights evidence object is not bound to its source")
        previous = registry.current_rights(connection, source_id)
        if actor_type == "agent" and previous and previous["status"] in {"unknown", "restricted"} and status in RIGHTS_CLEARED:
            raise PermissionError("an agent cannot promote unresolved rights")
        rights_id = registry.new_id()
        connection.execute(
            """INSERT INTO rights_records(
                 rights_id,source_id,status,evidence_type,evidence_ref,evidence_sha256,allowed_use,
                 restrictions,expires_at,reviewer,actor_type,created_at,training_allowed
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rights_id, source_id, status, evidence_type, evidence_ref, evidence_sha256,
             allowed_use, restrictions, expires_at, reviewer, actor_type, registry.now(), int(training_allowed)),
        )
        registry.audit(connection, "rights.revised", reviewer, "source", source_id,
                       {"previous": previous["status"] if previous else None, "new": status,
                        "rights_id": rights_id, "actor_type": actor_type,
                        "training_allowed": training_allowed})
    return rights_id


def promote_training(registry: Registry, source_id: str, *, actor: str) -> None:
    with registry.transaction() as connection:
        source = connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
        if source is None:
            raise KeyError(source_id)
        rights = registry.current_rights(connection, source_id)
        if (not rights or rights["status"] not in RIGHTS_CLEARED or not rights["evidence_ref"]
                or not rights["training_allowed"]):
            raise PermissionError("rights gate failed")
        if rights["expires_at"] is not None and rights["expires_at"] <= registry.now():
            raise PermissionError("rights evidence expired")
        if source["quality_status"] != "passed" or source["review_status"] != "reviewed":
            raise PermissionError("quality and review gates must pass independently")
        assert_review_accepted(connection, "source", source_id)
        if source["corpus_class"] in {"infrastructure_fixture", "evaluation_corpus"}:
            raise PermissionError("fixture and evaluation sources cannot be training promoted")
        connection.execute(
            "UPDATE sources SET training_status='accepted', corpus_class='accepted_corpus' WHERE source_id=?",
            (source_id,),
        )
        registry.audit(connection, "training.promoted", actor, "source", source_id,
                       {"rights_id": rights["rights_id"]})
