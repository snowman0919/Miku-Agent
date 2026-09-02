#!/usr/bin/env python3
"""Audit current GitHub repository policy and remote refs; intentionally online."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

try:
    from .release_common import (
        EXPECTED_REPOSITORY,
        EXPECTED_V000_COMMIT,
        EXPECTED_V000_TAG_OBJECT,
        ROOT,
        git,
        git_text,
        is_ancestor,
        origin_repository,
        run,
        v000_local_identity,
    )
except ImportError:  # Direct script execution.
    from release_common import (
    EXPECTED_REPOSITORY,
    EXPECTED_V000_COMMIT,
    EXPECTED_V000_TAG_OBJECT,
    ROOT,
    git,
    git_text,
    is_ancestor,
    origin_repository,
    run,
    v000_local_identity,
    )


@dataclass
class Check:
    name: str
    detail: str


def remote_refs(*patterns: str) -> dict[str, str]:
    result = git("ls-remote", "origin", *patterns)
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, ref = line.split("\t", 1)
        refs[ref] = sha
    return refs


def run_all() -> list[Check]:
    checks: list[Check] = []
    actual_repository = origin_repository()
    if actual_repository != EXPECTED_REPOSITORY:
        raise AssertionError(f"origin identity is {actual_repository}, expected {EXPECTED_REPOSITORY}")
    checks.append(Check("origin identity", EXPECTED_REPOSITORY))

    view = run([
        "gh", "repo", "view", EXPECTED_REPOSITORY,
        "--json", "nameWithOwner,visibility,defaultBranchRef,hasWikiEnabled,url",
    ])
    policy = json.loads(view.stdout)
    if policy.get("nameWithOwner") != EXPECTED_REPOSITORY:
        raise AssertionError("GitHub repository identity mismatch")
    if str(policy.get("visibility", "")).upper() != "PRIVATE":
        raise AssertionError("repository is not PRIVATE")
    if policy.get("defaultBranchRef", {}).get("name") != "main":
        raise AssertionError("default branch is not main")
    if policy.get("hasWikiEnabled") is not False:
        raise AssertionError("GitHub Wiki is enabled")
    checks.append(Check("GitHub repository policy", "PRIVATE, main, Wiki disabled"))

    pages = run(["gh", "api", f"repos/{EXPECTED_REPOSITORY}/pages"], check=False)
    if pages.returncode == 0 or "HTTP 404" not in pages.stderr:
        raise AssertionError(f"GitHub Pages is enabled or unverifiable: {pages.stderr.strip()}")
    checks.append(Check("GitHub Pages policy", "absent (HTTP 404)"))

    actions = run([
        "gh", "run", "list", "--repo", EXPECTED_REPOSITORY,
        "--limit", "1", "--json", "databaseId,status,workflowName",
    ])
    if json.loads(actions.stdout):
        raise AssertionError("GitHub Actions has a run in V0.0.x")
    if (ROOT / ".github" / "workflows").exists():
        raise AssertionError("tracked workflow directory exists in V0.0.x")
    checks.append(Check("GitHub Actions policy", "no workflow directory and no runs"))

    refs = remote_refs(
        "refs/heads/main", "refs/tags/v0.0.0", "refs/tags/v0.0.0^{}",
        "refs/tags/v0.0.1", "refs/tags/v0.0.1^{}",
    )
    local_type, local_object, local_peeled = v000_local_identity()
    if local_type != "tag" or local_object != EXPECTED_V000_TAG_OBJECT or local_peeled != EXPECTED_V000_COMMIT:
        raise AssertionError("local V0.0.0 identity changed")
    if refs.get("refs/tags/v0.0.0") != local_object or refs.get("refs/tags/v0.0.0^{}") != local_peeled:
        raise AssertionError("remote V0.0.0 differs from immutable local baseline")
    checks.append(Check("V0.0.0 remote integrity", f"{local_object} -> {local_peeled}"))

    remote_main = refs.get("refs/heads/main")
    if not remote_main:
        raise AssertionError("remote main is missing")
    if not is_ancestor(remote_main, "HEAD"):
        raise AssertionError("remote main is not reachable from local HEAD")
    checks.append(Check("remote main reachability", remote_main))

    local_v001 = git("show-ref", "--verify", "--quiet", "refs/tags/v0.0.1", check=False)
    if local_v001.returncode == 0:
        if git_text("cat-file", "-t", "v0.0.1") != "tag":
            raise AssertionError("local v0.0.1 is not annotated")
        local_object = git_text("rev-parse", "v0.0.1")
        local_peeled = git_text("rev-parse", "v0.0.1^{commit}")
        if refs.get("refs/tags/v0.0.1") != local_object or refs.get("refs/tags/v0.0.1^{}") != local_peeled:
            raise AssertionError("remote v0.0.1 differs from local annotated tag")
        checks.append(Check("V0.0.1 remote integrity", f"{local_object} -> {local_peeled}"))
    else:
        if "refs/tags/v0.0.1" in refs:
            raise AssertionError("remote v0.0.1 exists without a matching local tag")
        checks.append(Check("V0.0.1 tag state", "not created; permitted during release preparation"))
    return checks


def main() -> int:
    try:
        checks = run_all()
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for check in checks:
        print(f"PASS: {check.name} - {check.detail}")
    print(f"PASS: {len(checks)} remote audit checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
