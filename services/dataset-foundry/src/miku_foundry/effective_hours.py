from __future__ import annotations

from .registry import Registry


def summarize(registry: Registry) -> dict[str, int]:
    result = {
        "raw_speech_ms": 0,
        "accepted_physical_speech_ms": 0,
        "effective_speech_ms": 0,
        "raw_singing_ms": 0,
        "accepted_auxiliary_singing_ms": 0,
        "quarantine_ms": 0,
        "rejected_ms": 0,
    }
    with registry.connect() as connection:
        query = """
          SELECT a.*, s.training_status source_training_status,
                 (SELECT status FROM rights_records r WHERE r.source_id=s.source_id
                  ORDER BY created_at DESC, rights_id DESC LIMIT 1) rights_status
          FROM audio_samples a JOIN sources s ON s.source_id=a.source_id
        """
        for row in connection.execute(query):
            duration = row["duration_ms"]
            if row["modality"] == "singing_aux":
                result["raw_singing_ms"] += duration
                if row["training_status"] == "accepted" and row["rights_status"] in {"owned", "licensed", "permitted"}:
                    result["accepted_auxiliary_singing_ms"] += duration
                continue
            result["raw_speech_ms"] += duration
            if row["training_status"] == "rejected":
                result["rejected_ms"] += duration
            elif row["training_status"] != "accepted" or row["rights_status"] not in {"owned", "licensed", "permitted"}:
                result["quarantine_ms"] += duration
            else:
                result["accepted_physical_speech_ms"] += duration
                weighted = duration
                for field in ("quality_ppm", "alignment_ppm", "review_weight_ppm", "source_tier_weight_ppm"):
                    weighted = (weighted * row[field]) // 1_000_000
                result["effective_speech_ms"] += weighted
    return result
