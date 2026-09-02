PYTHON ?= $(shell if [ -x .venv/bin/python ]; then printf '%s' .venv/bin/python; else command -v python3; fi)

.PHONY: validate audit-remote audit-release report test

validate:
	$(PYTHON) tools/validate_repo.py
	$(PYTHON) -m pytest -q

audit-remote:
	$(PYTHON) tools/audit_remote.py

audit-release:
	@test -n "$(TAG)" || (echo "TAG is required, for example: make audit-release TAG=v0.0.1"; exit 2)
	$(PYTHON) tools/audit_release.py --tag "$(TAG)"

test:
	$(PYTHON) -m pytest

report:
	$(PYTHON) tools/build_validation_report.py
