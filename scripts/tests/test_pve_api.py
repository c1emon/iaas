"""Tests for the proxmoxer-backed read-only PVE API facade."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from scripts.pve_inventory.pve_api import (
    PveApiAuthenticationError,
    PveApiNotConfiguredError,
    ReadOnlyPveApi,
)
from scripts.pve_inventory.pve_api.client import HealthApiRuntimeConfig
from scripts.pve_inventory.pve_api import client as pve_client_mod


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


class _ClusterRoot:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self.status = _Leaf("cluster/status", payloads["cluster_status"], calls)
        self.ha = SimpleNamespace(status=SimpleNamespace(current=_Leaf("cluster/ha/status/current", payloads["ha_status"], calls)))
        self.ceph = SimpleNamespace(status=_Leaf("cluster/ceph/status", payloads["ceph_status"], calls))


class _FakeProxmox:
    def __init__(self, payloads: dict[str, Any], calls: list[tuple[str, str]]) -> None:
        self.cluster = _ClusterRoot(payloads, calls)
        self.nodes = _NodesRoot(payloads, calls)


def _payloads() -> dict[str, Any]:
    return {
        "cluster_status": {"quorate": True},
        "nodes": [{"node": "cohe"}],
        "node_status": {
            "cohe": {"status": "online"},
        },
        "node_storage": {
            "cohe": [],
        },
        "vms": {
            "cohe": [],
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
    payloads["nodes"] = [{"node": "cohe"}]
    payloads["node_status"]["cohe"] = {"status": "online"}
    payloads["node_storage"]["cohe"] = []
    payloads["vms"]["cohe"] = []
    payloads["ha_status"] = []
    prox = _FakeProxmox(payloads, calls)
    api = ReadOnlyPveApi(HealthApiRuntimeConfig("https://pve.example.invalid", "pve-ops@pve", "opentofu", "secret", True), prox=prox)

    assert not hasattr(api, "prox")
    assert api.cluster_status() == [{"quorate": True}]
    assert api.nodes() == [{"node": "cohe"}]
    assert api.node_status("cohe") == {"status": "online"}
    assert api.node_storage("cohe") == []
    assert api.vms("cohe") == []
    assert api.ha_status() == []
    assert api.ceph_status() == {"health": "HEALTH_OK"}

    assert calls == [
        ("cluster/status", "get"),
        ("nodes", "get"),
        ("nodes/cohe/status", "get"),
        ("nodes/cohe/storage", "get"),
        ("nodes/cohe/qemu", "get"),
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

    class FakeResourceException(pve_client_mod.ResourceException):
        def __init__(self, message: str, status_code: int = 401) -> None:
            super().__init__(message)
            self.status_code = status_code
            self.content = message

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
