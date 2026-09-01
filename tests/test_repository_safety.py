from tools.validate_repo import check_remote_visibility, check_repository_safety


def test_no_forbidden_or_secret_candidate_files():
    assert all(check.status == "PASS" for check in check_repository_safety())


def test_remote_is_private_when_configured():
    assert check_remote_visibility().status in {"PASS", "SKIP"}
