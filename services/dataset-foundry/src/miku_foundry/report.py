from __future__ import annotations

from .effective_hours import summarize
from .registry import Registry
from .split import leakage_findings


def inventory(registry: Registry) -> dict[str, object]:
    with registry.connect() as connection:
        counts = {}
        for table in ("sources", "objects", "audio_samples", "audio_metrics", "text_samples", "persona_samples",
                      "agentic_trajectories", "duplex_timelines", "reviews", "jobs"):
            counts[table] = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        rights = {row["status"]: row["n"] for row in connection.execute(
            "SELECT status,count(*) n FROM rights_records GROUP BY status ORDER BY status")}
        training = {row["training_status"]: row["n"] for row in connection.execute(
            "SELECT training_status,count(*) n FROM sources GROUP BY training_status ORDER BY training_status")}
    return {"counts": counts, "rights_records": rights, "source_training_status": training,
            "effective_hours_ms": summarize(registry), "split_leakage": leakage_findings(registry)}
