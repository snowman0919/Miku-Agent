from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "generate_speech_render_bundle.py"


def test_render_bundle_is_unique_and_never_self_accepts(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("render_bundle", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    seeds = tmp_path / "seeds.json"
    seeds.write_text(json.dumps({"seeds": [{
        "seed_id": "seed-1", "generation_job_id": "job-1", "category": "질문",
        "raw_text": "파일을 확인했나요?", "scenario": "확인 질문",
        "coverage_targets": ["의문 억양"], "review_status": "candidate",
    }]}), encoding="utf-8")
    (tmp_path / "accepted-window.json").write_text(json.dumps({"accepted_jobs": [
        {"job_id": "job-1", "provider": "command_code", "model": "generator"},
        {"job_id": "critic-1", "provider": "opencode", "model": "critic"},
    ]}), encoding="utf-8")
    output = tmp_path / "bundle.jsonl"
    manifest = module.build(seeds, output, 16)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert manifest["exact_unique_rows"] == len(rows) == 16
    assert {row["human_review"] for row in rows} == {"pending"}
    assert {row["training_status"] for row in rows} == {"quarantine"}
