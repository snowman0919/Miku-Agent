#!/usr/bin/env python3
"""Collect a sanitized, command-backed server inventory."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path


NVIDIA_SMI = shutil.which("nvidia-smi") or "/usr/lib/wsl/lib/nvidia-smi"


def command(argv: list[str]) -> dict[str, object]:
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=30, check=False)
        return {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": argv, "exit_code": None, "error": repr(exc)}


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--phase", choices=("pre-install", "post-install"), required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    environment = {
        "schema_version": 1,
        "phase": args.phase,
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "timezone": os.environ.get("TZ", "system-default"),
        "commands": [
            command(["uname", "-a"]), command(["cat", "/etc/os-release"]),
            command(["ldd", "--version"]), command(["uptime"]),
            command(["systemd-detect-virt"]), command(["lscpu"]),
            command(["free", "-b"]), command(["numactl", "--hardware"]),
            command(["nvcc", "--version"]), command(["docker", "version"]),
            command(["nvidia-container-cli", "info"]), command(["nvidia-ctk", "--version"]),
        ],
    }
    gpu = {
        "schema_version": 1,
        "source_of_truth": NVIDIA_SMI,
        "summary": command([NVIDIA_SMI]),
        "list": command([NVIDIA_SMI, "-L"]),
        "query": command([
            NVIDIA_SMI,
            "--query-gpu=name,uuid,pci.bus_id,driver_version,memory.total,memory.free,power.limit,power.max_limit,temperature.gpu,clocks.sm,clocks.mem,compute_mode,persistence_mode",
            "--format=csv,noheader,nounits",
        ]),
        "processes": command([NVIDIA_SMI, "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"]),
        "topology": command([NVIDIA_SMI, "topo", "-m"]),
    }
    storage = {
        "schema_version": 1,
        "df_bytes": command(["df", "-BT"]),
        "df_inodes": command(["df", "-i"]),
        "block_devices": command(["lsblk", "-b", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA"]),
    }
    network = {
        "schema_version": 1,
        "hostname": socket.gethostname(),
        "addresses": command(["ip", "-brief", "address"]),
        "routes": command(["ip", "route"]),
        "resolvers_present": Path("/etc/resolv.conf").exists(),
    }
    write(args.output_dir / "environment.json", environment)
    write(args.output_dir / "gpu-inventory.json", gpu)
    write(args.output_dir / "storage-inventory.json", storage)
    write(args.output_dir / "network-inventory.json", network)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
