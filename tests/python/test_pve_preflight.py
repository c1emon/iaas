"""Tests for the explicit online PVE preflight command."""

from __future__ import annotations

import json
from email.message import Message
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from iaas_automation.common.io import load_yaml
from iaas_automation.pve_inventory.inventory.model import build_model
from iaas_automation.pve_inventory.checks.preflight.api import ProxmoxAPI
from iaas_automation.pve_inventory.checks.preflight.model import derive_expected_resources
from iaas_automation.pve_inventory.checks.results import CheckResult, has_failures, render_report
from iaas_automation.pve_inventory.inventory.validation.cluster import validate_cluster
from iaas_automation.pve_inventory.inventory.validation.vm import validate_vms
from iaas_automation.pve_inventory.preflight import run_preflight


ROOT = Path(__file__).resolve().parents[2]
CLUSTER_PATH = ROOT / "environments" / "astra" / "inventory" / "pve-cluster.yml"
VMS_PATH = ROOT / "environments" / "astra" / "inventory" / "vms.yml"
MAKEFILE_PATH = ROOT / "Makefile"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "offline-validation.yml"


class _FakeResponse:
    def __init__(self, payload: Any):
        self._payload = json.dumps({"data": payload}).encode("utf-8")

    def read(self) -> bytes:
        return self._payload


def _fake_opener(routes: dict[str, Any]):
    def opener(request: Any, **_: Any) -> _FakeResponse:
        url = request.full_url
        if url not in routes:
            raise AssertionError(f"unexpected API request: {url}")
        payload = routes[url]
        if isinstance(payload, Exception):
            raise payload
        return _FakeResponse(payload)

    return opener


def _cluster_model() -> dict[str, Any]:
    cluster = validate_cluster(load_yaml(CLUSTER_PATH))
    return build_model(cluster, validate_vms(load_yaml(VMS_PATH), cluster))


def test_expected_resources_derive_from_validated_model() -> None:
    expected = derive_expected_resources(_cluster_model())

    assert expected.required_nodes == {"cohe"}
    assert expected.optional_nodes == {"node3"}
    assert expected.bridges_by_node["cohe"] == {"br_dev", "br_prod"}
    assert {item["datastore"] for item in expected.storage_by_node["cohe"]} == {"images", "memory"}
    assert {item["vmid"] for item in expected.templates} == {9001}
    assert {item["vmid"] for item in expected.vmid_expectations} == {500, 1000, 501}
    assert expected.mappings_by_node["cohe"] == {"iGpu0"}
    assert expected.optional_mapping_nodes["iGpu0"] == {"node3"}


def test_result_aggregation_and_exit_semantics() -> None:
    results = [
        CheckResult("PASS", "pass.one", "ok"),
        CheckResult("WARN", "warn.one", "careful"),
        CheckResult("SKIP", "skip.one", "not run"),
    ]
    assert has_failures(results) is False
    report = render_report(results)
    assert "summary: 1 pass, 1 warn, 0 fail, 1 skip" in report

    results.append(CheckResult("FAIL", "fail.one", "bad"))
    assert has_failures(results) is True


def test_fake_api_checks_cover_nodes_storage_templates_vmids_and_pci(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _cluster_model()
    cluster = model["cluster"]
    vms = {vm["name"]: vm for vm in model["vms"]}
    routes = {
        "https://pve.example.invalid/api2/json/nodes": [{"node": "cohe"}],
        "https://pve.example.invalid/api2/json/nodes/cohe/network": [
            {"iface": "br_dev", "type": "bridge"},
            {"iface": "br_prod", "type": "bridge"},
        ],
        "https://pve.example.invalid/api2/json/nodes/cohe/storage": [
            {"storage": "images", "content": "iso,import,snippets"},
            {"storage": "memory", "content": "images"},
        ],
        "https://pve.example.invalid/api2/json/cluster/resources?type=vm": [
            {"vmid": 9001, "node": "cohe", "name": "debian-13-tmpl-20260616", "template": True},
            {"vmid": 500, "node": "cohe", "name": "dev-web-01", "template": False},
            {"vmid": 1000, "node": "cohe", "name": "prod-app-01", "template": False},
        ],
        "https://pve.example.invalid/api2/json/nodes/cohe/qemu/500/config": {
            "tags": ",".join(["managed-by-opentofu", vms["dev-web-01"]["lifecycle_class"], vms["dev-web-01"]["nics"][0]["network"]["name"], *vms["dev-web-01"]["tags"]]),
            "description": "Managed by OpenTofu for astra-pve",
        },
        "https://pve.example.invalid/api2/json/nodes/cohe/qemu/1000/config": {
            "tags": ",".join(["managed-by-opentofu", vms["prod-app-01"]["lifecycle_class"], vms["prod-app-01"]["nics"][0]["network"]["name"], *vms["prod-app-01"]["tags"]]),
            "description": "Managed by OpenTofu for astra-pve",
        },
        "https://pve.example.invalid/api2/json/cluster/mapping/pci": [{"name": "iGpu0", "nodes": [{"node": "cohe"}]}],
    }
    api = ProxmoxAPI(
        endpoint="https://pve.example.invalid",
        api_username="pve-ops@pve",
        api_token_id="opentofu",
        api_token_secret="super-secret",
        insecure=True,
        opener=_fake_opener(routes),
    )

    results = run_preflight(CLUSTER_PATH, VMS_PATH, environ={}, api_client=api, ssh_runner=lambda *_args, **_kwargs: pytest.fail("SSH runner should not be used when context is absent"))

    report = render_report(results)
    assert "FAIL" not in report
    assert "SKIP ssh.context" in report
    assert "node3" in report


def test_api_auth_failure_is_reported_without_secret_leakage() -> None:
    secret = "super-secret-token"
    headers = Message()
    unauthorized = urllib.error.HTTPError(
        url="https://pve.example.invalid/api2/json/nodes",
        code=401,
        msg="Unauthorized",
        hdrs=headers,
        fp=None,
    )
    api = ProxmoxAPI(
        endpoint="https://pve.example.invalid",
        api_username="pve-ops@pve",
        api_token_id="opentofu",
        api_token_secret=secret,
        insecure=True,
        opener=_fake_opener({"https://pve.example.invalid/api2/json/nodes": unauthorized}),
    )

    results = run_preflight(CLUSTER_PATH, VMS_PATH, environ={}, api_client=api)
    report = render_report(results)

    assert has_failures(results) is True
    assert secret not in report
    assert "HTTP 401" in report


@pytest.mark.parametrize(
    ("ssh_host", "ssh_user", "returncode", "severity"),
    [
        (None, None, 0, "SKIP"),
        ("cohe", "pve-ops", 0, "PASS"),
        ("cohe", "pve-ops", 127, "FAIL"),
    ],
)
def test_ssh_adjuncts_are_optional_and_read_only(ssh_host: str | None, ssh_user: str | None, returncode: int, severity: str) -> None:
    routes = {
        "https://pve.example.invalid/api2/json/nodes": [{"node": "cohe"}],
        "https://pve.example.invalid/api2/json/nodes/cohe/network": [
            {"iface": "br_dev", "type": "bridge"},
            {"iface": "br_prod", "type": "bridge"},
        ],
        "https://pve.example.invalid/api2/json/nodes/cohe/storage": [
            {"storage": "images", "content": "iso,import,snippets"},
            {"storage": "memory", "content": "images"},
        ],
        "https://pve.example.invalid/api2/json/cluster/resources?type=vm": [
            {"vmid": 9001, "node": "cohe", "name": "debian-13-tmpl-20260616", "template": True},
        ],
        "https://pve.example.invalid/api2/json/cluster/mapping/pci": [],
        "https://pve.example.invalid/api2/json/cluster/mapping/pci/iGpu0": {"name": "iGpu0", "nodes": [{"node": "cohe"}]},
    }
    api = ProxmoxAPI(
        endpoint="https://pve.example.invalid",
        api_username="pve-ops@pve",
        api_token_id="opentofu",
        api_token_secret="secret",
        insecure=True,
        opener=_fake_opener(routes),
    )
    env = {
        "TF_VAR_pve_endpoint": "https://pve.example.invalid",
        "TF_VAR_pve_api_username": "pve-ops@pve",
        "TF_VAR_pve_api_token_id": "opentofu",
        "TF_VAR_pve_api_token_secret": "secret",
    }
    if ssh_host:
        env["PVE_HOST"] = ssh_host
    if ssh_user:
        env["PVE_SSH_USER"] = ssh_user

    ssh_calls: list[list[str]] = []

    def runner(command: list[str], **_: Any):
        ssh_calls.append(command)
        return type("Completed", (), {"returncode": returncode, "stdout": "", "stderr": "wrapper missing" if returncode else ""})()

    results = run_preflight(CLUSTER_PATH, VMS_PATH, environ=env, api_client=api, ssh_runner=runner)
    report = render_report(results)

    if severity == "SKIP":
        assert not ssh_calls
        assert any(result.severity == "SKIP" and result.check_id == "ssh.context" for result in results)
    else:
        assert ssh_calls
        assert any(result.severity == severity for result in results if result.check_id.startswith("ssh.wrapper."))
        assert all("--help" in " ".join(call) for call in ssh_calls)
    if severity == "SKIP":
        assert "SSH adjunct checks skipped" in report


def test_make_check_and_offline_ci_do_not_invoke_preflight() -> None:
    make_text = MAKEFILE_PATH.read_text(encoding="utf-8")
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "check: check-generated test lint-yaml typecheck ansible-lint tofu-fmt tofu-validate opnsense-validate" in make_text
    assert "pve-preflight" not in workflow_text
