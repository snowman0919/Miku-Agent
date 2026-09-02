#!/usr/bin/env python3
"""Audit a specific Manifest Format 2 annotated release tag."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass

try:
    from .release_common import (
        EXPECTED_V000_COMMIT,
        EXPECTED_V000_TAG_OBJECT,
        ROOT,
        assert_no_prohibited_commit_fields,
        blob_sha256,
        git,
        git_text,
        validate_document_hashes,
        validate_definition_binding,
        v000_local_identity,
        yaml_at_ref,
    )
except ImportError:  # Direct script execution.
    from release_common import (
    EXPECTED_V000_COMMIT,
    EXPECTED_V000_TAG_OBJECT,
    ROOT,
    assert_no_prohibited_commit_fields,
    blob_sha256,
    git,
    git_text,
    validate_document_hashes,
    validate_definition_binding,
    v000_local_identity,
    yaml_at_ref,
    )


@dataclass
class Check:
    name: str
    detail: str


def remote_tag_refs(tag: str) -> dict[str, str]:
    result = git("ls-remote", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, ref = line.split("\t", 1)
        refs[ref] = sha
    return refs


def run_all(tag: str) -> list[Check]:
    checks: list[Check] = []
    if tag != "v0.0.1":
        raise AssertionError("this release evidence contract expects TAG=v0.0.1")
    if git("show-ref", "--verify", "--quiet", f"refs/tags/{tag}", check=False).returncode != 0:
        raise AssertionError(f"local tag does not exist: {tag}")
    if git_text("cat-file", "-t", tag) != "tag":
        raise AssertionError(f"{tag} is not an annotated tag")
    tag_object = git_text("rev-parse", tag)
    release_commit = git_text("rev-parse", f"{tag}^{{commit}}")
    checks.append(Check("annotated tag", f"{tag_object} -> {release_commit}"))

    refs = remote_tag_refs(tag)
    if refs.get(f"refs/tags/{tag}") != tag_object or refs.get(f"refs/tags/{tag}^{{}}") != release_commit:
        raise AssertionError("local and remote tag object/peeled commit differ")
    checks.append(Check("remote tag equality", f"{tag_object} -> {release_commit}"))

    manifest = yaml_at_ref(release_commit, "release-manifest.yaml")
    assert_no_prohibited_commit_fields(manifest)
    identity = manifest.get("release_identity", {})
    if identity.get("manifest_format") != 2 or identity.get("tag") != tag:
        raise AssertionError("tagged manifest release identity mismatch")
    definition = identity.get("definition_commit")
    mode = validate_definition_binding(definition, release_commit, allow_preparation=False)
    checks.append(Check("definition binding", f"{definition}; {mode}"))

    validate_document_hashes(definition, manifest["document_hashes"])
    checks.append(Check("definition document hashes", f"{len(manifest['document_hashes'])} Git object hashes"))

    ledger = yaml_at_ref(release_commit, "spec/release-history.yaml")
    v001 = next((item for item in ledger["releases"] if item["version"] == "0.0.1"), None)
    if not v001 or v001.get("status") != "released" or v001.get("definition_commit") != definition:
        raise AssertionError("tagged release history does not bind V0.0.1 definition commit")
    tag_type, old_object, old_peeled = v000_local_identity()
    if (tag_type, old_object, old_peeled) != ("tag", EXPECTED_V000_TAG_OBJECT, EXPECTED_V000_COMMIT):
        raise AssertionError("V0.0.0 immutable baseline changed")
    checks.append(Check("V0.0.0 historical integrity", f"{old_object} -> {old_peeled}"))

    tag_message = git_text("for-each-ref", "--format=%(contents)", f"refs/tags/{tag}")
    tagged_manifest_hash = blob_sha256(release_commit, "release-manifest.yaml")
    report_path = manifest["validation_report"]["path"]
    tagged_report_hash = blob_sha256(release_commit, report_path)
    required_message_values = [definition, tagged_manifest_hash, tagged_report_hash, "Offline validation: PASS", "Pre-tag remote policy audit: PASS"]
    missing = [value for value in required_message_values if value not in tag_message]
    if missing:
        raise AssertionError(f"annotated tag message is missing release evidence: {missing}")
    checks.append(Check("tag message evidence", "definition, manifest/report hashes, validation and remote audit"))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    try:
        checks = run_all(args.tag)
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for check in checks:
        print(f"PASS: {check.name} - {check.detail}")
    print(f"PASS: {len(checks)} release audit checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
