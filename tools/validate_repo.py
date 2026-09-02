#!/usr/bin/env python3
"""Repository-level validation for the V0.0.0 definition lock."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_TARGETS = {
    "product-lock": "product-lock.schema.json",
    "project-state": "project-state.schema.json",
    "release-manifest": "release-manifest.schema.json",
    "auth-access-grant": "auth-access-grant.schema.json",
    "character-profile": "character-profile.schema.json",
    "model-profile": "model-profile.schema.json",
    "dataset-source": "dataset-source.schema.json",
    "dataset-sample": "dataset-sample.schema.json",
    "memory-record": "memory-record.schema.json",
    "memory-commit": "memory-commit.schema.json",
    "agent-tool-call": "agent-tool-call.schema.json",
    "agent-event": "agent-event.schema.json",
    "scheduler-task": "scheduler-task.schema.json",
    "reaction-command": "reaction-command.schema.json",
}

INVALID_EXPECTATIONS = {
    "auth-access-grant.revoked-without-revoked-at.json": "revoked_at",
    "memory-record.inferred-without-evidence.json": "non-empty",
    "memory-record.stable-zero-observations.json": "minimum of 1",
    "dataset-sample.accepted-unknown-rights.json": "unknown",
    "scheduler-task.external-write-without-approval.json": "approval_policy",
    "agent-tool-call.model-authorization-token.json": "Additional properties",
    "model-profile.codec-not-frozen.json": "True was expected",
    "memory-record.missing-character.json": "character_id",
    "project-state.public-repository.yaml": "private",
}

FORBIDDEN_SUFFIXES = {
    ".key", ".pem", ".p12", ".wav", ".mp3", ".flac", ".ogg", ".mp4",
    ".mkv", ".vrm", ".pt", ".pth", ".ckpt", ".safetensors", ".onnx",
    ".engine", ".plan",
}
FORBIDDEN_PREFIXES = (
    ".env", "checkpoints/", "data/raw/", "data/processed/", "artifacts/",
    "secrets/", "credentials/", "models/cache/",
)
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}"),
    "generic live secret": re.compile(r"\b(?:sk_" r"live|sk-[A-Za-z0-9]{20,})"),
}

DECISION_EVIDENCE = {
    "0001": ("docs/persona-constitution.md", ("캐릭터별", "character_id", "miku")),
    "0002": ("docs/system-context.md", ("server", "local", "우선")),
    "0003": ("docs/authentication-and-access-control.md", ("Clerk", "backend access grant", "deny")),
    "0004": ("docs/memory-architecture.md", ("namespace", "version", "evidence")),
    "0005": ("docs/realtime-protocol.md", ("/ws/audio", "/ws/events", "WebRTC")),
    "0006": ("docs/client-experience.md", ("Flutter", "Unity", "UI code")),
    "0007": ("docs/codex-execution.md", ("Docker", "privileged", "Docker socket")),
    "0008": ("docs/model-boundaries.md", ("DuplexSTT", "DuplexEARTTS", "Codec")),
    "0009": ("docs/data-governance.md", ("private repository", "Git", "rights")),
    "0010": ("docs/animation-and-embodiment.md", ("procedural", "FSM", "per-frame bone")),
}


@dataclass
class Check:
    name: str
    status: str
    detail: str


def load_data(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def schema_for_name(name: str) -> dict[str, Any]:
    return load_data(ROOT / "schemas" / SCHEMA_TARGETS[name])


def validate_instance(name: str, instance: Any) -> list[str]:
    validator = Draft202012Validator(schema_for_name(name), format_checker=FormatChecker())
    return [error.message for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path))]


def candidate_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    return sorted(line for line in result.stdout.splitlines() if line)


def check_schemas() -> Check:
    schemas = sorted((ROOT / "schemas").glob("*.schema.json"))
    if {p.name for p in schemas} != set(SCHEMA_TARGETS.values()):
        raise AssertionError("schema inventory does not match the required contract set")
    for path in schemas:
        schema = load_data(path)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise AssertionError(f"{path.name}: not JSON Schema Draft 2020-12")
        Draft202012Validator.check_schema(schema)
    return Check("schema self-validation", "PASS", f"{len(schemas)} Draft 2020-12 schemas")


def check_examples() -> list[Check]:
    valid_paths = sorted((ROOT / "examples" / "valid").glob("*"))
    seen: set[str] = set()
    for path in valid_paths:
        name = path.name.rsplit(".", 1)[0]
        errors = validate_instance(name, load_data(path))
        if errors:
            raise AssertionError(f"valid example {path.name} failed: {errors}")
        seen.add(name)
    missing = set(SCHEMA_TARGETS) - seen
    if missing:
        raise AssertionError(f"schemas without a valid example: {sorted(missing)}")

    invalid_paths = sorted((ROOT / "examples" / "invalid").glob("*"))
    if {p.name for p in invalid_paths} != set(INVALID_EXPECTATIONS):
        raise AssertionError("invalid example inventory differs from expected architecture violations")
    for path in invalid_paths:
        name = path.name.split(".", 1)[0]
        errors = validate_instance(name, load_data(path))
        if not errors:
            raise AssertionError(f"invalid example unexpectedly passed: {path.name}")
        expected = INVALID_EXPECTATIONS[path.name]
        if expected not in " | ".join(errors):
            raise AssertionError(f"{path.name}: expected reason {expected!r}, got {errors}")
    return [
        Check("valid examples", "PASS", f"{len(valid_paths)} examples accepted"),
        Check("invalid examples", "PASS", f"{len(invalid_paths)} invariant violations rejected for expected reasons"),
    ]


def check_root_contracts() -> Check:
    targets = {
        "product-lock": ROOT / "spec" / "product-lock.yaml",
        "project-state": ROOT / "PROJECT_STATE.yaml",
        "release-manifest": ROOT / "release-manifest.yaml",
    }
    for name, path in targets.items():
        errors = validate_instance(name, load_data(path))
        if errors:
            raise AssertionError(f"{path.name}: {errors}")
    return Check("root machine contracts", "PASS", "product lock, project state, release manifest")


def check_product_invariants() -> Check:
    lock = load_data(ROOT / "spec" / "product-lock.yaml")
    assertions = {
        "private repository": lock["repository"]["visibility"] == "private",
        "local-only V0.0.0": lock["execution"]["local_only"] is True,
        "server starts V0.1.0": lock["execution"]["server_allowed_from"] == "0.1.0",
        "codec frozen": lock["model"]["codec_frozen"] is True,
        "WebRTC excluded": lock["transport"]["webrtc"] is False,
        "Clerk dual gate": lock["auth"]["signup_gate"] == "clerk_allowlist" and lock["auth"]["runtime_gate"] == "backend_access_grant",
        "user-character memory": lock["memory"]["namespace"] == "user_and_character",
        "Flutter and Unity": lock["clients"]["mobile"] == "flutter" and lock["clients"]["desktop"] == "unity",
        "Docker boundary": lock["codex"]["privileged"] is False and lock["codex"]["host_docker_socket"] is False,
    }
    failed = [name for name, ok in assertions.items() if not ok]
    if failed:
        raise AssertionError(f"failed locked invariants: {failed}")
    return Check("product invariants", "PASS", f"{len(assertions)} fixed architecture boundaries")


def check_adrs_and_traceability() -> Check:
    adr_paths = sorted((ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    if len(adr_paths) != 10:
        raise AssertionError(f"expected 10 ADRs, found {len(adr_paths)}")
    required_headings = ["Status", "Date", "Context", "Decision", "Alternatives Considered", "Consequences", "Security Impact", "Data Impact", "Validation", "Supersedes", "Superseded By"]
    trace = (ROOT / "docs" / "traceability-matrix.md").read_text(encoding="utf-8")
    for path in adr_paths:
        text = path.read_text(encoding="utf-8")
        if "## Status\naccepted" not in text:
            raise AssertionError(f"{path.name}: ADR is not accepted")
        for heading in required_headings:
            if f"## {heading}" not in text:
                raise AssertionError(f"{path.name}: missing {heading}")
        adr_id = f"ADR-{path.name[:4]}"
        if adr_id not in trace:
            raise AssertionError(f"{adr_id} missing from traceability matrix")
    rows = [line for line in trace.splitlines() if re.match(r"^\| D-[0-9]{3} ", line)]
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) != 9 or not cells[3] or not cells[4] or not cells[5] or not cells[6] or cells[8] != "accepted":
            raise AssertionError(f"incomplete traceability row: {row}")
    if len(rows) < 10:
        raise AssertionError("traceability matrix has fewer than 10 accepted decisions")
    return Check("ADR and traceability", "PASS", f"10 accepted ADRs, {len(rows)} decision links")


def check_decision_consistency() -> Check:
    """Require each accepted ADR and its source document to carry the same decision anchors."""
    for adr_number, (document, anchors) in DECISION_EVIDENCE.items():
        adr_path = next((ROOT / "docs" / "adr").glob(f"{adr_number}-*.md"), None)
        if adr_path is None:
            raise AssertionError(f"ADR-{adr_number} is missing")
        adr_text = adr_path.read_text(encoding="utf-8").lower()
        document_text = (ROOT / document).read_text(encoding="utf-8").lower()
        for anchor in anchors:
            lowered = anchor.lower()
            if lowered not in adr_text:
                raise AssertionError(f"ADR-{adr_number} lost decision anchor {anchor!r}")
            if lowered not in document_text:
                raise AssertionError(f"{document} conflicts with ADR-{adr_number}: missing {anchor!r}")
    return Check("ADR/document consistency", "PASS", "10 accepted decisions share required semantic anchors")


def check_manifest_integrity() -> Check:
    manifest = load_data(ROOT / "release-manifest.yaml")
    expected_adrs = [f"ADR-{number:04d}" for number in range(1, 11)]
    if manifest["accepted_adrs"] != expected_adrs:
        raise AssertionError("release manifest accepted ADR inventory is incomplete or out of order")
    for relative, expected in manifest["document_hashes"].items():
        path = ROOT / relative
        if not path.is_file():
            raise AssertionError(f"release manifest hashes missing document: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"release manifest hash mismatch: {relative}")
    remote_exists = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=ROOT, text=True, capture_output=True,
    ).returncode == 0
    if remote_exists and manifest["repository_commit"] == "pending-finalization":
        raise AssertionError("release manifest commit remains pending after origin configuration")
    return Check("release manifest integrity", "PASS", f"{len(manifest['document_hashes'])} document hashes and 10 ADRs verified")


def check_capability_evaluations() -> Check:
    matrix = load_data(ROOT / "spec" / "v1-capability-matrix.yaml")
    gates = load_data(ROOT / "spec" / "v1-acceptance-gates.yaml")
    gate_ids = {gate["evaluation_id"] for gate in gates["gates"]}
    referenced = {eid for cap in matrix["capabilities"] for eid in cap["evaluation_id"]}
    missing = referenced - gate_ids
    if missing:
        raise AssertionError(f"capabilities reference missing gates: {sorted(missing)}")
    for gate in gates["gates"]:
        for key in ("threshold", "method", "dataset", "sample_count", "pass_rule"):
            if not gate.get(key):
                raise AssertionError(f"{gate['evaluation_id']}: missing {key}")
    return Check("capability evaluation links", "PASS", f"{len(matrix['capabilities'])} capabilities, {len(gate_ids)} gates")


def check_documents() -> Check:
    scan_paths = list((ROOT / "docs").rglob("*.md")) + list((ROOT / "spec").glob("*.yaml"))
    placeholder = re.compile(r"\b(?:TBD|TODO|FIXME)\b", re.IGNORECASE)
    for path in scan_paths:
        if path.name == "open-questions.md":
            continue
        if placeholder.search(path.read_text(encoding="utf-8")):
            raise AssertionError(f"unresolved placeholder in {path.relative_to(ROOT)}")

    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for path in list(ROOT.rglob("*.md")):
        for target in link_re.findall(path.read_text(encoding="utf-8")):
            clean = target.split("#", 1)[0]
            if not clean or re.match(r"^[a-z]+://", clean):
                continue
            if not (path.parent / clean).resolve().exists():
                raise AssertionError(f"broken relative link in {path.relative_to(ROOT)}: {target}")
    return Check("document hygiene", "PASS", "no unresolved placeholders or broken relative links")


def check_repository_safety() -> list[Check]:
    files = candidate_files()
    forbidden = [p for p in files if Path(p).suffix.lower() in FORBIDDEN_SUFFIXES or any(p == prefix or p.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)]
    if forbidden:
        raise AssertionError(f"forbidden tracked/candidate paths: {forbidden}")
    secret_hits: list[str] = []
    for rel in files:
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                secret_hits.append(f"{rel}: {label}")
    if secret_hits:
        raise AssertionError(f"possible secrets: {secret_hits}")
    return [
        Check("forbidden file policy", "PASS", f"{len(files)} tracked/candidate files inspected"),
        Check("secret scan", "PASS", "no recognized credential material"),
    ]


def check_remote_visibility() -> Check:
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True, capture_output=True)
    if remote.returncode != 0:
        return Check("private remote visibility", "SKIP", "origin is not configured; allowed before remote creation")
    view = subprocess.run(
        ["gh", "repo", "view", "--json", "visibility,hasWikiEnabled"],
        cwd=ROOT, text=True, capture_output=True,
    )
    if view.returncode != 0:
        raise AssertionError(f"cannot verify origin visibility: {view.stderr.strip()}")
    remote_policy = json.loads(view.stdout)
    visibility = str(remote_policy.get("visibility", "")).upper()
    if visibility != "PRIVATE":
        raise AssertionError(f"origin visibility is {visibility}, expected PRIVATE")
    if remote_policy.get("hasWikiEnabled") is not False:
        raise AssertionError("GitHub Wiki is enabled, expected disabled")
    runs = subprocess.run(
        ["gh", "run", "list", "--limit", "1", "--json", "databaseId"],
        cwd=ROOT, text=True, capture_output=True,
    )
    if runs.returncode != 0:
        raise AssertionError(f"cannot inspect GitHub Actions history: {runs.stderr.strip()}")
    if json.loads(runs.stdout):
        raise AssertionError("GitHub Actions has a run, prohibited in V0.0.0")
    pages = subprocess.run(
        ["gh", "api", "repos/{owner}/{repo}/pages"],
        cwd=ROOT, text=True, capture_output=True,
    )
    if pages.returncode == 0:
        raise AssertionError("GitHub Pages is enabled, prohibited in V0.0.0")
    if "HTTP 404" not in pages.stderr:
        raise AssertionError(f"cannot verify GitHub Pages is disabled: {pages.stderr.strip()}")
    return Check(
        "private remote policy", "PASS",
        "GitHub reports PRIVATE, Wiki disabled, Pages absent, and no Actions runs",
    )


def run_all() -> list[Check]:
    checks = [check_schemas()]
    checks.extend(check_examples())
    checks.append(check_root_contracts())
    checks.append(check_product_invariants())
    checks.append(check_adrs_and_traceability())
    checks.append(check_decision_consistency())
    checks.append(check_manifest_integrity())
    checks.append(check_capability_evaluations())
    checks.append(check_documents())
    checks.extend(check_repository_safety())
    checks.append(check_remote_visibility())
    return checks


def main() -> int:
    try:
        checks = run_all()
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for check in checks:
        print(f"{check.status}: {check.name} - {check.detail}")
    print(f"PASS: {sum(c.status == 'PASS' for c in checks)} checks; {sum(c.status == 'SKIP' for c in checks)} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
