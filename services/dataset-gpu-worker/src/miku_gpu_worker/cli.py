"""Command-line interface for explicit user-session execution."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .executor import STATES, Worker
from .metrics import environment_snapshot
from .protocol import TASK_TYPES, validate_job_package
from .registry import load_registry


def worker_root(value: str | None) -> Path:
    configured = value or os.environ.get("MIKU_WORKER_ROOT")
    if not configured:
        raise SystemExit("MIKU_WORKER_ROOT or --root is required")
    return Path(configured)


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="miku-worker")
    parser.add_argument("--root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    inspect = commands.add_parser("inspect"); inspect.add_argument("package", type=Path)
    submit = commands.add_parser("submit"); submit.add_argument("package", type=Path)
    run = commands.add_parser("run"); run.add_argument("--job"); run.add_argument("--watch-inbox", action="store_true"); run.add_argument("--force", action="store_true")
    status = commands.add_parser("status"); status.add_argument("job_id", nargs="?")
    verify = commands.add_parser("verify"); verify.add_argument("job_id")
    cancel = commands.add_parser("cancel"); cancel.add_argument("job_id")
    commands.add_parser("benchmark")
    models = commands.add_parser("models"); models.add_argument("registry", nargs="?", type=Path)
    cache = commands.add_parser("cache"); cache.add_argument("action", choices=("status", "verify", "prune"))
    commands.add_parser("clean-cache")
    recover = commands.add_parser("recover"); recover.add_argument("--stale-after", type=float, default=3600)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = worker_root(args.root)
    worker = Worker(root)
    if args.command == "doctor":
        snapshot = environment_snapshot("0" * 40)
        snapshot.update({"worker_root": str(root.resolve()), "disk_free_bytes": shutil.disk_usage(root).free, "task_allowlist": sorted(TASK_TYPES)})
        print_json(snapshot); return 0
    if args.command == "inspect":
        job, spec = validate_job_package(args.package); print_json({"job": job, "worker_spec": spec}); return 0
    if args.command == "submit":
        print(worker.submit(args.package)); return 0
    if args.command == "run":
        if args.watch_inbox:
            for package in sorted((root / "jobs" / "inbox").iterdir()):
                if package.is_dir(): print(worker.run(package.name, force=args.force))
            return 0
        if not args.job: raise SystemExit("run requires --job or --watch-inbox")
        target = worker.run(args.job, force=args.force); print(target)
        return 0 if target.parent.name == "completed" else 1
    if args.command == "status":
        values = {state: sorted(path.name for path in (root / "jobs" / state).iterdir()) for state in STATES}
        if args.job_id: values = {state: jobs for state, jobs in values.items() if args.job_id in jobs}
        print_json(values); return 0
    if args.command == "verify":
        ok = worker.verify(args.job_id); print_json({"job_id": args.job_id, "verified": ok}); return 0 if ok else 1
    if args.command == "cancel":
        source = worker.state_path("inbox", args.job_id); source.replace(worker.state_path("cancelled", args.job_id)); return 0
    if args.command == "models":
        print_json([] if args.registry is None else load_registry(args.registry)); return 0
    if args.command in {"cache", "clean-cache"}:
        cache = root / "objects" / "output-cache"
        if args.command == "clean-cache" or args.action == "prune":
            for path in cache.iterdir():
                if path.is_file(): path.unlink()
        print_json({"entries": len(list(cache.iterdir())), "path": str(cache)}); return 0
    if args.command == "recover":
        print_json({"recovered": worker.recover_stale(args.stale_after)}); return 0
    if args.command == "benchmark":
        print_json({"status": "BLOCKED", "reason": "benchmark requires an idle RTX 5090 and pinned model profiles"}); return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())

