from __future__ import annotations

from collections import defaultdict

from .registry import Registry


def _union_ms(rows: list[tuple[str, int, int]]) -> int:
    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for parent, start, end in rows:
        grouped[parent].append((start, end))
    total = 0
    for intervals in grouped.values():
        current_start = current_end = -1
        for start, end in sorted(intervals):
            if start > current_end:
                total += max(0, current_end - current_start)
                current_start, current_end = start, end
            else:
                current_end = max(current_end, end)
        total += max(0, current_end - current_start)
    return total


def _weighted_union_ms(rows: list[tuple[str, int, int, int]]) -> int:
    grouped: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for parent, start, end, weight in rows:
        grouped[parent].append((start, end, weight))
    total = 0
    for intervals in grouped.values():
        points = sorted({point for start, end, _ in intervals for point in (start, end)})
        for start, end in zip(points, points[1:]):
            weight = max(
                (value for left, right, value in intervals if left <= start and right >= end),
                default=0,
            )
            total += ((end - start) * weight) // 1_000_000
    return total


def summarize(registry: Registry) -> dict[str, int]:
    result = {
        "row_count": 0,
        "unique_sample_count": 0,
        "unique_object_count": 0,
        "referenced_duration_ms": 0,
        "unique_physical_interval_ms": 0,
        "raw_speech_ms": 0,
        "accepted_physical_speech_ms": 0,
        "effective_speech_ms": 0,
        "raw_singing_ms": 0,
        "accepted_auxiliary_singing_ms": 0,
        "quarantine_ms": 0,
        "rejected_ms": 0,
    }
    speech: list[tuple[str, int, int]] = []
    singing: list[tuple[str, int, int]] = []
    accepted_speech: list[tuple[str, int, int]] = []
    accepted_singing: list[tuple[str, int, int]] = []
    quarantine: list[tuple[str, int, int]] = []
    rejected: list[tuple[str, int, int]] = []
    weighted: list[tuple[str, int, int, int]] = []
    fingerprints: set[str] = set()
    objects: set[str] = set()
    with registry.connect() as connection:
        query = """
          SELECT a.*,
                 (SELECT status FROM rights_records r WHERE r.source_id=a.source_id
                  ORDER BY created_at DESC, rights_id DESC LIMIT 1) rights_status,
                 (SELECT expires_at FROM rights_records r WHERE r.source_id=a.source_id
                  ORDER BY created_at DESC, rights_id DESC LIMIT 1) rights_expires_at,
                 (SELECT training_allowed FROM rights_records r WHERE r.source_id=a.source_id
                  ORDER BY created_at DESC, rights_id DESC LIMIT 1) rights_training_allowed,
                 (SELECT r.decision FROM reviews r WHERE r.entity_type='source' AND r.entity_id=a.source_id
                  ORDER BY r.revision DESC LIMIT 1) source_review_decision,
                 (SELECT e.evidence_json FROM reviews r LEFT JOIN review_evidence e USING(review_id)
                  WHERE r.entity_type='source' AND r.entity_id=a.source_id
                  ORDER BY r.revision DESC LIMIT 1) source_review_evidence,
                 (SELECT r.decision FROM reviews r WHERE r.entity_type='audio' AND r.entity_id=a.sample_id
                  ORDER BY r.revision DESC LIMIT 1) sample_review_decision,
                 (SELECT e.evidence_json FROM reviews r LEFT JOIN review_evidence e USING(review_id)
                  WHERE r.entity_type='audio' AND r.entity_id=a.sample_id
                  ORDER BY r.revision DESC LIMIT 1) sample_review_evidence,
                 s.training_status source_training_status,
                 s.corpus_class
          FROM audio_samples a JOIN sources s ON s.source_id=a.source_id
        """
        now = registry.now()
        for row in connection.execute(query):
            result["row_count"] += 1
            result["referenced_duration_ms"] += row["duration_ms"]
            fingerprints.add(row["segment_fingerprint"])
            objects.add(row["clip_object_sha256"] or row["parent_object_sha256"])
            interval = (
                row["parent_object_sha256"],
                row["segment_start_ms"],
                row["segment_end_ms"],
            )
            accepted = (
                row["training_status"] == "accepted"
                and row["rights_status"] in {"owned", "licensed", "permitted"}
                and row["rights_training_allowed"] == 1
                and (row["rights_expires_at"] is None or row["rights_expires_at"] > now)
                and row["source_training_status"] == "accepted"
                and row["corpus_class"] == "accepted_corpus"
                and row["source_review_decision"] == "accept"
                and row["source_review_evidence"] is not None
                and row["sample_review_decision"] == "accept"
                and row["sample_review_evidence"] is not None
            )
            if row["modality"] == "singing_aux":
                singing.append(interval)
                if accepted:
                    accepted_singing.append(interval)
                continue
            speech.append(interval)
            if row["training_status"] == "rejected":
                rejected.append(interval)
            elif not accepted:
                quarantine.append(interval)
            else:
                accepted_speech.append(interval)
                weight = 1_000_000
                for field in (
                    "quality_ppm",
                    "alignment_ppm",
                    "review_weight_ppm",
                    "source_tier_weight_ppm",
                ):
                    weight = (weight * row[field]) // 1_000_000
                weighted.append((*interval, weight))
    result["unique_sample_count"] = len(fingerprints)
    result["unique_object_count"] = len(objects)
    result["unique_physical_interval_ms"] = _union_ms(speech + singing)
    result["raw_speech_ms"] = _union_ms(speech)
    result["accepted_physical_speech_ms"] = _union_ms(accepted_speech)
    result["effective_speech_ms"] = _weighted_union_ms(weighted)
    result["raw_singing_ms"] = _union_ms(singing)
    result["accepted_auxiliary_singing_ms"] = _union_ms(accepted_singing)
    result["quarantine_ms"] = _union_ms(quarantine)
    result["rejected_ms"] = _union_ms(rejected)
    return result
