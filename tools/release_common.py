"""Shared local Git primitives for release evidence validation and audits."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REPOSITORY = "snowman0919/Miku-Agent"
EXPECTED_V000_TAG_OBJECT = "d1e97d732498f67b848264819e6316954a6ec52b"
EXPECTED_V000_COMMIT = "08ea6c6dc06e0a1a3a2a71fc8daa704b35e368d4"
EXPECTED_V001_TAG_OBJECT = "602f01eed26e0b343ae5028cbc42f5e8c265c67f"
EXPECTED_V001_COMMIT = "a9d40ac385c8a9fe342558f0925c20d6d1711701"
EXPECTED_V001_DEFINITION = "6a7249c14539521a2b2d614b081134e6d40dd989"
PROHIBITED_COMMIT_FIELDS = {
    "repository_commit", "release_commit", "tag_target_commit", "self_commit", "head_commit",
}


def run(command: list[str], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=cwd, check=check)


def git_text(*args: str, cwd: Path = ROOT) -> str:
    return git(*args, cwd=cwd).stdout.strip()


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def commit_exists(commit: str, *, root: Path = ROOT) -> bool:
    result = git("cat-file", "-e", f"{commit}^{{commit}}", cwd=root, check=False)
    return result.returncode == 0


def is_ancestor(ancestor: str, descendant: str = "HEAD", *, root: Path = ROOT) -> bool:
    result = git("merge-base", "--is-ancestor", ancestor, descendant, cwd=root, check=False)
    return result.returncode == 0


def blob_bytes(commit: str, path: str, *, root: Path = ROOT) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=root, capture_output=True, check=True,
    )
    return result.stdout


def blob_sha256(commit: str, path: str, *, root: Path = ROOT) -> str:
    return hashlib.sha256(blob_bytes(commit, path, root=root)).hexdigest()


def validate_document_hashes(
    definition_commit: str,
    document_hashes: dict[str, str],
    *,
    root: Path = ROOT,
) -> None:
    for relative, expected in document_hashes.items():
        try:
            actual = blob_sha256(definition_commit, relative, root=root)
        except subprocess.CalledProcessError as exc:
            raise AssertionError(f"definition commit does not contain hashed document: {relative}") from exc
        if actual != expected:
            raise AssertionError(f"definition-commit document hash mismatch: {relative}")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def yaml_at_ref(ref: str, path: str, *, root: Path = ROOT) -> Any:
    return yaml.safe_load(blob_bytes(ref, path, root=root).decode("utf-8"))


def validate_definition_binding(
    definition_commit: str,
    release_ref: str = "HEAD",
    *,
    root: Path = ROOT,
    allow_preparation: bool = True,
) -> str:
    if not commit_exists(definition_commit, root=root):
        raise AssertionError(f"definition_commit is not a commit object: {definition_commit}")
    release_commit = git_text("rev-parse", f"{release_ref}^{{commit}}", cwd=root)
    if not is_ancestor(definition_commit, release_commit, root=root):
        raise AssertionError("definition_commit is not an ancestor of the release commit")
    if allow_preparation and definition_commit == release_commit:
        return "release-preparation"
    parent = git("rev-parse", f"{release_commit}^", cwd=root, check=False)
    if parent.returncode != 0 or parent.stdout.strip() != definition_commit:
        actual = parent.stdout.strip() or "no-parent"
        raise AssertionError(
            f"definition_commit must equal release commit parent: expected {definition_commit}, actual {actual}"
        )
    return "release-commit"


def assert_no_prohibited_commit_fields(value: Any, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in PROHIBITED_COMMIT_FIELDS:
                raise AssertionError(f"prohibited self-referential field at {path}.{key}")
            assert_no_prohibited_commit_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            assert_no_prohibited_commit_fields(nested, f"{path}[{index}]")


def v000_local_identity(*, root: Path = ROOT) -> tuple[str, str, str]:
    tag_type = git_text("cat-file", "-t", "v0.0.0", cwd=root)
    tag_object = git_text("rev-parse", "v0.0.0", cwd=root)
    peeled = git_text("rev-parse", "v0.0.0^{commit}", cwd=root)
    return tag_type, tag_object, peeled


def validate_v000_history_entry(entry: dict[str, Any], *, root: Path = ROOT) -> tuple[str, str]:
    tag_type, tag_object, peeled = v000_local_identity(root=root)
    if (tag_type, tag_object, peeled) != ("tag", EXPECTED_V000_TAG_OBJECT, EXPECTED_V000_COMMIT):
        raise AssertionError("V0.0.0 local tag identity differs from immutable baseline")
    if entry.get("tag_object") != tag_object or entry.get("peeled_commit") != peeled:
        raise AssertionError("release history V0.0.0 binding differs from local tag")
    return tag_object, peeled


def origin_repository(*, root: Path = ROOT) -> str:
    url = git_text("remote", "get-url", "origin", cwd=root)
    normalized = url.removesuffix(".git")
    if normalized.startswith("git@github.com:"):
        return normalized.split(":", 1)[1]
    marker = "github.com/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]
    return normalized
