"""Tests for the explicit online PVE health command."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.pve_inventory.health import derive_health_expectations, load_health_runtime_config, render_report, run_health
from scripts.pve_inventory.io import load_yaml
from scripts.pve_inventory.model import build_model
from scripts.pve_inventory.preflight_results import has_failures
from scripts.pve_inventory.validation import validate_cluster, validate_vms
from scripts.pve_inventory.pve_api.errors import PveApiNotConfiguredError, PveApiUnavailableError, PveApiAuthenticationError


ROOT = Path(__file__).resolve().parents[2]
CLUSTER_PATH = ROOT / "inventory" / "pve-cluster.yml"
VMS_PATH = ROOT / "inventory" / "vms.yml"
MAKEFILE_PATH = ROOT / "Makefile"
PVE_MAKEFILE_PATH = ROOT / "infra" / "tofu" / "pve" / "Makefile"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "offline-validation.yml"


class _FakeHealthApi:
    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses

    def _response(self, key: str, subkey: Any | None = None) -> Any:
        value = self._responses[key]
        if subkey is not None:
            value = value[subkey]
        if isinstance(value, Exception):
            raise value
        return value

    def cluster_status(self) -> Any:
        return self._response("cluster_status")

    def nodes(self) -> Any:
        return self._response("nodes")

    def node_status(self, node: str) -> Any:
        return self._response("node_status", node)

    def node_storage(self, node: str) -> Any:
        return self._response("node_storage", node)

    def vms(self, node: str) -> Any:
        return self._response("vms", node)

    def vm_status(self, node: str, vmid: int) -> Any:
        return self._response("vm_status", (node, vmid))

    def vm_config(self, node: str, vmid: int) -> Any:
        return self._response("vm_config", (node, vmid))

    def ha_status(self) -> Any:
        return self._response("ha_status")

    def ceph_status(self) -> Any:
        return self._response("ceph_status")


def _model() -> dict[str, Any]:
    cluster = validate_cluster(load_yaml(CLUSTER_PATH))
    return build_model(cluster, validate_vms(load_yaml(VMS_PATH), cluster))


def _baseline_api(**overrides: Any) -> _FakeHealthApi:
    responses: dict[str, Any] = {
        "cluster_status": [{"quorate": True}],
        "nodes": [{"node": "cohe", "status": "online"}],
        "node_status": {
            "cohe": {
                "cpu": 3.64,
                "cpuinfo": {"cpus": 4},
                "memory": {"used": 1_000, "total": 4_000},
                "rootfs": {"used": 1_000, "total": 4_000},
            },
        },
        "node_storage": {
            "cohe": [
                {"storage": "images", "active": True, "usage": 10},
                {"storage": "memory", "active": True, "usage": 10},
            ],
        },
        "vms": {
            "cohe": [
                {"vmid": 9001, "name": "debian-13-tmpl-20260616", "template": True, "status": "stopped"},
                {"vmid": 1000, "name": "prod-app-01", "template": False, "status": "running"},
                {"vmid": 500, "name": "dev-web-01", "template": False, "status": "running"},
                {"vmid": 501, "name": "media-lab-01", "template": False, "status": "running"},
            ],
        },
        "vm_status": {
            ("cohe", 9001): {"status": "stopped"},
            ("cohe", 1000): {"status": "running"},
            ("cohe", 500): {"status": "running"},
            ("cohe", 501): {"status": "running"},
        },
        "vm_config": {
            ("cohe", 9001): {"template": True},
            ("cohe", 1000): {"template": False},
            ("cohe", 500): {"template": False},
            ("cohe", 501): {"template": False},
        },
        "ha_status": [],
        "ceph_status": PveApiNotConfiguredError("not configured"),
    }
    for key, value in overrides.items():
        responses[key] = value
    return _FakeHealthApi(responses)


def _results_by_id(results: list[Any]) -> dict[str, Any]:
    return {result.check_id: result for result in results}


def test_health_expectations_derive_from_inventory_model() -> None:
    expectations = derive_health_expectations(_model())

    assert expectations.required_nodes == {"cohe"}
    assert expectations.optional_nodes == {"node3"}
    assert set(expectations.templates) == {"debian_13_genericcloud"}
    assert {vm["name"] for vm in expectations.declared_vms} == {"dev-web-01", "prod-app-01", "media-lab-01"}
    assert expectations.required_datastores_by_node["cohe"] == {"images", "memory"}


def test_health_passes_quorum_and_marks_optional_node_missing_while_flagging_capacity() -> None:
    api = _baseline_api(
        node_status={
            "cohe": {
                "cpu": 3.64,
                "cpuinfo": {"cpus": 4},
                "memory": {"used": 3_700, "total": 4_000},
                "rootfs": {"used": 3_960, "total": 4_000},
            }
        },
    )

    results = run_health(environ={}, api_client=api)
    result_map = _results_by_id(results)

    assert result_map["api.reachability"].severity == "PASS"
    assert result_map["cluster.quorum"].severity == "PASS"
    assert result_map["node.optional.node3"].severity == "WARN"
    assert result_map["node.capacity.cohe.cpu"].severity == "WARN"
    assert result_map["node.capacity.cohe.memory"].severity == "WARN"
    assert result_map["node.capacity.cohe.rootfs"].severity == "FAIL"


@pytest.mark.parametrize(
    ("storage", "expected_severity"),
    [
        ([{"storage": "images", "active": True, "usage": 96}, {"storage": "memory", "active": True, "usage": 10}], "FAIL"),
        ([{"storage": "images", "active": False, "usage": 10}, {"storage": "memory", "active": True, "usage": 10}], "FAIL"),
        ([{"storage": "images", "active": True, "usage": 86}, {"storage": "memory", "active": True, "usage": 10}], "WARN"),
    ],
)
def test_health_checks_required_storage_presence_activation_and_usage(storage: list[dict[str, Any]], expected_severity: str) -> None:
    api = _baseline_api(node_storage={"cohe": storage})
    results = run_health(environ={}, api_client=api)
    assert _results_by_id(results)["storage.cohe.images"].severity == expected_severity


def test_health_fails_for_missing_referenced_template_and_non_template_records() -> None:
    api = _baseline_api(
        vms={"cohe": [{"vmid": 1000, "name": "prod-app-01", "template": False, "status": "running"}]},
        vm_status={("cohe", 1000): {"status": "stopped"}},
        vm_config={("cohe", 9001): {"template": False}},
    )

    results = run_health(environ={}, api_client=api)
    result_map = _results_by_id(results)

    assert result_map["template.debian_13_genericcloud"].severity == "FAIL"
    assert result_map["vm.dev-web-01"].severity == "SKIP"
    assert result_map["vm.media-lab-01"].severity == "SKIP"
    assert result_map["vm.prod-app-01"].severity == "WARN"


@pytest.mark.parametrize(
    ("ha_status", "expected_severity"),
    [
        (PveApiNotConfiguredError("missing"), "SKIP"),
        ([], "SKIP"),
        ([{"sid": "vm:1000", "state": "error"}], "FAIL"),
    ],
)
def test_health_handles_ha_skip_empty_and_unhealthy_states(ha_status: Any, expected_severity: str) -> None:
    api = _baseline_api(ha_status=ha_status)
    results = run_health(environ={}, api_client=api)
    assert _results_by_id(results)["ha"].severity == expected_severity


@pytest.mark.parametrize(
    ("ceph_status", "expected_severity"),
    [
        (PveApiUnavailableError("missing"), "SKIP"),
        ({"health": "HEALTH_OK"}, "PASS"),
        ({"health": {"status": "HEALTH_OK"}}, "PASS"),
        ({"status": "HEALTH_OK"}, "PASS"),
        ({"health": "HEALTH_WARN"}, "WARN"),
        ({"health": "HEALTH_ERR"}, "FAIL"),
    ],
)
def test_health_handles_ceph_skip_pass_warn_and_fail(ceph_status: Any, expected_severity: str) -> None:
    api = _baseline_api(ceph_status=ceph_status)
    results = run_health(environ={}, api_client=api)
    assert _results_by_id(results)["ceph"].severity == expected_severity


def test_health_reports_do_not_leak_secrets() -> None:
    secret = "super-secret-token"

    class FailingApi:
        _api_token_secret = secret

        def redact_operator_text(self, text: str) -> str:
            return text.replace(secret, "<redacted>")

        def cluster_status(self) -> Any:
            raise PveApiAuthenticationError(f"invalid token {secret}")

    results = run_health(environ={}, api_client=FailingApi())
    report = render_report(results)

    assert secret not in report
    assert has_failures(results) is True


def test_offline_guards_keep_pve_health_outside_make_check_and_ci() -> None:
    make_text = MAKEFILE_PATH.read_text(encoding="utf-8")
    pve_make_text = PVE_MAKEFILE_PATH.read_text(encoding="utf-8")
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "check: check-generated test lint-yaml tofu-fmt tofu-validate" in make_text
    assert "pve-health" in make_text
    assert "validate: validate-source validate-ansible check-generated init" in pve_make_text
    assert "check-pve: pve-preflight" in pve_make_text
    assert "pve-health" not in workflow_text
    assert "health.py" not in workflow_text


def test_health_runtime_config_uses_api_only_tf_vars() -> None:
    runtime = load_health_runtime_config(
        {
            "TF_VAR_pve_endpoint": "https://pve.example.invalid",
            "TF_VAR_pve_api_username": "pve-ops@pve",
            "TF_VAR_pve_api_token_id": "opentofu",
            "TF_VAR_pve_api_token_secret": "secret",
            "TF_VAR_pve_insecure": "true",
        }
    )

    assert runtime.endpoint == "https://pve.example.invalid"
    assert runtime.insecure is True
