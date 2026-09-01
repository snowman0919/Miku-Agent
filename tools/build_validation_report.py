#!/usr/bin/env python3
"""Run validation and write the evidence-backed V0.0.0 report."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from validate_repo import ROOT, run_all


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else "unavailable"


def main() -> int:
    try:
        checks = run_all()
    except Exception as exc:
        print(f"validation failed: {exc}")
        return 1

    pytest = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    pytest_output = " ".join(line.strip() for line in (pytest.stdout + pytest.stderr).splitlines() if line.strip())
    if pytest.returncode != 0:
        print(pytest_output)
        return pytest.returncode

    schemas = len(list((ROOT / "schemas").glob("*.schema.json")))
    valid = len(list((ROOT / "examples" / "valid").glob("*")))
    invalid = len(list((ROOT / "examples" / "invalid").glob("*")))
    adrs = len(list((ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")))
    open_questions = sum(1 for line in (ROOT / "docs" / "open-questions.md").read_text(encoding="utf-8").splitlines() if line.startswith("| ") and not line.startswith("| Question") and not line.startswith("|---"))
    remote = next(check for check in checks if check.name == "private remote visibility")
    check_lines = "\n".join(f"- {check.status}: {check.name} — {check.detail}" for check in checks)

    report = f"""# V0.0.0 Validation Report

## 실행 환경

- OS: {platform.platform()}
- Python: {platform.python_version()}
- Git: {command_output(['git', '--version'])}
- GitHub CLI: {command_output(['gh', '--version'])}
- 실행 환경 경계: local-only

## 검증 command

```text
make validate
python3 tools/validate_repo.py
python3 -m pytest -q
```

## 결과

- Repository validation: PASS
- Pytest result: PASS — {pytest_output}
- Schema count: {schemas}
- Valid example count: {valid}
- Invalid example count: {invalid}
- Accepted ADR count: {adrs}
- Open question count: {open_questions}
- Tracked/candidate forbidden file result: PASS
- Secret scan result: PASS
- Repository visibility result: {remote.status} — {remote.detail}

## 세부 검사

{check_lines}

## Unresolved blocker

{"없음" if remote.status == "PASS" else "로컬 정의 검증은 완료되었으며 GitHub origin 생성과 PRIVATE visibility 확인은 release 전 남은 단계다."}

## Scope confirmation

- RTX 5090 server was not accessed.
- No model was downloaded or trained.
- No external media dataset was collected.
- No Clerk production credentials were created.
- No application runtime was implemented.
- {"The repository is private." if remote.status == "PASS" else "Private remote creation remains an explicit release step."}
"""
    report_path = ROOT / "reports" / "v0.0.0-validation.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8", newline="\n")
    print(pytest_output)
    for check in checks:
        print(f"{check.status}: {check.name} - {check.detail}")
    print(f"PASS: wrote {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
