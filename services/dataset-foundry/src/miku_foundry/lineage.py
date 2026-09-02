from __future__ import annotations

import hashlib
import json

from .registry import Registry


def plan_transform(registry: Registry, kind: str, inputs: list[str], spec: dict[str, object],
                   *, tool: str, tool_version: str) -> str:
    canonical = json.dumps({"inputs": inputs, "spec": spec}, sort_keys=True, separators=(",", ":"))
    spec_sha256 = hashlib.sha256(f"{kind}\0{tool}\0{tool_version}\0{canonical}".encode()).hexdigest()
    with registry.transaction() as connection:
        existing = connection.execute("SELECT transform_id FROM transforms WHERE spec_sha256=?", (spec_sha256,)).fetchone()
        if existing:
            return existing["transform_id"]
        for digest in inputs:
            if not connection.execute("SELECT 1 FROM objects WHERE sha256=?", (digest,)).fetchone():
                raise KeyError(f"unknown input object: {digest}")
        transform_id = registry.new_id()
        connection.execute("INSERT INTO transforms VALUES (?,?,?,?,?,?,?,?,?)",
                           (transform_id, kind, canonical, spec_sha256, tool, tool_version,
                            "planned", registry.now(), None))
    return transform_id


def add_lineage(registry: Registry, transform_id: str, parents: list[str], child: str) -> None:
    with registry.transaction() as connection:
        if not connection.execute("SELECT 1 FROM objects WHERE sha256=?", (child,)).fetchone():
            raise KeyError(child)
        for parent in parents:
            cycle = connection.execute(
                """WITH RECURSIVE descendants(node) AS (
                       SELECT child_sha256 FROM lineage_edges WHERE parent_sha256=?
                       UNION SELECT e.child_sha256 FROM lineage_edges e JOIN descendants d ON e.parent_sha256=d.node
                     ) SELECT 1 FROM descendants WHERE node=? LIMIT 1""", (child, parent)
            ).fetchone()
            if parent == child or cycle:
                raise ValueError("lineage edge would create a cycle")
        for parent in parents:
            connection.execute("INSERT OR IGNORE INTO lineage_edges VALUES (?,?,?)", (parent, child, transform_id))
        connection.execute("UPDATE transforms SET status='succeeded', completed_at=? WHERE transform_id=?",
                           (registry.now(), transform_id))
        registry.audit(connection, "lineage.committed", "local-writer", "transform", transform_id,
                       {"parents": parents, "child": child})
