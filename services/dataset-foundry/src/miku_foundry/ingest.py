from __future__ import annotations

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
