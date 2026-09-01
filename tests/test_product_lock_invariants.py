from tools.validate_repo import ROOT, load_data


def test_fixed_technology_and_scope_boundaries():
    lock = load_data(ROOT / "spec" / "product-lock.yaml")
    assert lock["repository"] == {
        "visibility": "private", "public_distribution": False, "data_in_git": False,
        "weights_in_git": False, "media_assets_in_git": False, "secrets_in_git": False,
    }
    assert lock["execution"]["local_only"] is True
    assert lock["execution"]["server_allowed_from"] == "0.1.0"
    assert lock["model"]["codec_frozen"] is True
    assert lock["transport"]["webrtc"] is False
    assert lock["auth"]["provider"] == "clerk"
    assert (lock["auth"]["signup_gate"], lock["auth"]["runtime_gate"]) == ("clerk_allowlist", "backend_access_grant")
    assert lock["memory"]["namespace"] == "user_and_character"
    assert (lock["clients"]["mobile"], lock["clients"]["desktop"]) == ("flutter", "unity")
    assert lock["codex"]["privileged"] is False
    assert lock["codex"]["host_docker_socket"] is False

