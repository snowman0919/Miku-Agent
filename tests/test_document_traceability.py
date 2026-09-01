from tools.validate_repo import check_adrs_and_traceability, check_capability_evaluations


def test_accepted_decisions_are_traceable():
    assert check_adrs_and_traceability().status == "PASS"


def test_every_capability_evaluation_has_a_gate():
    assert check_capability_evaluations().status == "PASS"

