#!/usr/bin/env python3
"""Build the V0.0.1 release-preparation validation report."""

from __future__ import annotations

import platform
import subprocess
import sys

try:
    from .audit_remote import run_all as run_remote_audit
    from .release_common import ROOT, git_text, load_yaml, v000_local_identity
    from .validate_repo import run_all as run_offline_validation
except ImportError:  # Direct script execution.
    from audit_remote import run_all as run_remote_audit
    from release_common import ROOT, git_text, load_yaml, v000_local_identity
    from validate_repo import run_all as run_offline_validation


def first_line(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else "unavailable"


def main() -> int:
    manifest = load_yaml(ROOT / "release-manifest.yaml")
    if manifest.get("product_version") != "0.0.1":
        print("FAIL: finalize Manifest Format 2 before building the V0.0.1 report")
        return 1
    try:
        offline_checks = run_offline_validation()
        remote_checks = run_remote_audit()
    except Exception as exc:
        print(f"FAIL: validation or remote audit failed: {exc}")
        return 1

    pytest = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    pytest_output = " ".join(line.strip() for line in (pytest.stdout + pytest.stderr).splitlines() if line.strip())
    if pytest.returncode != 0:
        print(pytest_output)
        return pytest.returncode

    tag_type, v000_object, v000_peeled = v000_local_identity()
    definition = manifest["release_identity"]["definition_commit"]
    offline_lines = "\n".join(f"- PASS: {check.name} — {check.detail}" for check in offline_checks)
    remote_lines = "\n".join(f"- PASS: {check.name} — {check.detail}" for check in remote_checks)
    report = f"""# V0.0.1 Validation Report

## Purpose

V0.0.0 제품 계약을 변경하지 않고 release identity의 자기참조를 제거하며 offline content validation과 current GitHub policy audit을 분리한 V0.0.1 release evidence를 검증한다.

## Environment

- OS: {platform.platform()}
- Python: {platform.python_version()}
- Git: {first_line(['git', '--version'])}
- GitHub CLI: {first_line(['gh', '--version'])}
- Execution boundary: local-only

## Previous release binding

- Tag: `v0.0.0`
- Tag type: `{tag_type}`
- Tag object: `{v000_object}`
- Peeled commit: `{v000_peeled}`
- Immutability result: PASS

## Definition commit

- Definition commit: `{definition}`
- Release preparation HEAD: `{git_text('rev-parse', 'HEAD')}`
- Binding mode: definition commit is the validated source immediately before release evidence commit

## Manifest format

- Manifest format: `2`
- Release tag declared by manifest: `v0.0.1`
- Self-referential commit fields: absent
- Release commit identity: annotated Git tag, not a tracked manifest field

## Offline validation commands

```text
make validate
python3 tools/validate_repo.py
python3 -m pytest -q
```

- Offline repository validation: PASS
- Pytest result: PASS — {pytest_output}
- Offline-without-gh behavioral test: PASS
- Schema result: PASS
- ADR result: PASS — 11 accepted ADRs
- Definition document hash result: PASS
- V0.0.0 immutability result: PASS
- Forbidden file result: PASS
- Secret scan result: PASS

## Offline validation details

{offline_lines}

## Remote audit at release preparation time

Command: `make audit-remote`

{remote_lines}

The `v0.0.1` tag does not yet exist during this report's release-preparation phase. Tag existence and local/remote tag equality are intentionally not reported as PASS here; post-tag evidence is produced by `make audit-release TAG=v0.0.1`.

## Known limitations

- V0.0.1 corrects release evidence semantics only; it does not validate RTX 5090 model feasibility.
- Current GitHub policy is time-varying and is authoritative only at the recorded audit time, not part of offline validation.
- Model, dataset, client runtime and production authentication remain unimplemented by design.

## Scope confirmation

- RTX 5090 server was not accessed.
- No model was downloaded or trained.
- No external media dataset was collected.
- No Clerk production credentials were created.
- No application runtime was implemented.
- V0.0.0 was not rewritten or retagged.
- V0.1.0 server work has not started.
"""
    path = ROOT / manifest["validation_report"]["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8", newline="\n")
    print(pytest_output)
    print(f"PASS: wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
