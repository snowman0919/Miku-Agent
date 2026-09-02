from tools.validate_repo import check_local_git_invariants, check_repository_safety


def test_no_forbidden_or_secret_candidate_files():
    assert all(check.status == "PASS" for check in check_repository_safety())


def test_local_git_and_historical_tag_invariants():
    assert check_local_git_invariants().status == "PASS"
