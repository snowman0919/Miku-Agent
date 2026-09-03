#!/usr/bin/env python3
"""Count only parent-adjudicated, schema-valid subordinate jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode()


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("window path escapes its root")
    return path


def audit(root: Path, minimum: int = 30) -> dict[str, object]:
    window = json.loads((root / "accepted-window.json").read_text(encoding="utf-8"))
    accepted = []
    for item in window["accepted_jobs"]:
        if item.get("parent_decision") != "accepted" or not item.get("used_in"):
            raise ValueError(f"job lacks parent acceptance evidence: {item.get('job_id')}")
        receipt = json.loads(inside(root, item["receipt"]).read_text(encoding="utf-8"))
        output = json.loads(inside(root, item["output"]).read_text(encoding="utf-8"))
        output_sha256 = hashlib.sha256(canonical(output)).hexdigest()
        if (
            receipt["job_id"] != item["job_id"]
            or receipt["result"] != {"status": "completed", "validated": True}
            or output_sha256 != receipt.get("output_sha256")
            or output_sha256 != item.get("output_sha256")
        ):
            raise ValueError(f"job is not accepted evidence: {item['job_id']}")
        accepted.append(receipt)
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in (root / "receipts").glob("*.json")]
    providers = Counter(item["provider"] for item in accepted)
    models = Counter(item["model"] for item in accepted)
    roles = Counter(item["role"] for item in accepted)
    failures = Counter(
        item["failure"]["category"] for item in receipts if not item["result"]["validated"]
    )
    latencies = sorted(item["wall_ms"] for item in accepted)
    if len(accepted) < minimum or not providers["command_code"] or not providers["opencode"]:
        raise ValueError("accepted provider window is incomplete")
    return {
        "accepted_jobs": len(accepted), "attempted_jobs": len(receipts),
        "accepted_by_provider": dict(providers), "accepted_by_model": dict(models),
        "accepted_by_role": dict(roles),
        "command_code_to_opencode_ratio": providers["command_code"] / providers["opencode"],
        "first_pass_accepted": sum(item["attempts"] == 1 for item in accepted),
        "failure_categories": dict(failures),
        "latency_ms": {
            "mean": round(statistics.mean(latencies)),
            "p50": round(statistics.median(latencies)),
            "p95": latencies[min(len(latencies) - 1, round((len(latencies) - 1) * .95))],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("window", type=Path)
    parser.add_argument("--minimum", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(audit(args.window, args.minimum), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
