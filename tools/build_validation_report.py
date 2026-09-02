#!/usr/bin/env python3
"""Build the current V0.1.0 release-preparation validation report."""

from __future__ import annotations

import platform
import subprocess
import sys

try:
    from .audit_remote import run_all as run_remote_audit
    from .release_common import ROOT, git_text, load_yaml
    from .validate_repo import run_all as run_offline_validation
except ImportError:
    from audit_remote import run_all as run_remote_audit
    from release_common import ROOT, git_text, load_yaml
    from validate_repo import run_all as run_offline_validation


RUN_IDS = (
    "47c125f9-3dfd-4e33-9762-85558dbfa884",
    "589f60d6-541b-4c6c-a290-3523d1d41655",
    "89c19075-441b-471b-8480-88ff83857fd2",
)


def first_line(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else "unavailable"


def main() -> int:
    manifest = load_yaml(ROOT / "release-manifest.yaml")
    if manifest.get("product_version") != "0.1.0":
        print("FAIL: finalize the V0.1.0 Manifest Format 2 evidence first")
        return 1
    try:
        offline = run_offline_validation()
        remote = run_remote_audit()
    except Exception as exc:
        print(f"FAIL: validation or remote audit failed: {exc}")
        return 1
    pytest = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    pytest_output = " ".join(line.strip() for line in (pytest.stdout + pytest.stderr).splitlines() if line.strip())
    if pytest.returncode:
        print(pytest_output)
        return pytest.returncode
    run_results = []
    for run_id in RUN_IDS:
        result = subprocess.run(
            [sys.executable, "tools/v0_1_0/validate_run.py", f"runs/v0.1.0/{run_id}"],
            cwd=ROOT, text=True, capture_output=True,
        )
        if result.returncode:
            print(result.stdout + result.stderr)
            return result.returncode
        run_results.append(f"- `{run_id}`: PASS")
    offline_lines = "\n".join(f"- PASS: {item.name} — {item.detail}" for item in offline)
    remote_lines = "\n".join(f"- PASS: {item.name} — {item.detail}" for item in remote)
    definition = manifest["release_identity"]["definition_commit"]
    report = f"""# V0.1.0 Validation Report

## Result

CONDITIONAL release evidence: PASS

## Environment

- OS: {platform.platform()}
- Python: {platform.python_version()}
- Git: {first_line(["git", "--version"])}
- Definition commit: `{definition}`
- Release preparation HEAD: `{git_text("rev-parse", "HEAD")}`
- Previous release: annotated `v0.0.1`

## Manifest Format 2

- Release tag declared: `v0.1.0`
- Definition commit is the immediate parent input to Commit B.
- Document hashes resolve against Git objects at the definition commit.
- No self-referential release commit field exists.

## Offline validation

- `make validate`: PASS
- Pytest: PASS — {pytest_output}
- Secret scan: PASS
- Forbidden checkpoint/audio/cache policy: PASS

{offline_lines}

## Run evidence validation

{chr(10).join(run_results)}

The R0, failed R2 mitigation, and successful experimental R3 evidence bundles
all have canonical UUID bindings, checkpoint hashes, inventory, metrics,
classification, command logs, and artifact separation.

## Pre-tag remote policy audit

{remote_lines}

The `v0.1.0` tag is intentionally absent during preparation. Post-tag local/remote
object equality is checked separately by `make audit-release TAG=v0.1.0` after push.

## Feasibility decision

- Classification: CONDITIONAL
- Official FP32: load/general PASS; function-calling CUDA OOM; RTF 49.74.
- Experimental BF16: general/function channel PASS; RTF 2.3915.
- Interactive/TTFA/interruption/soak: blocked by pinned 80 GB VRAM and container prerequisites.
- No unmeasured item is reported as PASS.

## Scope and safety

- No fine-tuning, Korean adaptation, persona training, or voice data collection occurred.
- No model weight, generated WAV, raw telemetry, token, or private key is tracked.
- No host driver/kernel/runtime was changed.
- V0.0.0 and V0.0.1 tag objects remain unchanged.
"""
    output = ROOT / manifest["validation_report"]["path"]
    output.write_text(report, encoding="utf-8", newline="\n")
    print(pytest_output)
    print(f"PASS: wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
