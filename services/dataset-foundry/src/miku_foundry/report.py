from __future__ import annotations

from .effective_hours import summarize
from .registry import Registry
from .split import leakage_findings


def inventory(registry: Registry) -> dict[str, object]:
    with registry.connect() as connection:
        counts = {}
        for table in ("sources", "objects", "audio_samples", "audio_metrics", "text_samples", "persona_samples",
                      "agentic_trajectories", "duplex_timelines", "reviews", "review_evidence", "jobs"):
            counts[table] = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        rights = {row["status"]: row["n"] for row in connection.execute(
            "SELECT status,count(*) n FROM rights_records GROUP BY status ORDER BY status")}
        training = {row["training_status"]: row["n"] for row in connection.execute(
            "SELECT training_status,count(*) n FROM sources GROUP BY training_status ORDER BY training_status")}
        corpus = {}
        for corpus_class in (
            "infrastructure_fixture", "candidate_corpus", "quarantine_real_corpus",
            "accepted_corpus", "evaluation_corpus",
        ):
            section = {"sources": connection.execute(
                "SELECT count(*) FROM sources WHERE corpus_class=?", (corpus_class,)
            ).fetchone()[0]}
            for table in (
                "audio_samples", "text_samples", "persona_samples",
                "agentic_trajectories", "duplex_timelines",
            ):
                section[table] = connection.execute(
                    f"""SELECT count(*) FROM {table} x JOIN sources s ON s.source_id=x.source_id
                        WHERE s.corpus_class=?""",
                    (corpus_class,),
                ).fetchone()[0]
            corpus[corpus_class] = section
        agentic = dict(connection.execute(
            """SELECT
                 count(*) FILTER (WHERE training_status='accepted') accepted,
                 count(*) FILTER (WHERE training_status='accepted' AND execution_backed=1) execution_backed,
                 count(*) FILTER (WHERE training_status='accepted' AND execution_receipt_sha256 IS NOT NULL) receipt_backed,
                 count(*) FILTER (WHERE training_status='accepted' AND failure_recovery=1) failure_recovery
               FROM agentic_trajectories"""
        ).fetchone())
    return {
        "counts": counts,
        "corpus": corpus,
        "rights_records": rights,
        "source_training_status": training,
        "agentic": agentic,
        "audio": summarize(registry),
        "split_leakage": leakage_findings(registry),
    }
