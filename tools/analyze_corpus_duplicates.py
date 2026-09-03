#!/usr/bin/env python3
"""Measure reproducible exact and lexical duplicate clusters in canonical corpora."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


PRIME = (1 << 61) - 1
TOKEN = re.compile(r"\w+", re.UNICODE)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def shingles(text: str, kind: str) -> set[int]:
    normalized = normalize(text)
    if kind == "character_5gram":
        units = re.sub(r"\s+", "", normalized)
        values = (units[i:i + 5] for i in range(max(1, len(units) - 4)))
    elif kind == "token_2gram":
        tokens = TOKEN.findall(normalized)
        values = ("\0".join(tokens[i:i + 2]) for i in range(max(1, len(tokens) - 1)))
    else:
        raise ValueError(f"unknown shingle kind: {kind}")
    return {int.from_bytes(hashlib.blake2b(value.encode(), digest_size=8).digest()) % PRIME for value in values}


def permutation_coefficients(count: int) -> list[tuple[int, int]]:
    coefficients = []
    for index in range(count):
        digest = hashlib.sha256(f"miku-minhash-v1:{index}".encode()).digest()
        coefficients.append((int.from_bytes(digest[:8], "big") % (PRIME - 1) + 1,
                             int.from_bytes(digest[8:16], "big") % PRIME))
    return coefficients


def minhash(features: set[int], coefficients: list[tuple[int, int]]) -> tuple[int, ...]:
    return tuple(min((a * value + b) % PRIME for value in features) for a, b in coefficients)


class Components:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[right] = left

    def summary(self) -> dict[str, int]:
        sizes = Counter(self.find(index) for index in range(len(self.parent)))
        duplicate_sizes = [size for size in sizes.values() if size > 1]
        return {
            "effective_unique_rows": len(sizes),
            "duplicate_clusters": len(duplicate_sizes),
            "rows_in_duplicate_clusters": sum(duplicate_sizes),
            "largest_cluster_rows": max(sizes.values(), default=0),
        }


def exact_clusters(texts: list[str]) -> dict[str, int]:
    counts = Counter(map(normalize, texts))
    duplicate_sizes = [size for size in counts.values() if size > 1]
    return {
        "effective_unique_rows": len(counts),
        "duplicate_clusters": len(duplicate_sizes),
        "rows_in_duplicate_clusters": sum(duplicate_sizes),
        "largest_cluster_rows": max(counts.values(), default=0),
    }


def lexical_clusters(texts: list[str], kind: str, threshold_ppm: int,
                     permutations: int, bands: int) -> dict[str, int]:
    if permutations <= 0 or bands <= 0 or permutations % bands:
        raise ValueError("permutations must be positive and divisible by bands")
    feature_sets = [shingles(text, kind) for text in texts]
    coefficients = permutation_coefficients(permutations)
    signatures = [minhash(features, coefficients) for features in feature_sets]
    rows_per_band = permutations // bands
    candidates: set[tuple[int, int]] = set()
    for band in range(bands):
        buckets: dict[tuple[int, ...], list[int]] = defaultdict(list)
        start = band * rows_per_band
        for index, signature in enumerate(signatures):
            buckets[signature[start:start + rows_per_band]].append(index)
        for bucket in buckets.values():
            if len(bucket) > 1:
                candidates.update(itertools.combinations(bucket, 2))
    components = Components(len(texts))
    matched_pairs = 0
    for left, right in candidates:
        common = len(feature_sets[left] & feature_sets[right])
        union = len(feature_sets[left] | feature_sets[right])
        if common * 1_000_000 >= threshold_ppm * union:
            components.union(left, right)
            matched_pairs += 1
    return {
        **components.summary(),
        "candidate_pairs": len(candidates),
        "matched_pairs": matched_pairs,
        "threshold_ppm": threshold_ppm,
        "minhash_permutations": permutations,
        "lsh_bands": bands,
    }


def group_summary(values: list[str]) -> dict[str, int]:
    counts = Counter(values)
    return {"groups": len(counts), "largest_group_rows": max(counts.values(), default=0)}


def corpus_analysis(rows: list[dict[str, str]], threshold_ppm: int,
                    permutations: int, bands: int) -> dict[str, object]:
    texts = [row["text"] for row in rows]
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode())
        digest.update(b"\n")
    return {
        "rows": len(rows),
        "input_rows_sha256": digest.hexdigest(),
        "normalized_exact": exact_clusters(texts),
        "character_5gram_jaccard": lexical_clusters(texts, "character_5gram", threshold_ppm,
                                                      permutations, bands),
        "token_2gram_jaccard": lexical_clusters(texts, "token_2gram", threshold_ppm,
                                                  permutations, bands),
        "template_family": group_summary([row["template_family"] for row in rows]),
        "generator_family": group_summary([row["generator_family"] for row in rows]),
        "generator_prompt_family": group_summary([row["generator_prompt_family"] for row in rows]),
        "lineage_family": group_summary([row["lineage_family"] for row in rows]),
        "semantic_embedding": {"status": "not_measured", "effective_unique_rows": None},
    }


def load_corpora(registry: Path) -> dict[str, list[dict[str, str]]]:
    with sqlite3.connect(registry) as connection:
        connection.row_factory = sqlite3.Row
        speech = []
        for row in connection.execute("""
            SELECT t.sample_id, t.normalized_text, t.provenance_json, s.derivative_family
            FROM text_samples t JOIN sources s USING(source_id)
            WHERE t.corpus='miku-speech-script' AND t.training_status='quarantine'
            ORDER BY t.sample_id
        """):
            provenance = json.loads(row["provenance_json"])
            speech.append({
                "id": row["sample_id"], "text": row["normalized_text"],
                "template_family": provenance["template_family"],
                "generator_family": provenance["generation_model"],
                "generator_prompt_family": provenance["generation_job_id"],
                "lineage_family": f'{row["derivative_family"]}:{provenance["bundle_object_sha256"]}',
            })
        duplex = []
        for row in connection.execute("""
            SELECT d.timeline_id, d.events_json, d.provenance_json, s.derivative_family
            FROM duplex_timelines d JOIN sources s USING(source_id)
            WHERE d.training_status='accepted'
            ORDER BY d.timeline_id
        """):
            events = json.loads(row["events_json"])
            provenance = json.loads(row["provenance_json"])
            duplex.append({
                "id": row["timeline_id"],
                "text": " ".join(str(event.get("text", "")) for event in events if event.get("text")),
                "template_family": provenance["template_family"],
                "generator_family": f'{provenance["generator"]}:{provenance["generator_sha256"]}',
                "generator_prompt_family": f'{provenance["generator"]}:{provenance["generator_sha256"]}',
                "lineage_family": row["derivative_family"],
            })
    return {"speech_render_candidate": speech, "accepted_duplex": duplex}


def analyze(registry: Path, threshold_ppm: int = 800_000,
            permutations: int = 64, bands: int = 16) -> dict[str, object]:
    if not registry.is_file() or not 0 < threshold_ppm <= 1_000_000:
        raise ValueError("registry must exist and threshold must be 1..1000000 ppm")
    return {
        "schema_version": 1,
        "algorithm": {
            "normalization": "Unicode NFKC, casefold, collapsed whitespace",
            "candidate_search": "deterministic MinHash LSH; candidates verified by exact Jaccard",
            "cluster_rule": "connected components of verified pairs",
            "duplex_text": "concatenated non-empty event text",
        },
        "corpora": {name: corpus_analysis(rows, threshold_ppm, permutations, bands)
                    for name, rows in load_corpora(registry).items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold-ppm", type=int, default=800_000)
    parser.add_argument("--permutations", type=int, default=64)
    parser.add_argument("--bands", type=int, default=16)
    args = parser.parse_args()
    report = analyze(args.registry, args.threshold_ppm, args.permutations, args.bands)
    body = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(args.output)
    print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
