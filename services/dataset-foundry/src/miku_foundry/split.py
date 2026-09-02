from __future__ import annotations

import hashlib

from .registry import Registry


def deterministic_split(group_id: str, policy_version: str = "source-split-v1") -> str:
    value = int.from_bytes(hashlib.sha256(f"{policy_version}\0{group_id}".encode()).digest()[:8], "big") % 10000
    if value < 8000:
        return "train"
    if value < 9000:
        return "validation"
    return "test"


def assign_group(registry: Registry, group_id: str, *, policy_version: str = "source-split-v1",
                 split: str | None = None, freeze: bool = False) -> str:
    chosen = split or deterministic_split(group_id, policy_version)
    with registry.transaction() as connection:
        existing = connection.execute(
            "SELECT * FROM split_assignments WHERE group_id=? AND policy_version=?", (group_id, policy_version)
        ).fetchone()
        if existing:
            if existing["split"] != chosen or (existing["frozen"] and not freeze):
                raise PermissionError("split assignment is immutable for this policy version")
            return existing["split"]
        connection.execute("INSERT INTO split_assignments VALUES (?,?,?,?,?)",
                           (group_id, policy_version, chosen, int(freeze), registry.now()))
        registry.audit(connection, "split.assigned", "local-writer", "source_group", group_id,
                       {"policy_version": policy_version, "split": chosen, "frozen": freeze})
    return chosen


def leakage_findings(registry: Registry, policy_version: str = "source-split-v1") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    with registry.connect() as connection:
        query = """
        WITH RECURSIVE ancestry(root, node) AS (
          SELECT parent_sha256, child_sha256 FROM lineage_edges
          UNION
          SELECT ancestry.root, lineage_edges.child_sha256
          FROM ancestry JOIN lineage_edges ON lineage_edges.parent_sha256=ancestry.node
        ), object_groups AS (
          SELECT so.sha256, s.derivative_family AS group_id
          FROM source_objects so JOIN sources s ON s.source_id=so.source_id
        )
        SELECT DISTINCT p.group_id parent_group, c.group_id child_group,
               ps.split parent_split, cs.split child_split
        FROM ancestry a
        JOIN object_groups p ON p.sha256=a.root
        JOIN object_groups c ON c.sha256=a.node
        JOIN split_assignments ps ON ps.group_id=p.group_id AND ps.policy_version=?
        JOIN split_assignments cs ON cs.group_id=c.group_id AND cs.policy_version=?
        WHERE ps.split<>cs.split
        """
        for row in connection.execute(query, (policy_version, policy_version)):
            findings.append(dict(row))
    return findings
