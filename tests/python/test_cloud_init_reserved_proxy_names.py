"""Proxy configuration must never become guest credential material."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from iaas.common.errors import ValidationError
from iaas.common.proxy_names import require_guest_credential_name
from iaas.pve_inventory.cloud_init_helpers import render
from iaas.pve_inventory.inventory.validation.cluster import validate_automation

ROOT = Path(__file__).resolve().parents[2]
TFVARS = ROOT / "tests/fixtures/environment/generated/opentofu/pve.tfvars.json"


@pytest.mark.parametrize("name", ["HTTP_PROXY", "https_proxy", "No_Proxy", "aLl_PrOxY", "ftp_PROXY"])
@pytest.mark.parametrize("field", ["password_env", "public_key_env"])
def test_render_rejects_reserved_names_before_reading_any_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, field: str) -> None:
    payload = json.loads(TFVARS.read_text())
    payload["cluster"]["automation"]["cloud_init"]["users"][-1][field] = name
    tfvars = tmp_path / "pve.tfvars.json"
    tfvars.write_text(json.dumps(payload))
    monkeypatch.setattr(render, "read_required_env", lambda _: pytest.fail("credential value read before conflict rejection"))
    with pytest.raises(ValidationError, match="reserved proxy environment name"):
        render.render_snippets(tfvars, "images")


@pytest.mark.parametrize("field", ["password_env", "public_key_env"])
def test_inventory_and_direct_render_reject_reserved_names(field: str) -> None:
    cluster = json.loads(TFVARS.read_text())["cluster"]
    user = cluster["automation"]["cloud_init"]["users"][0]
    user[field] = "hTtPs_PrOxY"
    with pytest.raises(ValidationError, match="reserved proxy environment name"):
        validate_automation({"cluster": cluster}, cluster["storage_roles"], {}, {})
    with pytest.raises(ValidationError, match="reserved proxy environment name"):
        render.build_cloud_init_user(copy.deepcopy(user), {})


def test_reserved_env_reader_rejects_before_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render.os, "environ", {})
    with pytest.raises(ValidationError, match="reserved proxy environment name"):
        render.read_required_env("ALL_PROXY")
    require_guest_credential_name("PVE_VM_ADMIN_PASSWORD")
