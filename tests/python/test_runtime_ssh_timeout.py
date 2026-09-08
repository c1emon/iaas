"""Generic timeout selection and explicit migration errors."""

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.pve_inventory.cloud_init_helpers.ssh import resolve_ssh_timeout


def test_generic_timeout(monkeypatch):
    monkeypatch.delenv("ASTRA_PVE_SSH_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("IAAS_PVE_SSH_TIMEOUT_SECONDS", "12")
    assert resolve_ssh_timeout(None) == 12
    assert resolve_ssh_timeout(5) == 5


def test_legacy_timeout_rejected_even_with_explicit_argument(monkeypatch):
    monkeypatch.setenv("ASTRA_PVE_SSH_TIMEOUT_SECONDS", "12")
    with pytest.raises(ValidationError, match="no longer supported"):
        resolve_ssh_timeout(5)
