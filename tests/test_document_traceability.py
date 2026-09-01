from tools.validate_repo import (
    check_adrs_and_traceability,
    check_capability_evaluations,
    check_decision_consistency,
    check_manifest_integrity,
)


def test_accepted_decisions_are_traceable():
    assert check_adrs_and_traceability().status == "PASS"


def test_every_capability_evaluation_has_a_gate():
    assert check_capability_evaluations().status == "PASS"


def test_accepted_adrs_and_source_documents_share_decision_anchors():
    assert check_decision_consistency().status == "PASS"


def test_release_manifest_hashes_and_adr_inventory_are_current():
    assert check_manifest_integrity().status == "PASS"
