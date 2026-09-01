from pathlib import Path

from tools.validate_repo import ROOT, INVALID_EXPECTATIONS, load_data, validate_instance


def test_all_valid_examples_and_each_schema_contract():
    paths = sorted((ROOT / "examples" / "valid").glob("*"))
    seen = set()
    for path in paths:
        name = path.name.rsplit(".", 1)[0]
        assert validate_instance(name, load_data(path)) == []
        seen.add(name)
    assert seen == set(__import__("tools.validate_repo", fromlist=["SCHEMA_TARGETS"]).SCHEMA_TARGETS)


def test_architecture_invalid_examples_fail_for_intended_reason():
    for filename, expected in INVALID_EXPECTATIONS.items():
        path = ROOT / "examples" / "invalid" / filename
        name = filename.split(".", 1)[0]
        errors = validate_instance(name, load_data(path))
        assert errors
        assert expected in " | ".join(errors)

