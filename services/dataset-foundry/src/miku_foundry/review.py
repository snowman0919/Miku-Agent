from __future__ import annotations

from .registry import Registry


class ReviewConflict(RuntimeError):
    pass


def add_review(registry: Registry, entity_type: str, entity_id: str, decision: str,
               reviewer: str, reason: str, *, expected_revision: int) -> str:
    conflict: tuple[int, int] | None = None
    review_id = ""
    with registry.transaction() as connection:
        latest = connection.execute(
            "SELECT * FROM reviews WHERE entity_type=? AND entity_id=? ORDER BY revision DESC LIMIT 1",
            (entity_type, entity_id),
        ).fetchone()
        actual_revision = latest["revision"] if latest else 0
        if actual_revision != expected_revision:
            registry.audit(connection, "review.conflict", reviewer, entity_type, entity_id,
                           {"expected_revision": expected_revision, "actual_revision": actual_revision})
            conflict = (expected_revision, actual_revision)
        else:
            review_id = registry.new_id()
            connection.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)",
                               (review_id, entity_type, entity_id, actual_revision + 1, reviewer,
                                latest["decision"] if latest else None, decision, reason, registry.now()))
            registry.audit(connection, "review.revised", reviewer, entity_type, entity_id,
                           {"previous": latest["decision"] if latest else None, "new": decision,
                            "revision": actual_revision + 1})
    if conflict:
        raise ReviewConflict(f"expected revision {conflict[0]}, found {conflict[1]}")
    return review_id
