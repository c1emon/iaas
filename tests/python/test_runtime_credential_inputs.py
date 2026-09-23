"""The runtime consumes inputs, independent of caller-side secret acquisition."""

import json
import subprocess
from types import SimpleNamespace
import stat

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.k3s_automation.secrets import load_protected_environment_json
from iaas_automation.pve_inventory.pve_api.runtime import load_api_runtime_config
from iaas_automation.runtime_execution import credentials


def test_root_owned_public_trust_file_is_accepted_but_root_owned_secret_is_rejected(monkeypatch):
    class RootOwnedFile:
        def stat(self):
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_size=1)

    monkeypatch.setattr(credentials.os, "getuid", lambda: 501)
    path = RootOwnedFile()
    credentials.protected_file(path, secret=False)
    with pytest.raises(ValidationError, match="owned by the execution user"):
        credentials.protected_file(path)


def test_credentials_need_no_provider_process_or_token(monkeypatch, tmp_path):
    def unexpected_process(*args, **kwargs):
        raise AssertionError("credential input loading must not execute a provider")

    monkeypatch.setattr(subprocess, "run", unexpected_process)
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    config = load_api_runtime_config({
        "TF_VAR_pve_endpoint": "https://pve.example.invalid:8006",
        "TF_VAR_pve_api_username": "pve-ops@pve",
        "TF_VAR_pve_api_token_id": "opentofu",
        "TF_VAR_pve_api_token_secret": "synthetic-input",
    })
    assert config.api_token_secret == "synthetic-input"
    # The same resolved input can be supplied by op run or a traditional Secret.
    path = tmp_path / "runtime.json"
    reference = "op://example/cluster/token"
    path.write_text(json.dumps({reference: "synthetic-input"}))
    path.chmod(0o600)
    channel = load_protected_environment_json(path)
    assert channel.resolve(reference).status == "resolved"
    assert "synthetic-input" not in repr(channel)
    path.chmod(0o644)
    with pytest.raises(ValidationError, match="restrictive permissions"):
        load_protected_environment_json(path)
    with pytest.raises(ValidationError, match="missing required"):
        load_api_runtime_config({})
