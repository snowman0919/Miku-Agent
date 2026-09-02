#!/usr/bin/env python3
"""Create immutable metadata for one V0.1.0 experiment run."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import uuid
from pathlib import Path

import yaml


SOURCE = {
    "repository": "snowman0919/Miku-Agent",
    "release_tag": "v0.0.1",
    "tag_object": "602f01eed26e0b343ae5028cbc42f5e8c265c67f",
    "release_commit": "a9d40ac385c8a9fe342558f0925c20d6d1711701",
    "definition_commit": "6a7249c14539521a2b2d614b081134e6d40dd989",
    "release_manifest_sha256": "e2b361e1b18c96dcfbfe31637da0d54fb89a6fb18973eda9c5bf6bf6aed42418",
    "validation_report_sha256": "fd65847722cb4aac411c3e3f71ed44d7ca8f7bfe795c3ef6baa5f58f6df17096",
    "product_lock_sha256": "bfa41bd956b08296d3883317b5e579c9afb13b7579e7004e5bc43afa4678ee18",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--experiment", default="R0")
    parser.add_argument("--dtype", default="official-reference")
    parser.add_argument("--model-modification", default="none")
    args = parser.parse_args()
    run_id = str(uuid.UUID(args.run_id))
    if run_id != args.run_id:
        parser.error("run ID must be a canonical UUID")
    repo = args.repo.resolve(strict=True)
    run = repo / "runs" / "v0.1.0" / run_id
    (run / "errors").mkdir(parents=True, exist_ok=False)
    (run / "notes").mkdir()

    actual = {
        "tag_object": git(repo, "rev-parse", "v0.0.1"),
        "release_commit": git(repo, "rev-parse", "v0.0.1^{commit}"),
        "release_manifest_sha256": sha256(repo / "release-manifest.yaml"),
        "validation_report_sha256": sha256(repo / "reports/v0.0.1-validation.md"),
        "product_lock_sha256": sha256(repo / "spec/product-lock.yaml"),
    }
    mismatches = {key: {"expected": SOURCE[key], "actual": value} for key, value in actual.items() if value != SOURCE[key]}
    if mismatches:
        raise SystemExit("SOURCE LOCK MISMATCH\n" + json.dumps(mismatches, indent=2))
    binding = {
        "run_id": run_id,
        "experiment": args.experiment,
        "source": SOURCE,
        "branch": "v0.1.0-reference-feasibility",
        "branch_start_commit": git(repo, "rev-parse", "v0.1.0-reference-feasibility^{commit}"),
        "model": {
            "repository": "nvidia/NVIDIA-NemotronLabs-VoiceChat-11B",
            "revision": "359ada7b1c60851e40ff08065f9b0340244f27e0",
        },
        "software": {
            "nvidia_speech_repository": "https://github.com/NVIDIA-NeMo/Speech.git",
            "nvidia_speech_branch": "nemotron-labs-voicechat",
            "nvidia_speech_commit": "097dfe9e2f55baf653b83035868bdc89849f1b47",
        },
        "configuration": {
            "dtype": args.dtype,
            "quantization": "none",
            "offload": "none",
            "model_modification": args.model_modification,
            "checkpoint_modification": "none",
        },
    }
    (run / "run-binding.yaml").write_text(yaml.safe_dump(binding, sort_keys=False), encoding="utf-8")
    model_source = {
        "schema_version": 1,
        "repository": binding["model"]["repository"],
        "immutable_revision": binding["model"]["revision"],
        "license": "NVIDIA Open Model Development Agreement 1.1",
        "gated": False,
        "checkpoint_artifact_id": "voicechat-11b-checkpoint-359ada7b",
        "nested_remote_code": {
            "repository": "nvidia/NVIDIA-Nemotron-Nano-9B-v2",
            "resolved_snapshot": "6533e8de2c68e4536bf7c411d7a3ce5734111476",
            "note": "Resolved from the Hugging Face cache after the official loader fetched floating remote code.",
        },
        "nvidia_speech": binding["software"],
    }
    (run / "model-source.json").write_text(json.dumps(model_source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_list = json.loads(subprocess.check_output(["uv", "pip", "list", "--python", sys.executable, "--format", "json"], text=True))
    experiment_dir = repo / "experiments" / "v0.1.0-rtx5090"
    software = {
        "schema_version": 1,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "flake_lock_sha256": sha256(experiment_dir / "flake.lock"),
        "uv_lock_sha256": sha256(experiment_dir / "uv.lock"),
        "packages": package_list,
    }
    (run / "software-lock.json").write_text(json.dumps(software, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run / "commands.log").write_text(
        "# Sanitized reproducibility commands; no credentials.\n"
        "nix flake check --no-build\n"
        "nix develop --command ./sync-env.sh\n"
        "nix develop --command .venv/bin/python ../../tools/v0_1_0/blackwell_smoke.py\n",
        encoding="utf-8",
    )
    print(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
