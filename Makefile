PYTHON ?= $(shell if [ -x .venv/bin/python ]; then printf '%s' .venv/bin/python; else command -v python3; fi)

.PHONY: validate report test

validate:
	$(PYTHON) tools/build_validation_report.py

test:
	$(PYTHON) -m pytest

report:
	$(PYTHON) tools/build_validation_report.py
