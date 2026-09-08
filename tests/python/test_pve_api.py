"""Tests for the proxmoxer-backed read-only PVE API facade."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from iaas_automation.pve_inventory.pve_api import (
    PveApiAuthenticationError,
    PveApiNotConfiguredError,
    PveReadOnlyApi,
    ReadOnlyPveApi,
)
from iaas_automation.pve_inventory.pve_api.client import HealthApiRuntimeConfig
from iaas_automation.pve_inventory.pve_api import client as pve_client_mod
from iaas_automation.pve_inventory.health import run_health
from iaas_automation.pve_inventory.preflight import run_preflight


ROOT = Path(__file__).resolve().parents[2]
CLUSTER_PATH = ROOT / "tests" / "fixtures" / "environment" / "inventory" / "pve-cluster.yml"
VMS_PATH = ROOT / "tests" / "fixtures" / "environment" / "inventory" / "vms.yml"

class _Leaf:
    def __init__(self, path: str, response: Any, calls: list[tuple[str, str]]) -> None:
        self._path = path
        self._response = response
        self._calls = calls

    def get(self) -> Any:
        self._calls.append((self._path, "get"))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _QemuVm:
    def __init__(self, node: str, vmid: int, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self.status = SimpleNamespace(current=_Leaf(f"nodes/{node}/qemu/{vmid}/status/current", payloads["vm_status"][(node, vmid)], calls))
        self.config = _Leaf(f"nodes/{node}/qemu/{vmid}/config", payloads["vm_config"][(node, vmid)], calls)


class _QemuCollection:
    def __init__(self, node: str, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self._node = node
        self._payloads = payloads
        self._calls = calls

    def get(self) -> Any:
        self._calls.append((f"nodes/{self._node}/qemu", "get"))
        return self._payloads["vms"][self._node]

    def __call__(self, vmid: int) -> _QemuVm:
        return _QemuVm(self._node, vmid, self._payloads, self._calls)


class _NodeCollection:
    def __init__(self, node: str, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self.status = _Leaf(f"nodes/{node}/status", payloads["node_status"][node], calls)
        self.network = _Leaf(f"nodes/{node}/network", payloads.get("node_network", {}).get(node, []), calls)
        self.storage = _Leaf(f"nodes/{node}/storage", payloads["node_storage"][node], calls)
        self.qemu = _QemuCollection(node, payloads, calls)


class _NodesRoot:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self._payloads = payloads
        self._calls = calls

    def get(self) -> Any:
        self._calls.append(("nodes", "get"))
        return self._payloads["nodes"]

    def __call__(self, node: str) -> _NodeCollection:
        return _NodeCollection(node, self._payloads, self._calls)


class _PciMappingRoot:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self._payloads = payloads
        self._calls = calls

    def get(self) -> Any:
        self._calls.append(("cluster/mapping/pci", "get"))
        return self._payloads["pci_mappings"]

    def __call__(self, mapping_name: str) -> _Leaf:
        return _Leaf(f"cluster/mapping/pci/{mapping_name}", self._payloads["pci_mapping_detail"][mapping_name], self._calls)


class _ClusterResources:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self._payloads = payloads
        self._calls = calls

    def get(self, **_: Any) -> Any:
        self._calls.append(("cluster/resources?type=vm", "get"))
        return self._payloads["cluster_vm_resources"]


class _ClusterRoot:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self.status = _Leaf("cluster/status", payloads["cluster_status"], calls)
        self.ha = SimpleNamespace(status=SimpleNamespace(current=_Leaf("cluster/ha/status/current", payloads["ha_status"], calls)))
        self.ceph = SimpleNamespace(status=_Leaf("cluster/ceph/status", payloads["ceph_status"], calls))
        self.resources = _ClusterResources(payloads, calls)
        self.mapping = SimpleNamespace(pci=_PciMappingRoot(payloads, calls))


class _FakeProxmox:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self.cluster = _ClusterRoot(payloads, calls)
        self.nodes = _NodesRoot(payloads, calls)


def _payloads() -> dict[str, Any]:
    return {
        "cluster_status": {"quorate": True},
        "nodes": [{"node": "node-a"}],
        "cluster_vm_resources": [{"vmid": 9001, "node": "node-a", "name": "debian-13-tmpl-20260616", "template": True}],
        "pci_mappings": [{"name": "test-gpu", "nodes": [{"node": "node-a"}]}],
        "pci_mapping_detail": {"test-gpu": {"name": "test-gpu", "nodes": [{"node": "node-a"}]}},
        "node_status": {
            "node-a": {"status": "online"},
        },
        "node_storage": {
            "node-a": [],
        },
        "vms": {
            "node-a": [],
        },
        "vm_status": {},
        "vm_config": {},
        "ha_status": [],
        "ceph_status": {"health": "HEALTH_OK"},
    }


def test_read_only_api_uses_get_only_named_methods() -> None:
    calls: list[tuple[str, str]] = []
    payloads = _payloads()
    payloads["cluster_status"] = [{"quorate": True}]
    payloads["nodes"] = [{"node": "node-a"}]
    payloads["cluster_vm_resources"] = [{"vmid": 9001, "node": "node-a", "name": "debian-13-tmpl-20260616", "template": True}]
    payloads["pci_mappings"] = [{"name": "test-gpu", "nodes": [{"node": "node-a"}]}]
    payloads["pci_mapping_detail"] = {"test-gpu": {"name": "test-gpu", "nodes": [{"node": "node-a"}]}}
    payloads["node_status"]["node-a"] = {"status": "online"}
    payloads["node_network"] = {"node-a": []}
    payloads["node_storage"]["node-a"] = []
    payloads["vms"]["node-a"] = []
    payloads["ha_status"] = []
    prox = _FakeProxmox(payloads, calls)
    api = ReadOnlyPveApi(HealthApiRuntimeConfig("https://pve.example.invalid", "pve-ops@pve", "opentofu", "secret", True), prox=prox)

    assert not hasattr(api, "prox")
    assert api.cluster_status() == [{"quorate": True}]
    assert api.nodes() == [{"node": "node-a"}]
    assert api.node_status("node-a") == {"status": "online"}
    assert api.node_network("node-a") == []
    assert api.node_storage("node-a") == []
    assert api.cluster_vm_resources() == [{"vmid": 9001, "node": "node-a", "name": "debian-13-tmpl-20260616", "template": True}]
    assert api.vms("node-a") == []
    assert api.pci_mappings() == [{"name": "test-gpu", "nodes": [{"node": "node-a"}]}]
    assert api.pci_mapping_detail("test-gpu") == {"name": "test-gpu", "nodes": [{"node": "node-a"}]}
    assert api.ha_status() == []
    assert api.ceph_status() == {"health": "HEALTH_OK"}

    assert calls == [
        ("cluster/status", "get"),
        ("nodes", "get"),
        ("nodes/node-a/status", "get"),
        ("nodes/node-a/network", "get"),
        ("nodes/node-a/storage", "get"),
        ("cluster/resources?type=vm", "get"),
        ("nodes/node-a/qemu", "get"),
        ("cluster/mapping/pci", "get"),
        ("cluster/mapping/pci/test-gpu", "get"),
        ("cluster/ha/status/current", "get"),
        ("cluster/ceph/status", "get"),
    ]


@pytest.mark.parametrize(
    ("endpoint", "expected_host", "expected_port"),
    [
        ("pve.example.internal", "pve.example.internal", None),
        ("pve.example.internal:8007", "pve.example.internal", 8007),
        ("https://pve.example.internal:8006/api2/json", "pve.example.internal", 8006),
    ],
)
def test_runtime_endpoint_is_normalized_for_proxmoxer(monkeypatch: pytest.MonkeyPatch, endpoint: str, expected_host: str, expected_port: int | None) -> None:
    calls: dict[str, Any] = {}

    class FakeProxmox:
        def __init__(self, host: str, **kwargs: Any) -> None:
            calls["host"] = host
            calls["kwargs"] = kwargs

    monkeypatch.setattr(pve_client_mod, "ProxmoxAPI", FakeProxmox)

    ReadOnlyPveApi(HealthApiRuntimeConfig(endpoint, "pve-ops@pve", "opentofu", "secret", True))

    assert calls["host"] == expected_host
    assert calls["kwargs"].get("port") == expected_port
    assert calls["kwargs"]["user"] == "pve-ops@pve"


def test_client_boundary_redacts_secrets_from_auth_errors() -> None:
    secret = "super-secret-token"

    class FakeAuthenticationError(pve_client_mod.AuthenticationError):
        pass

    class RaisingLeaf:
        def get(self) -> Any:
            raise FakeAuthenticationError(f"invalid token {secret}")

    prox = SimpleNamespace(cluster=SimpleNamespace(status=RaisingLeaf()))
    api = ReadOnlyPveApi(
        HealthApiRuntimeConfig("https://pve.example.invalid", "pve-ops@pve", "opentofu", secret, True),
        prox=prox,
    )

    with pytest.raises(PveApiAuthenticationError) as excinfo:
        api.cluster_status()

    assert secret not in str(excinfo.value)


def test_client_boundary_distinguishes_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResourceException(Exception):
        def __init__(self, message: str, status_code: int = 404) -> None:
            super().__init__(message)
            self.status_code = status_code
            self.content = message

    monkeypatch.setattr(pve_client_mod, "ResourceException", FakeResourceException)

    class RaisingLeaf:
        def get(self) -> Any:
            raise FakeResourceException("not configured")

    prox = SimpleNamespace(cluster=SimpleNamespace(ha=SimpleNamespace(status=SimpleNamespace(current=RaisingLeaf()))))
    api = ReadOnlyPveApi(HealthApiRuntimeConfig("https://pve.example.invalid", "pve-ops@pve", "opentofu", "secret", True), prox=prox)

    with pytest.raises(PveApiNotConfiguredError):
        api.ha_status()


class _SharedFakeApi:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self._payloads = payloads
        self._calls = calls

    def cluster_status(self) -> Any:
        self._calls.append(("cluster/status", "get"))
        return self._payloads["cluster_status"]

    def nodes(self) -> Any:
        self._calls.append(("nodes", "get"))
        return self._payloads["nodes"]

    def node_status(self, node: str) -> Any:
        self._calls.append((f"nodes/{node}/status", "get"))
        return self._payloads["node_status"][node]

    def node_network(self, node: str) -> Any:
        self._calls.append((f"nodes/{node}/network", "get"))
        return self._payloads["node_network"][node]

    def node_storage(self, node: str) -> Any:
        self._calls.append((f"nodes/{node}/storage", "get"))
        return self._payloads["node_storage"][node]

    def cluster_vm_resources(self) -> Any:
        self._calls.append(("cluster/resources?type=vm", "get"))
        return self._payloads["cluster_vm_resources"]

    def vms(self, node: str) -> Any:
        self._calls.append((f"nodes/{node}/qemu", "get"))
        return self._payloads["vms"][node]

    def vm_status(self, node: str, vmid: int) -> Any:
        self._calls.append((f"nodes/{node}/qemu/{vmid}/status/current", "get"))
        return self._payloads["vm_status"][(node, vmid)]

    def vm_config(self, node: str, vmid: int) -> Any:
        self._calls.append((f"nodes/{node}/qemu/{vmid}/config", "get"))
        return self._payloads["vm_config"][(node, vmid)]

    def pci_mappings(self) -> Any:
        self._calls.append(("cluster/mapping/pci", "get"))
        return self._payloads["pci_mappings"]

    def pci_mapping_detail(self, mapping_name: str) -> Any:
        self._calls.append((f"cluster/mapping/pci/{mapping_name}", "get"))
        return self._payloads["pci_mapping_detail"][mapping_name]

    def ha_status(self) -> Any:
        self._calls.append(("cluster/ha/status/current", "get"))
        return self._payloads["ha_status"]

    def ceph_status(self) -> Any:
        self._calls.append(("cluster/ceph/status", "get"))
        return self._payloads["ceph_status"]


def test_shared_fake_client_satisfies_protocol_for_health_and_preflight() -> None:
    calls: list[tuple[str, str]] = []
    payloads = _payloads()
    payloads["cluster_status"] = [{"quorate": True}]
    payloads["nodes"] = [{"node": "node-a", "status": "online"}]
    payloads["node_network"] = {"node-a": [{"iface": "br_dev", "type": "bridge"}, {"iface": "br_prod", "type": "bridge"}]}
    payloads["node_storage"] = {"node-a": [{"storage": "images", "active": True, "usage": 10}, {"storage": "memory", "active": True, "usage": 10}]}
    payloads["cluster_vm_resources"] = [
        {"vmid": 9001, "node": "node-a", "name": "debian-13-tmpl-20260616", "template": True},
        {"vmid": 500, "node": "node-a", "name": "dev-web-01", "template": False},
        {"vmid": 1000, "node": "node-a", "name": "prod-app-01", "template": False},
        {"vmid": 501, "node": "node-a", "name": "media-lab-01", "template": False},
    ]
    payloads["vms"] = {
        "node-a": [
            {"vmid": 9001, "name": "debian-13-tmpl-20260616", "template": True, "status": "stopped"},
            {"vmid": 1000, "name": "prod-app-01", "template": False, "status": "running"},
            {"vmid": 500, "name": "dev-web-01", "template": False, "status": "running"},
            {"vmid": 501, "name": "media-lab-01", "template": False, "status": "running"},
        ]
    }
    payloads["vm_status"] = {
        ("node-a", 9001): {"status": "stopped"},
        ("node-a", 1000): {"status": "running"},
        ("node-a", 500): {"status": "running"},
        ("node-a", 501): {"status": "running"},
    }
    payloads["vm_config"] = {
        ("node-a", 9001): {"template": True},
        ("node-a", 1000): {"template": False, "tags": "managed-by-opentofu"},
        ("node-a", 500): {"template": False, "tags": "managed-by-opentofu"},
        ("node-a", 501): {"template": False, "tags": "managed-by-opentofu"},
    }
    payloads["pci_mappings"] = [{"name": "test-gpu", "nodes": [{"node": "node-a"}]}]
    payloads["pci_mapping_detail"] = {"test-gpu": {"name": "test-gpu", "nodes": [{"node": "node-a"}]}}
    payloads["ha_status"] = []
    payloads["ceph_status"] = {"health": "HEALTH_OK"}

    fake = _SharedFakeApi(payloads, calls)

    assert isinstance(fake, PveReadOnlyApi)
    assert run_health(CLUSTER_PATH, VMS_PATH, environ={}, api_client=fake)
    assert run_preflight(CLUSTER_PATH, VMS_PATH, environ={}, api_client=fake, ssh_runner=lambda *_args, **_kwargs: None)
