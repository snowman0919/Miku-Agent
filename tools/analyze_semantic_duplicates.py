#!/usr/bin/env python3
"""Measure semantic duplicate clusters with a revision-pinned sentence encoder."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sqlite3
from pathlib import Path

from analyze_corpus_duplicates import Components


MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
MODEL_LICENSE = "mit"


def load_texts(registry: Path) -> dict[str, list[tuple[str, str]]]:
    with sqlite3.connect(registry) as connection:
        speech = connection.execute("""
            SELECT sample_id, normalized_text FROM text_samples
            WHERE corpus='miku-speech-script' AND training_status='quarantine'
            ORDER BY sample_id
        """).fetchall()
        duplex = []
        for timeline_id, events_json in connection.execute("""
            SELECT timeline_id, events_json FROM duplex_timelines
            WHERE training_status='accepted' ORDER BY timeline_id
        """):
            events = json.loads(events_json)
            duplex.append((timeline_id, " ".join(str(event.get("text", ""))
                                                  for event in events if event.get("text"))))
        korean = connection.execute("""
            SELECT sample_id, normalized_text FROM text_samples
            WHERE corpus='korean_foundation' AND training_status='accepted'
            ORDER BY sample_id
        """).fetchall()
    result = {"speech_render_candidate": speech, "accepted_duplex": duplex}
    if korean:
        result["accepted_korean_foundation"] = korean
    return result


def duplex_policy_text(scenario: str, events_json: str, expected: str, forbidden: str) -> str:
    events = json.loads(events_json)
    sequence = " ".join(f'{event.get("actor", "")} {event.get("type", "")} {event.get("text", "")}'
                        for event in events)
    return f"{scenario} {expected} {forbidden} {sequence}"


def load_cross_split(registry: Path) -> dict[str, tuple[list[tuple[str, str]], list[tuple[str, str]]]]:
    with sqlite3.connect(registry) as connection:
        speech = connection.execute("""
            SELECT sample_id, normalized_text FROM text_samples
            WHERE corpus='miku-speech-script' AND training_status='quarantine' ORDER BY sample_id
        """).fetchall()
        tts_eval = connection.execute("""
            SELECT sample_id, normalized_text FROM text_samples
            WHERE corpus='tts-eval-script' AND training_status='holdout' ORDER BY sample_id
        """).fetchall()
        duplex = [(row[0], duplex_policy_text(*row[1:])) for row in connection.execute("""
            SELECT timeline_id, scenario, events_json, expected_behavior, forbidden_behavior
            FROM duplex_timelines WHERE training_status='accepted' ORDER BY timeline_id
        """)]
        duplex_eval = [(row[0], duplex_policy_text(*row[1:])) for row in connection.execute("""
            SELECT timeline_id, scenario, events_json, expected_behavior, forbidden_behavior
            FROM duplex_timelines WHERE training_status='holdout' ORDER BY timeline_id
        """)]
        agentic = []
        for identity, task_type, events_json in connection.execute("""
            SELECT trajectory_id, task_type, events_json FROM agentic_trajectories
            WHERE training_status='accepted' ORDER BY trajectory_id
        """):
            events = json.loads(events_json)
            agentic.append((identity, f'{task_type} ' + " ".join(
                f'{event.get("tool", "")} {event.get("kind", "")} {event.get("summary", "")}'
                for event in events)))
        agentic_eval = connection.execute("""
            SELECT sample_id, normalized_text FROM text_samples
            WHERE corpus='agentic-eval-task' AND training_status='holdout' ORDER BY sample_id
        """).fetchall()
    return {
        "speech_candidate_to_tts_eval": (speech, tts_eval),
        "accepted_duplex_to_duplex_eval": (duplex, duplex_eval),
        "accepted_agentic_to_agentic_eval": (agentic, agentic_eval),
    }


def file_manifest(root: Path) -> dict[str, object]:
    files, total = {}, 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        body = path.read_bytes()
        files[str(path.relative_to(root))] = hashlib.sha256(body).hexdigest()
        total += len(body)
    return {"files": files, "total_bytes": total}


def semantic_clusters(embeddings, threshold_ppm: int, batch_size: int) -> dict[str, object]:
    import torch

    count = embeddings.shape[0]
    components = Components(count)
    matched_pairs = 0
    nearest = []
    threshold = threshold_ppm / 1_000_000
    columns = torch.arange(count, device=embeddings.device)
    for start in range(0, count, batch_size):
        end = min(count, start + batch_size)
        similarities = embeddings[start:end] @ embeddings.T
        rows = torch.arange(start, end, device=embeddings.device)
        similarities[torch.arange(end - start, device=embeddings.device), rows] = -1
        nearest.extend(similarities.max(dim=1).values.cpu().tolist())
        similarities.masked_fill_(columns[None, :] <= rows[:, None], -1)
        pairs = torch.nonzero(similarities >= threshold, as_tuple=False).cpu().tolist()
        matched_pairs += len(pairs)
        for left, right in pairs:
            components.union(start + left, right)
    valid_nearest = sorted(value for value in nearest if value >= 0)

    def percentile(fraction: float) -> int | None:
        if not valid_nearest:
            return None
        return round(valid_nearest[round((len(valid_nearest) - 1) * fraction)] * 1_000_000)

    return {
        **components.summary(),
        "matched_pairs": matched_pairs,
        "cosine_threshold_ppm": threshold_ppm,
        "nearest_neighbor_cosine_ppm": {
            "p50": percentile(.50), "p90": percentile(.90), "p95": percentile(.95),
            "p99": percentile(.99), "max": percentile(1),
        },
    }


def cross_similarity(left, right, left_ids: list[str], right_ids: list[str],
                     threshold_ppm: int, batch_size: int) -> dict[str, object]:
    import torch

    components = Components(len(left_ids) + len(right_ids))
    matched_left, matched_right = set(), set()
    matched_pairs = 0
    maximum = (-1.0, 0, 0)
    threshold = threshold_ppm / 1_000_000
    for start in range(0, len(left_ids), batch_size):
        end = min(len(left_ids), start + batch_size)
        similarities = left[start:end] @ right.T
        value, flat_index = similarities.flatten().max(dim=0)
        if value.item() > maximum[0]:
            local = flat_index.item() // len(right_ids)
            maximum = (value.item(), start + local, flat_index.item() % len(right_ids))
        pairs = torch.nonzero(similarities >= threshold, as_tuple=False).cpu().tolist()
        matched_pairs += len(pairs)
        for local_left, right_index in pairs:
            left_index = start + local_left
            matched_left.add(left_index)
            matched_right.add(right_index)
            components.union(left_index, len(left_ids) + right_index)
    return {
        "cosine_threshold_ppm": threshold_ppm,
        "matched_pairs": matched_pairs,
        "candidate_rows_with_match": len(matched_left),
        "evaluation_rows_with_match": len(matched_right),
        "largest_cross_component_rows": components.summary()["largest_cluster_rows"] if matched_pairs else 0,
        "maximum_cosine_ppm": round(maximum[0] * 1_000_000),
        "strongest_pair": {"candidate_id": left_ids[maximum[1]], "evaluation_id": right_ids[maximum[2]]},
    }


def analyze(registry: Path, cache: Path, thresholds_ppm: list[int], encode_batch_size: int,
            compare_batch_size: int) -> dict[str, object]:
    import sentence_transformers
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    if (not registry.is_file() or not thresholds_ppm
            or any(not 0 < value <= 1_000_000 for value in thresholds_ppm)):
        raise ValueError("registry must exist and thresholds must be 1..1000000 ppm")
    snapshot = Path(snapshot_download(
        MODEL_ID, revision=MODEL_REVISION, cache_dir=cache,
        ignore_patterns=["*.bin", "onnx/*", "openvino/*", ".eval_results/*"],
    ))
    model = SentenceTransformer(str(snapshot), device="cuda", trust_remote_code=False)
    corpora = {}
    for name, rows in load_texts(registry).items():
        _, texts = zip(*rows)
        input_digest = hashlib.sha256("".join(f"{identity}\0{text}\n" for identity, text in rows).encode()).hexdigest()
        embeddings = model.encode([f"query: {text}" for text in texts], batch_size=encode_batch_size,
                                  normalize_embeddings=True, convert_to_tensor=True,
                                  show_progress_bar=False)
        corpora[name] = {
            "rows": len(rows), "input_rows_sha256": input_digest,
            "threshold_results": {
                str(value): semantic_clusters(embeddings, value, compare_batch_size)
                for value in thresholds_ppm
            },
        }
        del embeddings
        torch.cuda.empty_cache()
    cross_split = {}
    for name, (left_rows, right_rows) in load_cross_split(registry).items():
        left_ids, left_texts = zip(*left_rows)
        right_ids, right_texts = zip(*right_rows)
        left_embeddings = model.encode([f"query: {text}" for text in left_texts], batch_size=encode_batch_size,
                                       normalize_embeddings=True, convert_to_tensor=True,
                                       show_progress_bar=False)
        right_embeddings = model.encode([f"query: {text}" for text in right_texts], batch_size=encode_batch_size,
                                        normalize_embeddings=True, convert_to_tensor=True,
                                        show_progress_bar=False)
        cross_split[name] = {
            "candidate_rows": len(left_rows), "evaluation_rows": len(right_rows),
            "candidate_rows_sha256": hashlib.sha256("".join(
                f"{identity}\0{text}\n" for identity, text in left_rows).encode()).hexdigest(),
            "evaluation_rows_sha256": hashlib.sha256("".join(
                f"{identity}\0{text}\n" for identity, text in right_rows).encode()).hexdigest(),
            "threshold_results": {
                str(value): cross_similarity(left_embeddings, right_embeddings, list(left_ids),
                                             list(right_ids), value, compare_batch_size)
                for value in thresholds_ppm
            },
        }
        del left_embeddings, right_embeddings
        torch.cuda.empty_cache()
    return {
        "schema_version": 1,
        "algorithm": {
            "input_prefix": "query: ", "similarity": "cosine",
            "cluster_rule": "connected components of all pairs at or above threshold",
            "comparison": "exact chunked all-pairs matrix multiplication",
            "cross_split_duplex": "scenario, expected/forbidden behavior, and actor/type/text event sequence",
        },
        "model": {
            "id": MODEL_ID, "revision": MODEL_REVISION, "license": MODEL_LICENSE,
            "max_seq_length": model.max_seq_length,
            "snapshot_manifest": file_manifest(snapshot),
        },
        "runtime": {
            "python": platform.python_version(), "torch": torch.__version__,
            "cuda_runtime": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
            "transformers": transformers.__version__,
            "sentence_transformers": sentence_transformers.__version__,
        },
        "corpora": corpora,
        "cross_split": cross_split,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold-ppm", type=int, nargs="+", default=[980_000, 990_000])
    parser.add_argument("--encode-batch-size", type=int, default=256)
    parser.add_argument("--compare-batch-size", type=int, default=512)
    args = parser.parse_args()
    report = analyze(args.registry, args.cache, args.threshold_ppm,
                     args.encode_batch_size, args.compare_batch_size)
    body = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(args.output)
    print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
