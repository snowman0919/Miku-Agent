from __future__ import annotations

import re

from .registry import Registry


def register_source(registry: Registry, *, source_id: str | None, source_type: str, title: str,
                    origin: str, acquisition_method: str, language: str, character_id: str,
                    derivative_family: str, creator: str | None = None, parent_work: str | None = None,
                    notes: str = "", quality_status: str = "unscored", review_status: str = "unreviewed",
                    training_status: str = "quarantine",
                    corpus_class: str = "quarantine_real_corpus",
                    evaluation_status: str | None = None) -> str:
    source_id = source_id or registry.new_id()
    with registry.transaction() as connection:
        connection.execute(
            """INSERT INTO sources(
                 source_id,source_type,title,origin,creator,acquisition_method,discovered_at,
                 acquired_at,language,character_id,parent_work,derivative_family,intake_status,
                 quality_status,review_status,training_status,notes,corpus_class,evaluation_status
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (source_id, source_type, title, origin, creator, acquisition_method, registry.now(),
             registry.now(), language, character_id, parent_work, derivative_family, "registered",
             quality_status, review_status, training_status, notes, corpus_class, evaluation_status),
        )
        registry.audit(connection, "source.registered", "local-writer", "source", source_id,
                       {"source_type": source_type, "origin": origin, "derivative_family": derivative_family})
    return source_id


def record_source_quality(
    registry: Registry, source_id: str, status: str, evidence_sha256: str, *, actor: str
) -> None:
    if status not in {"passed", "failed"} or re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None:
        raise ValueError("source quality status or evidence SHA-256 is invalid")
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("quality actor is required")
    with registry.transaction() as connection:
        if not connection.execute(
            "SELECT 1 FROM source_objects WHERE source_id=? AND sha256=?",
            (source_id, evidence_sha256),
        ).fetchone():
            raise PermissionError("quality evidence object is not bound to its source")
        previous = connection.execute(
            "SELECT quality_status FROM sources WHERE source_id=?", (source_id,)
        ).fetchone()
        if previous is None:
            raise KeyError(source_id)
        connection.execute("UPDATE sources SET quality_status=? WHERE source_id=?", (status, source_id))
        registry.audit(connection, "source.quality_revised", actor, "source", source_id,
                       {"previous": previous[0], "new": status, "evidence_sha256": evidence_sha256})
