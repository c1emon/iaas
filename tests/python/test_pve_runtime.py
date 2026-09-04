"""Tests for shared PVE runtime parsing."""

from __future__ import annotations

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.pve_inventory.pve_api.runtime import load_api_runtime_config, load_online_runtime_context, parse_pve_bool


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("true", True), ("yes", True), ("on", True), ("0", False), ("false", False), ("no", False), ("off", False)],
)
def test_parse_pve_bool_accepts_shared_spellings(raw: str, expected: bool) -> None:
    assert parse_pve_bool(raw) is expected


def test_online_runtime_context_keeps_optional_ssh_context_without_api_vars() -> None:
    runtime = load_online_runtime_context({"PVE_HOST": "cohe", "PVE_SSH_USER": "pve-ops"})

    assert runtime.endpoint == ""
    assert runtime.api_username == ""
    assert runtime.api_token_id == ""
    assert runtime.api_token_secret == ""
    assert runtime.ssh_host == "cohe"
    assert runtime.ssh_user == "pve-ops"


def test_missing_api_variables_do_not_leak_secret_values() -> None:
    with pytest.raises(ValidationError) as excinfo:
        load_api_runtime_config(
            {
                "TF_VAR_pve_endpoint": "",
                "TF_VAR_pve_api_username": "pve-ops@pve",
                "TF_VAR_pve_api_token_id": "opentofu",
                "TF_VAR_pve_api_token_secret": "super-secret-token",
            }
        )

    assert "super-secret-token" not in str(excinfo.value)


@pytest.mark.parametrize("loader", [load_api_runtime_config, load_online_runtime_context])
def test_invalid_boolean_error_message_is_shared(loader) -> None:
    env = {
        "TF_VAR_pve_endpoint": "https://pve.example.invalid",
        "TF_VAR_pve_api_username": "pve-ops@pve",
        "TF_VAR_pve_api_token_id": "opentofu",
        "TF_VAR_pve_api_token_secret": "secret",
        "TF_VAR_pve_insecure": "maybe",
    }

    with pytest.raises(ValidationError) as excinfo:
        loader(env)

    assert str(excinfo.value) == "TF_VAR_pve_insecure must be a boolean-like value, got 'maybe'"
