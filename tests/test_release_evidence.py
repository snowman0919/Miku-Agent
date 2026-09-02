from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.release_common import (
    EXPECTED_V000_COMMIT,
    EXPECTED_V000_TAG_OBJECT,
    ROOT,
    validate_definition_binding,
    validate_document_hashes,
    validate_v000_history_entry,
)
from tools.validate_repo import load_data, validate_instance


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


def commit_file(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    run_git(repo, "add", path)
    run_git(repo, "commit", "-m", message)
    return run_git(repo, "rev-parse", "HEAD")


def init_repo(repo: Path) -> str:
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Release Test")
    run_git(repo, "config", "user.email", "release@example.invalid")
    return commit_file(repo, "docs/binding.md", "definition\n", "definition")


def test_manifest_schema_rejects_self_referential_commit_field():
    path = ROOT / "examples" / "invalid" / "release-manifest.self-referential-commit.yaml"
    errors = validate_instance("release-manifest", load_data(path))
    assert errors
    assert "Additional properties" in " | ".join(errors)


def test_definition_commit_must_exist():
    with pytest.raises(AssertionError, match="not a commit object"):
        validate_definition_binding("0" * 40)


def test_definition_commit_must_be_release_ancestor(tmp_path: Path):
    repo = tmp_path / "repo"
    definition = init_repo(repo)
    commit_file(repo, "main.txt", "main\n", "main release")
    run_git(repo, "switch", "--orphan", "unrelated")
    for tracked in run_git(repo, "ls-files").splitlines():
        path = repo / tracked
        if path.exists():
            path.unlink()
    unrelated = commit_file(repo, "unrelated.txt", "unrelated\n", "unrelated")
    run_git(repo, "switch", "main")
    assert definition != unrelated
    with pytest.raises(AssertionError, match="not an ancestor"):
        validate_definition_binding(unrelated, root=repo)


def test_document_hashes_bind_definition_git_object_not_working_tree(tmp_path: Path):
    repo = tmp_path / "repo"
    definition = init_repo(repo)
    expected = hashlib.sha256(b"definition\n").hexdigest()
    commit_file(repo, "docs/binding.md", "changed after definition\n", "release evidence")
    validate_document_hashes(definition, {"docs/binding.md": expected}, root=repo)
    working_hash = hashlib.sha256((repo / "docs/binding.md").read_bytes()).hexdigest()
    assert working_hash != expected
    with pytest.raises(AssertionError, match="hash mismatch"):
        validate_document_hashes(definition, {"docs/binding.md": "0" * 64}, root=repo)


def test_v000_history_entry_must_match_actual_immutable_tag():
    valid = {"tag_object": EXPECTED_V000_TAG_OBJECT, "peeled_commit": EXPECTED_V000_COMMIT}
    assert validate_v000_history_entry(valid) == (EXPECTED_V000_TAG_OBJECT, EXPECTED_V000_COMMIT)
    with pytest.raises(AssertionError, match="differs"):
        validate_v000_history_entry({**valid, "peeled_commit": "0" * 40})


def test_offline_validator_passes_without_gh_on_path(tmp_path: Path):
    isolated_bin = tmp_path / "bin"
    isolated_bin.mkdir()
    git_path = shutil.which("git")
    assert git_path
    (isolated_bin / "git").symlink_to(git_path)
    environment = os.environ.copy()
    environment["PATH"] = str(isolated_bin)
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_repo.py")],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "offline checks" in result.stdout
