from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from .config import initialize_layout, paths_from_env
from .export import export_training, snapshot
from .ingest import register_source
from .jobs import authorize_remote_5090, ensure_job, prepare_remote_package
from .lineage import plan_transform
from .pilot import build as build_pilot
from .registry import Registry
from .report import inventory
from .review import promote_sample
from .review_server import serve
from .rights import promote_training, register_rights
from .split import assign_group, leakage_findings
from .store import ObjectStore
from .worker_import import import_worker_result


WRITE_COMMANDS = {"init", "ingest", "register-source", "register-rights", "plan-transform", "run-job",
                  "segment", "transcribe", "align", "normalize", "score", "dedup", "split", "snapshot",
                  "export", "queue-5090", "pilot", "promote", "promote-sample"}
WRITE_COMMANDS.add("import-worker-result")


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _load_json(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="miku-data")
    root.add_argument("--data-root")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("init", "doctor", "verify-objects", "report", "pilot"):
        command = sub.add_parser(name)
        if name in WRITE_COMMANDS:
            command.add_argument("--dry-run", action="store_true")

    command = sub.add_parser("register-source")
    command.add_argument("--metadata", required=True)
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("ingest")
    command.add_argument("path")
    command.add_argument("--source-id", required=True)
    command.add_argument("--role", default="raw")
    command.add_argument("--media-type")
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("register-rights")
    command.add_argument("--source-id", required=True)
    command.add_argument("--status", required=True)
    command.add_argument("--evidence-type", required=True)
    command.add_argument("--evidence-ref", required=True)
    command.add_argument("--allowed-use", required=True)
    command.add_argument("--reviewer", required=True)
    command.add_argument("--actor-type", required=True)
    command.add_argument("--training-allowed", action=argparse.BooleanOptionalAction, default=False)
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("promote")
    command.add_argument("--source-id", required=True)
    command.add_argument("--actor", required=True)
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("promote-sample")
    command.add_argument("--entity-type", choices=("audio", "text", "persona", "agentic", "duplex"), required=True)
    command.add_argument("--entity-id", required=True)
    command.add_argument("--actor", required=True)
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("plan-transform")
    command.add_argument("--kind", required=True)
    command.add_argument("--input", action="append", required=True)
    command.add_argument("--spec", required=True)
    command.add_argument("--tool", required=True)
    command.add_argument("--tool-version", required=True)
    command.add_argument("--dry-run", action="store_true")
    for name in ("run-job", "segment", "transcribe", "align", "normalize", "score", "dedup"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", required=True)
        command.add_argument("--resume", action="store_true")
        command.add_argument("--job-id")
        command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("split")
    command.add_argument("--group-id")
    command.add_argument("--split", choices=("train", "validation", "test", "eval"))
    command.add_argument("--freeze", action="store_true")
    command.add_argument("--audit", action="store_true")
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("snapshot")
    command.add_argument("--snapshot-id", required=True)
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("export")
    command.add_argument("--corpus", choices=("audio", "text", "persona", "agentic", "duplex"), required=True)
    command.add_argument("--split", choices=("train", "validation", "test", "eval"), required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("queue-5090")
    command.add_argument("--manifest", required=True)
    command.add_argument("--grant")
    command.add_argument("--dry-run", action="store_true")
    command = sub.add_parser("review")
    review = command.add_subparsers(dest="review_command", required=True)
    serve_parser = review.add_parser("serve")
    serve_parser.add_argument("--port", type=int, default=8765)
    review.add_parser("export")
    command = sub.add_parser("verify-release")
    command.add_argument("receipt")
    command = sub.add_parser("import-worker-result")
    command.add_argument("package")
    command.add_argument("--actor", required=True)
    command.add_argument("--dry-run", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    paths = paths_from_env(args.data_root)
    registry = Registry(paths.registry)
    dry_run = bool(getattr(args, "dry_run", False))
    if args.command == "init":
        if dry_run:
            _json({"would_initialize": str(paths.root)})
            return 0
        initialize_layout(paths)
        registry.initialize()
        _json({"initialized": str(paths.root), "registry": str(paths.registry)})
        return 0
    if not paths.registry.exists():
        raise RuntimeError("foundry is not initialized")
    registry.initialize()

    if args.command == "doctor":
        usage = shutil.disk_usage(paths.root)
        store = ObjectStore(paths, registry)
        result = {"data_root": str(paths.root), "free_bytes": usage.free,
                  "reserve_ok": usage.free >= 5 * 1024**3, "object_failures": store.verify(),
                  "recovery": store.reconcile()}
        _json(result)
        return 0 if result["reserve_ok"] and not result["object_failures"] else 1
    if args.command == "register-source":
        value = _load_json(args.metadata)
        if dry_run:
            _json({"would_register": value})
        else:
            _json({"source_id": register_source(registry, **value)})
    elif args.command == "ingest":
        _json({"sha256": ObjectStore(paths, registry).ingest(Path(args.path), args.source_id,
                role=args.role, media_type=args.media_type, dry_run=dry_run), "dry_run": dry_run})
    elif args.command == "verify-objects":
        failures = ObjectStore(paths, registry).verify()
        _json({"failures": failures})
        return int(bool(failures))
    elif args.command == "register-rights":
        if dry_run:
            _json({"would_register": args.status, "source_id": args.source_id,
                   "training_allowed": args.training_allowed})
        else:
            _json({"rights_id": register_rights(registry, args.source_id, args.status, args.evidence_type,
                   args.evidence_ref, args.allowed_use, reviewer=args.reviewer, actor_type=args.actor_type,
                   training_allowed=args.training_allowed)})
    elif args.command == "promote":
        if dry_run:
            _json({"would_promote": args.source_id})
        else:
            promote_training(registry, args.source_id, actor=args.actor)
            _json({"promoted": args.source_id})
    elif args.command == "promote-sample":
        if dry_run:
            _json({"would_promote_sample": args.entity_id, "entity_type": args.entity_type})
        else:
            changed = promote_sample(registry, args.entity_type, args.entity_id, actor=args.actor)
            _json({"promoted": args.entity_id, "entity_type": args.entity_type, "changed": changed})
    elif args.command == "plan-transform":
        spec = _load_json(args.spec)
        if dry_run:
            _json({"would_plan": args.kind, "inputs": args.input, "spec": spec})
        else:
            _json({"transform_id": plan_transform(registry, args.kind, args.input, spec,
                   tool=args.tool, tool_version=args.tool_version)})
    elif args.command in {"run-job", "segment", "transcribe", "align", "normalize", "score", "dedup"}:
        manifest = _load_json(args.manifest)
        if dry_run:
            _json({"would_queue": args.command, "manifest": manifest})
        else:
            _json({"job_id": ensure_job(registry, args.command, manifest), "state": "prepared"})
    elif args.command == "split":
        if args.audit:
            findings = leakage_findings(registry)
            _json({"findings": findings})
            return int(bool(findings))
        if not args.group_id:
            raise ValueError("--group-id is required unless --audit is used")
        if dry_run:
            _json({"would_assign": args.group_id, "split": args.split, "freeze": args.freeze})
        else:
            _json({"split": assign_group(registry, args.group_id, split=args.split, freeze=args.freeze)})
    elif args.command == "snapshot":
        if dry_run:
            _json({"would_snapshot": args.snapshot_id})
        else:
            _json(snapshot(registry, paths, args.snapshot_id))
    elif args.command == "export":
        if dry_run:
            _json({"would_export": args.corpus, "split": args.split, "output": args.output})
        else:
            _json(export_training(registry, Path(args.output), split=args.split, corpus=args.corpus))
    elif args.command == "queue-5090":
        manifest = _load_json(args.manifest)
        if dry_run:
            _json({"would_queue_remote": manifest})
        else:
            job_id, state = prepare_remote_package(paths, registry, manifest)
            grant = _load_json(args.grant) if args.grant else None
            if grant:
                authorize_remote_5090(registry, job_id, grant)
                state = "staged"
            _json({"job_id": job_id, "state": state})
    elif args.command == "pilot":
        if dry_run:
            _json({"would_build": {"audio_sources": 10, "audio_samples": 100, "persona": 1000,
                                    "agentic": 500, "duplex": 500}})
        else:
            _json(build_pilot(paths, registry))
    elif args.command == "report":
        _json(inventory(registry))
    elif args.command == "review":
        if args.review_command == "serve":
            serve(paths, registry, args.port)
        else:
            with registry.connect() as connection:
                _json([dict(row) for row in connection.execute("SELECT * FROM reviews ORDER BY created_at")])
    elif args.command == "verify-release":
        receipt_path = Path(args.receipt)
        receipt = _load_json(args.receipt)
        base = receipt_path.parent
        failures = []
        for name, expected in receipt.get("parquet_sha256", {}).items():
            actual = hashlib.sha256((base / name).read_bytes()).hexdigest()
            if actual != expected:
                failures.append({"path": name, "expected": expected, "actual": actual})
        _json({"failures": failures})
        return int(bool(failures))
    elif args.command == "import-worker-result":
        if dry_run:
            _json({"would_import_worker_result": args.package, "actor": args.actor})
        else:
            _json(import_worker_result(paths, registry, Path(args.package), actor=args.actor))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, PermissionError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
