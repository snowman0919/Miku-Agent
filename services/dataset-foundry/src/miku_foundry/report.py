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
        current_rights = {row["status"]: row["n"] for row in connection.execute(
            """SELECT status,count(*) n FROM rights_records r
               WHERE rights_id=(SELECT rights_id FROM rights_records latest
                 WHERE latest.source_id=r.source_id ORDER BY created_at DESC,rights_id DESC LIMIT 1)
               GROUP BY status ORDER BY status"""
        )}
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
        duplex = dict(connection.execute(
            """SELECT
                 count(*) FILTER (WHERE training_status='accepted') accepted,
                 count(*) FILTER (WHERE training_status='accepted' AND human_adjudication IS NOT NULL) human_adjudicated,
                 count(*) FILTER (WHERE training_status='accepted' AND (
                   audio_input_sha256 IS NOT NULL OR audio_output_sha256 IS NOT NULL
                   OR json_extract(provenance_json,'$.timestamp_backed')=1
                 )) audio_or_timestamp_backed,
                 count(DISTINCT events_json) FILTER (WHERE training_status='accepted') distinct_event_sequences
               FROM duplex_timelines"""
        ).fetchone())
        duplex["scenario_distribution"] = {
            row["scenario"]: row["n"] for row in connection.execute(
                """SELECT scenario,count(*) n FROM duplex_timelines
                   WHERE training_status='accepted' GROUP BY scenario ORDER BY scenario"""
            )
        }
        korean_text = dict(connection.execute(
            """SELECT
                 count(*) FILTER (WHERE training_status='accepted') accepted_documents,
                 coalesce(sum(CASE WHEN training_status='accepted'
                   THEN json_extract(provenance_json,'$.token_count') ELSE 0 END),0) accepted_tokens,
                 count(DISTINCT json_extract(provenance_json,'$.document_sha256'))
                   FILTER (WHERE training_status='accepted') exact_unique_documents
               FROM text_samples WHERE corpus='korean_foundation'"""
        ).fetchone())
        korean_text["tokenizers"] = [row[0] for row in connection.execute(
            """SELECT DISTINCT json_extract(provenance_json,'$.tokenizer_id')
               FROM text_samples WHERE corpus='korean_foundation' AND training_status='accepted'
               ORDER BY 1"""
        )]
    return {
        "counts": counts,
        "corpus": corpus,
        "rights_records": rights,
        "current_rights_sources": current_rights,
        "source_training_status": training,
        "agentic": agentic,
        "duplex": duplex,
        "korean_text": korean_text,
        "audio": summarize(registry),
        "split_leakage": leakage_findings(registry),
    }
