#!/usr/bin/env python3
"""Network-independent repository validation for Miku Agent release evidence."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

try:
    from .release_common import (
        EXPECTED_V000_COMMIT,
        EXPECTED_V000_TAG_OBJECT,
        EXPECTED_V001_COMMIT,
        EXPECTED_V001_DEFINITION,
        EXPECTED_V001_TAG_OBJECT,
        ROOT,
        assert_no_prohibited_commit_fields,
        commit_exists,
        git,
        git_text,
        load_yaml,
        v000_local_identity,
        validate_definition_binding,
        validate_document_hashes,
        validate_v000_history_entry,
    )
except ImportError:  # Direct script execution.
    from release_common import (
    EXPECTED_V000_COMMIT,
    EXPECTED_V000_TAG_OBJECT,
    EXPECTED_V001_COMMIT,
    EXPECTED_V001_DEFINITION,
    EXPECTED_V001_TAG_OBJECT,
    ROOT,
    assert_no_prohibited_commit_fields,
    commit_exists,
    git,
    git_text,
    load_yaml,
    v000_local_identity,
    validate_definition_binding,
    validate_document_hashes,
    validate_v000_history_entry,
    )

SCHEMA_TARGETS = {
    "product-lock": "product-lock.schema.json",
    "project-state": "project-state.schema.json",
    "release-manifest": "release-manifest.schema.json",
    "release-history": "release-history.schema.json",
    "run-binding": "run-binding.schema.json",
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
DATASET_SCHEMA_NAMES = {
    "agentic-execution-receipt.schema.json", "agentic-trajectory.schema.json",
    "audio-sample.schema.json", "dataset-release.schema.json",
    "duplex-timeline.schema.json", "object.schema.json", "persona-sample.schema.json",
    "remote-job.schema.json", "review.schema.json", "rights-record.schema.json",
    "source.schema.json", "split-assignment.schema.json", "text-sample.schema.json",
    "transform.schema.json",
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
    "release-manifest.self-referential-commit.yaml": "Additional properties",
}

FORBIDDEN_SUFFIXES = {
    ".key", ".pem", ".p12", ".wav", ".mp3", ".flac", ".ogg", ".mp4",
    ".mkv", ".vrm", ".pt", ".pth", ".ckpt", ".safetensors", ".onnx",
    ".engine", ".plan",
    ".sqlite", ".sqlite3", ".db", ".parquet", ".arrow", ".bin",
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
FORBIDDEN_MAGIC = {
    b"SQLite format 3\x00": "SQLite database",
    b"PAR1": "Parquet data",
    b"RIFF": "RIFF media",
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
    "0011": ("docs/versioning-and-release.md", ("definition_commit", "annotated", "offline")),
    "0012": ("docs/dataset/architecture.md", ("sha-256", "sqlite", "canonical")),
    "0013": ("docs/dataset/gpu-worker-topology.md", ("rtx 3080", "rtx 5090", "manifest")),
    "0014": ("docs/dataset/rights-promotion.md", ("rights", "quality", "training")),
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
    result = git("ls-files", "--cached", "--others", "--exclude-standard")
    return sorted(line for line in result.stdout.splitlines() if line)


def check_schemas() -> Check:
    root_schemas = sorted((ROOT / "schemas").glob("*.schema.json"))
    if {path.name for path in root_schemas} != set(SCHEMA_TARGETS.values()):
        raise AssertionError("schema inventory does not match the required contract set")
    dataset_schemas = sorted((ROOT / "schemas" / "dataset").glob("*.schema.json"))
    if {path.name for path in dataset_schemas} != DATASET_SCHEMA_NAMES:
        raise AssertionError("V0.2 dataset schema inventory does not match the required contract set")
    schemas = root_schemas + dataset_schemas
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
    if {path.name for path in invalid_paths} != set(INVALID_EXPECTATIONS):
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


def _legacy_root_is_preserved(manifest: dict[str, Any], state: dict[str, Any]) -> bool:
    return (
        manifest.get("product_version") == "0.0.0"
        and manifest.get("phase") == "product-definition-lock"
        and state.get("product_version") == "0.0.0"
        and state.get("phase") == "product-definition-lock"
    )


def check_root_contracts() -> Check:
    product_errors = validate_instance("product-lock", load_data(ROOT / "spec" / "product-lock.yaml"))
    if product_errors:
        raise AssertionError(f"product-lock.yaml: {product_errors}")
    manifest = load_data(ROOT / "release-manifest.yaml")
    state = load_data(ROOT / "PROJECT_STATE.yaml")
    if _legacy_root_is_preserved(manifest, state):
        return Check("root machine contracts", "PASS", "V0.0.0 root evidence preserved during Commit A preparation")
    for name, value in (("release-manifest", manifest), ("project-state", state)):
        errors = validate_instance(name, value)
        if errors:
            raise AssertionError(f"{name}: {errors}")
    return Check("root machine contracts", "PASS", f"product lock and V{manifest['product_version']} evidence contracts")


def check_product_invariants() -> Check:
    lock = load_data(ROOT / "spec" / "product-lock.yaml")
    assertions = {
        "private repository": lock["repository"]["visibility"] == "private",
        "local-only": lock["execution"]["local_only"] is True,
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
        raise AssertionError(f"failed locked product invariants: {failed}")
    return Check("product invariants", "PASS", f"{len(assertions)} V0.0.0 decisions unchanged")


def check_adrs_and_traceability() -> Check:
    adr_paths = sorted((ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    if len(adr_paths) != 14:
        raise AssertionError(f"expected 14 ADRs in the V0.2 workspace, found {len(adr_paths)}")
    headings = ["Status", "Date", "Context", "Decision", "Alternatives Considered", "Consequences", "Security Impact", "Data Impact", "Validation", "Supersedes", "Superseded By"]
    trace = (ROOT / "docs" / "traceability-matrix.md").read_text(encoding="utf-8")
    for path in adr_paths:
        text = path.read_text(encoding="utf-8")
        if "## Status\naccepted" not in text:
            raise AssertionError(f"{path.name}: ADR is not accepted")
        for heading in headings:
            if f"## {heading}" not in text:
                raise AssertionError(f"{path.name}: missing {heading}")
        if f"ADR-{path.name[:4]}" not in trace:
            raise AssertionError(f"ADR-{path.name[:4]} missing from traceability matrix")
    rows = [line for line in trace.splitlines() if re.match(r"^\| D-[0-9]{3} ", line)]
    if len(rows) < 13:
        raise AssertionError("traceability matrix has fewer than 13 accepted decisions")
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) != 9 or not all(cells[index] for index in (3, 4, 5, 6)) or cells[8] != "accepted":
            raise AssertionError(f"incomplete traceability row: {row}")
    return Check("ADR and traceability", "PASS", f"14 accepted ADRs, {len(rows)} decision links")


def check_decision_consistency() -> Check:
    for adr_number, (document, anchors) in DECISION_EVIDENCE.items():
        adr_path = next((ROOT / "docs" / "adr").glob(f"{adr_number}-*.md"), None)
        if adr_path is None:
            raise AssertionError(f"ADR-{adr_number} is missing")
        adr_text = adr_path.read_text(encoding="utf-8").lower()
        document_text = (ROOT / document).read_text(encoding="utf-8").lower()
        for anchor in anchors:
            if anchor.lower() not in adr_text or anchor.lower() not in document_text:
                raise AssertionError(f"ADR-{adr_number} and {document} lost shared anchor {anchor!r}")
    return Check("ADR/document consistency", "PASS", "14 accepted decisions share semantic anchors")


def check_release_history() -> Check:
    ledger = load_yaml(ROOT / "spec" / "release-history.yaml")
    errors = validate_instance("release-history", ledger)
    if errors:
        raise AssertionError(f"release-history.yaml: {errors}")
    v000 = next((item for item in ledger["releases"] if item["version"] == "0.0.0"), None)
    if v000 is None:
        raise AssertionError("release history is missing V0.0.0")
    tag_object, peeled = validate_v000_history_entry(v000)
    v001 = next((item for item in ledger["releases"] if item["version"] == "0.0.1"), None)
    if not v001 or v001.get("status") != "released":
        raise AssertionError("release history is missing released V0.0.1")
    if v001.get("definition_commit") != EXPECTED_V001_DEFINITION:
        raise AssertionError("release history V0.0.1 definition differs from immutable baseline")
    if git_text("rev-parse", "v0.0.1") != EXPECTED_V001_TAG_OBJECT or git_text("rev-parse", "v0.0.1^{commit}") != EXPECTED_V001_COMMIT:
        raise AssertionError("V0.0.1 local tag identity differs from immutable baseline")
    manifest = load_data(ROOT / "release-manifest.yaml")
    if manifest.get("product_version") == "0.1.0":
        v010 = next((item for item in ledger["releases"] if item["version"] == "0.1.0"), None)
        definition = manifest.get("release_identity", {}).get("definition_commit")
        if not v010 or v010.get("status") != "released" or v010.get("definition_commit") != definition:
            raise AssertionError("release history V0.1.0 definition differs from manifest")
    return Check("release history", "PASS", f"V0.0.0 tag object {tag_object} and peeled commit {peeled}")


def check_manifest_integrity() -> Check:
    manifest = load_data(ROOT / "release-manifest.yaml")
    state = load_data(ROOT / "PROJECT_STATE.yaml")
    if _legacy_root_is_preserved(manifest, state):
        return Check("release manifest integrity", "PASS", "legacy V0.0.0 evidence retained until Commit B")
    assert_no_prohibited_commit_fields(manifest)
    expected_adrs = [f"ADR-{number:04d}" for number in range(1, 12)]
    if manifest["accepted_adrs"] != expected_adrs:
        raise AssertionError("manifest accepted ADR inventory is incomplete or out of order")
    definition = manifest["release_identity"]["definition_commit"]
    tag = manifest["release_identity"].get("tag")
    tag_exists = bool(tag) and git("rev-parse", "--verify", f"refs/tags/{tag}", check=False).returncode == 0
    historical_v010 = (
        manifest.get("product_version") == "0.1.0"
        and tag == "v0.1.0"
        and tag_exists
        and git("merge-base", "--is-ancestor", "v0.1.0^{commit}", "HEAD", check=False).returncode == 0
        and git("diff", "--quiet", "v0.1.0", "--", "release-manifest.yaml", check=False).returncode == 0
    )
    release_ref = tag if tag_exists else "HEAD"
    if historical_v010:
        binding_mode = "historical-release-descendant:" + validate_definition_binding(
            definition, release_ref=release_ref, allow_preparation=False
        )
    else:
        binding_mode = validate_definition_binding(
            definition, release_ref=release_ref, allow_preparation=True
        )
    validate_document_hashes(definition, manifest["document_hashes"])
    return Check(
        "release manifest integrity", "PASS",
        f"format 2 {binding_mode} at {release_ref}; {len(manifest['document_hashes'])} hashes bound to {definition}",
    )


def check_capability_evaluations() -> Check:
    matrix = load_data(ROOT / "spec" / "v1-capability-matrix.yaml")
    gates = load_data(ROOT / "spec" / "v1-acceptance-gates.yaml")
    gate_ids = {gate["evaluation_id"] for gate in gates["gates"]}
    referenced = {eid for cap in matrix["capabilities"] for eid in cap["evaluation_id"]}
    if referenced - gate_ids:
        raise AssertionError(f"capabilities reference missing gates: {sorted(referenced - gate_ids)}")
    for gate in gates["gates"]:
        for key in ("threshold", "method", "dataset", "sample_count", "pass_rule"):
            if not gate.get(key):
                raise AssertionError(f"{gate['evaluation_id']}: missing {key}")
    return Check("capability evaluation links", "PASS", f"{len(matrix['capabilities'])} capabilities, {len(gate_ids)} gates")


def check_documents() -> Check:
    scan_paths = list((ROOT / "docs").rglob("*.md")) + list((ROOT / "spec").glob("*.yaml"))
    placeholder = re.compile(r"\b(?:TBD|TODO|FIXME)\b", re.IGNORECASE)
    for path in scan_paths:
        if path.name != "open-questions.md" and placeholder.search(path.read_text(encoding="utf-8")):
            raise AssertionError(f"unresolved placeholder in {path.relative_to(ROOT)}")
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        for target in link_re.findall(path.read_text(encoding="utf-8")):
            clean = target.split("#", 1)[0]
            if clean and not re.match(r"^[a-z]+://", clean) and not (path.parent / clean).resolve().exists():
                raise AssertionError(f"broken relative link in {path.relative_to(ROOT)}: {target}")
    return Check("document hygiene", "PASS", "no unresolved placeholders or broken relative links")


def check_repository_safety() -> list[Check]:
    files = candidate_files()
    forbidden = [path for path in files if Path(path).suffix.lower() in FORBIDDEN_SUFFIXES or any(path == prefix or path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)]
    if forbidden:
        raise AssertionError(f"forbidden tracked/candidate paths: {forbidden}")
    disguised: list[str] = []
    for relative in files:
        path = ROOT / relative
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            prefix = stream.read(16)
        for magic, label in FORBIDDEN_MAGIC.items():
            if prefix.startswith(magic):
                disguised.append(f"{relative}: {label}")
    if disguised:
        raise AssertionError(f"forbidden artifact content: {disguised}")
    secret_hits: list[str] = []
    for relative in files:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                secret_hits.append(f"{relative}: {label}")
    if secret_hits:
        raise AssertionError(f"possible secrets: {secret_hits}")
    return [
        Check("forbidden file policy", "PASS", f"{len(files)} tracked/candidate files inspected"),
        Check("secret scan", "PASS", "no recognized credential material"),
    ]


def check_local_git_invariants() -> Check:
    if git_text("rev-parse", "--is-inside-work-tree") != "true":
        raise AssertionError("not inside a Git working tree")
    tag_type, tag_object, peeled = v000_local_identity()
    if (tag_type, tag_object, peeled) != ("tag", EXPECTED_V000_TAG_OBJECT, EXPECTED_V000_COMMIT):
        raise AssertionError("V0.0.0 local tag invariant failed")
    if not commit_exists("HEAD"):
        raise AssertionError("HEAD is not a commit")
    return Check("local Git invariants", "PASS", "Git repository and immutable V0.0.0 tag verified offline")


def run_all() -> list[Check]:
    checks = [check_schemas()]
    checks.extend(check_examples())
    checks.extend([
        check_root_contracts(),
        check_product_invariants(),
        check_adrs_and_traceability(),
        check_decision_consistency(),
        check_release_history(),
        check_manifest_integrity(),
        check_capability_evaluations(),
        check_documents(),
    ])
    checks.extend(check_repository_safety())
    checks.append(check_local_git_invariants())
    return checks


def main() -> int:
    try:
        checks = run_all()
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}")
        return 1
    for check in checks:
        print(f"{check.status}: {check.name} - {check.detail}")
    print(f"PASS: {len(checks)} offline checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
