import json
import os
import subprocess
import importlib.util
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_opencode_output_is_validated_and_receipt_redacts_secret(tmp_path: Path) -> None:
    executable = tmp_path / "opencode"
    executable.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' '{\"type\":\"text\",\"part\":{\"text\":\"{\\\"status\\\":\\\"completed\\\",\\\"summary\\\":\\\"ok\\\",\\\"result\\\":{}}\"}}'\n"
        "printf '%s\\n' '{\"type\":\"step_finish\",\"part\":{\"tokens\":{\"total\":1},\"cost\":0}}'\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    env_file = tmp_path / ".env"
    secret = "test-secret-value-never-store"
    env_file.write_text(f"OPENCODE_API_KEY={secret}\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    environment = {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "MIKU_SUBAGENT_ENV": str(env_file),
    }
    completed = subprocess.run(
        [
            str(ROOT / "scripts/subagents/run-opencode"),
            "--model",
            "fake/model",
            "--role",
            "critic",
            "--schema",
            str(ROOT / "schemas/subagents/result.schema.json"),
            "--receipt",
            str(receipt),
            "return json",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    record = json.loads(receipt.read_text(encoding="utf-8"))
    assert record["result"] == {"status": "completed", "validated": True}
    assert record["retention"] == "provider_default"
    assert secret not in receipt.read_text(encoding="utf-8") + completed.stdout + completed.stderr


def test_failed_provider_is_not_validated_and_secret_is_redacted(tmp_path: Path) -> None:
    executable = tmp_path / "opencode"
    secret = "test-secret-value-never-store"
    executable.write_text(f"#!/bin/sh\necho 'auth failed: {secret}' >&2\nexit 1\n", encoding="utf-8")
    executable.chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text(f"OPENCODE_API_KEY={secret}\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    completed = subprocess.run(
        [
            str(ROOT / "scripts/subagents/run-opencode"), "--model", "fake/model",
            "--role", "critic", "--schema", str(ROOT / "schemas/subagents/result.schema.json"),
            "--receipt", str(receipt), "return json",
        ],
        cwd=ROOT,
        env={"PATH": f"{tmp_path}:{os.environ['PATH']}", "MIKU_SUBAGENT_ENV": str(env_file)},
        capture_output=True,
        text=True,
        check=False,
    )
    record = json.loads(receipt.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert record["result"] == {"status": "failed", "validated": False}
    assert record["failure"]["category"] == "AUTH_INVALID"
    assert secret not in receipt.read_text(encoding="utf-8") + completed.stderr


def test_window_audit_counts_acceptance_not_attempts(tmp_path: Path) -> None:
    script = ROOT / "tools/audit_subagent_window.py"
    spec = importlib.util.spec_from_file_location("window_audit", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    (tmp_path / "receipts").mkdir(); (tmp_path / "outputs").mkdir()
    jobs = []
    for index, provider in enumerate(("command_code", "command_code", "opencode")):
        job_id = f"job-{index}"; value = {"value": index}
        output_sha = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        (tmp_path / "outputs" / f"{job_id}.json").write_text(json.dumps(value), encoding="utf-8")
        (tmp_path / "receipts" / f"{job_id}.json").write_text(json.dumps({
            "job_id": job_id, "provider": provider, "model": "model", "role": "role",
            "attempts": 1, "wall_ms": 1, "result": {"status": "completed", "validated": True},
            "failure": None, "output_sha256": output_sha,
        }), encoding="utf-8")
        jobs.append({"job_id": job_id, "receipt": f"receipts/{job_id}.json",
                     "output": f"outputs/{job_id}.json", "output_sha256": output_sha,
                     "parent_decision": "accepted", "used_in": "test"})
    (tmp_path / "accepted-window.json").write_text(json.dumps({"accepted_jobs": jobs}), encoding="utf-8")
    result = module.audit(tmp_path, minimum=3)
    assert result["accepted_jobs"] == 3
    assert result["command_code_to_opencode_ratio"] == 2
