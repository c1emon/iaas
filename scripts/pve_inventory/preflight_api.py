"""PVE API client and API-first readiness checks.

The implementation intentionally uses stdlib urllib/ssl so the online check
adds no new dependency surface and can stay fully read-only.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, cast

from .preflight_config import RuntimeConfig
from .preflight_model import DerivedResources
from .preflight_results import CheckResult


def _redact(text: str, secrets: list[str]) -> str:
    """Best-effort secret scrubbing for operator-visible messages."""
    redacted = text
    for secret in sorted({value for value in secrets if value}, key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")
    return redacted


def _normalize_string_list(value: Any) -> set[str]:
    """Treat PVE comma-separated fields and lists as the same content set."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {item.strip() for item in value.split(",") if item.strip()}
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()


def _pve_storage_content_names(content: set[str]) -> set[str]:
    """Translate repository storage-role vocabulary to PVE API content names.

    The inventory model uses ``disk`` to describe a VM disk storage role because
    that is the operator-facing purpose. PVE exposes that same capability as
    ``images`` in ``/nodes/{node}/storage`` content lists.
    """
    mapped = set(content)
    if "disk" in mapped:
        mapped.remove("disk")
        mapped.add("images")
    return mapped


def _api_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [cast(dict[str, Any], item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [cast(dict[str, Any], value)]
    return []


@dataclass(frozen=True)
class ProxmoxAPI:
    """Tiny GET-only JSON client for the PVE API token endpoint."""
    endpoint: str
    api_username: str
    api_token_id: str
    api_token_secret: str
    insecure: bool = False
    timeout: int = 15
    opener: Callable[..., Any] = urllib.request.urlopen
    base_url: str = field(init=False, default="")

    def __post_init__(self) -> None:
        # Proxmox token auth is sent as the standard API token header.
        base = self.endpoint.rstrip("/")
        if not base.endswith("/api2/json"):
            base = f"{base}/api2/json"
        object.__setattr__(self, "base_url", base)

    def _request(self, path: str) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"PVEAPIToken={self.api_username}!{self.api_token_id}={self.api_token_secret}"},
            method="GET",
        )
        context = ssl._create_unverified_context() if self.insecure else ssl.create_default_context()
        return self.opener(request, context=context, timeout=self.timeout)

    def get_json(self, path: str) -> Any:
        """Fetch and decode a JSON API response without mutating state."""
        try:
            response = self._request(path)
            payload = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            detail = f"HTTP {exc.code}"
            if body:
                detail = f"{detail}: {body.strip()}"
            raise RuntimeError(detail) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc
        except OSError as exc:
            raise RuntimeError(str(exc)) from exc

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON response: {exc}") from exc

        if isinstance(decoded, dict) and "data" in decoded:
            return decoded["data"]
        return decoded


def create_api_client(runtime: RuntimeConfig) -> ProxmoxAPI:
    """Build the default client from normalized runtime config."""
    return ProxmoxAPI(
        endpoint=runtime.endpoint,
        api_username=runtime.api_username,
        api_token_id=runtime.api_token_id,
        api_token_secret=runtime.api_token_secret,
        insecure=runtime.insecure,
    )


def _emit(results: list[CheckResult], severity: str, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=cast(Any, severity), check_id=check_id, message=message))


def _node_index(client: ProxmoxAPI, results: list[CheckResult], secrets: list[str]) -> set[str] | None:
    """Load node inventory first; later checks only run when auth reached."""
    try:
        nodes = _api_items(client.get_json("/nodes"))
    except RuntimeError as exc:
        _emit(results, "FAIL", "api.nodes", _redact(f"PVE API authentication/reachability failed: {exc}", secrets))
        return None
    node_names = {str(node.get("node")) for node in nodes if node.get("node")}
    _emit(results, "PASS", "api.nodes", f"PVE API reachable; discovered {len(node_names)} node(s)")
    return node_names


def _check_required_nodes(expected: DerivedResources, node_names: set[str], results: list[CheckResult]) -> set[str]:
    """Mark used nodes as required and declared placeholders as warnings."""
    present_required: set[str] = set()
    for node in sorted(expected.required_nodes):
        if node in node_names:
            present_required.add(node)
            _emit(results, "PASS", f"model.node.{node}", f"required node {node} is present")
        else:
            _emit(results, "FAIL", f"model.node.{node}", f"required node {node} is missing")
    for node in sorted(expected.optional_nodes):
        if node not in node_names:
            _emit(results, "WARN", f"model.node.optional.{node}", f"declared-but-unused placeholder node {node} is unavailable")
        else:
            _emit(results, "PASS", f"model.node.optional.{node}", f"unused declared node {node} is present")
    return present_required


def _check_bridges(client: ProxmoxAPI, expected: DerivedResources, present_nodes: set[str], results: list[CheckResult], secrets: list[str]) -> None:
    """Check only bridges needed by VMs on the nodes that are actually used."""
    for node in sorted(present_nodes):
        required = sorted(expected.bridges_by_node.get(node, set()))
        if not required:
            continue
        try:
            entries = _api_items(client.get_json(f"/nodes/{urllib.parse.quote(node)}/network"))
        except RuntimeError as exc:
            _emit(results, "FAIL", f"api.network.{node}", _redact(f"unable to read node network configuration: {exc}", secrets))
            continue
        available = {
            str(item.get("iface") or item.get("bridge") or item.get("name"))
            for item in entries
            if item.get("type") in {"bridge", "bridgeport", "network"} or item.get("bridge") or item.get("iface")
        }
        for bridge in required:
            if bridge in available:
                _emit(results, "PASS", f"api.bridge.{node}.{bridge}", f"bridge {bridge} is available on {node}")
            else:
                _emit(results, "FAIL", f"api.bridge.{node}.{bridge}", f"required bridge {bridge} is missing on {node}")


def _check_storage(client: ProxmoxAPI, expected: DerivedResources, present_nodes: set[str], results: list[CheckResult], secrets: list[str]) -> None:
    """Verify the storage roles required by VMs, templates, and snippets."""
    for node in sorted(present_nodes):
        required = expected.storage_by_node.get(node, [])
        if not required:
            continue
        try:
            entries = _api_items(client.get_json(f"/nodes/{urllib.parse.quote(node)}/storage"))
        except RuntimeError as exc:
            _emit(results, "FAIL", f"api.storage.{node}", _redact(f"unable to read node storage configuration: {exc}", secrets))
            continue
        storage_index = {str(item.get("storage")): item for item in entries if item.get("storage")}
        for requirement in required:
            storage = storage_index.get(requirement["datastore"])
            if storage is None:
                _emit(results, "FAIL", f"api.storage.{node}.{requirement['role']}", f"required storage datastore {requirement['datastore']} is missing on {node}")
                continue
            exposed = _normalize_string_list(storage.get("content"))
            expected_content = _pve_storage_content_names(set(requirement.get("content") or []))
            if expected_content and not expected_content.issubset(exposed):
                _emit(results, "FAIL", f"api.storage.{node}.{requirement['role']}", f"storage {requirement['datastore']} on {node} does not expose required content {', '.join(sorted(expected_content))}")
            else:
                _emit(results, "PASS", f"api.storage.{node}.{requirement['role']}", f"storage {requirement['datastore']} is available on {node}")


def _cluster_vm_index(client: ProxmoxAPI, results: list[CheckResult], secrets: list[str]) -> dict[int, dict[str, Any]] | None:
    """Build a quick VMID index from the cluster resource listing."""
    try:
        items = _api_items(client.get_json("/cluster/resources?type=vm"))
    except RuntimeError as exc:
        _emit(results, "FAIL", "api.vms", _redact(f"unable to query VM inventory: {exc}", secrets))
        return None
    index: dict[int, dict[str, Any]] = {}
    for item in items:
        vmid = item.get("vmid")
        if isinstance(vmid, int):
            index[vmid] = item
    _emit(results, "PASS", "api.vms", f"discovered {len(index)} VM record(s)")
    return index


def _check_templates(client: ProxmoxAPI, expected: DerivedResources, vm_index: dict[int, dict[str, Any]], results: list[CheckResult], secrets: list[str]) -> None:
    """Confirm the declared template records exist and are flagged as templates."""
    for template in expected.templates:
        record = vm_index.get(template["vmid"])
        if record is None:
            _emit(results, "FAIL", f"api.template.{template['vmid']}", f"template VMID {template['vmid']} ({template['name']}) is missing")
            continue
        template_flag = record.get("template") in {True, 1, "1", "true", "yes", "on"}
        if record.get("name") != template["name"] or record.get("node") != template["node"] or not template_flag:
            _emit(
                results,
                "FAIL",
                f"api.template.{template['vmid']}",
                f"template VMID {template['vmid']} mismatch: expected name={template['name']} node={template['node']} template=true; got name={record.get('name')!r} node={record.get('node')!r} template={record.get('template')!r}",
            )
            continue
        _emit(results, "PASS", f"api.template.{template['vmid']}", f"template {template['name']} on {template['node']} is present")


def _check_vmids(client: ProxmoxAPI, expected: DerivedResources, vm_index: dict[int, dict[str, Any]], results: list[CheckResult], secrets: list[str]) -> None:
    """Allow free VMIDs; occupied IDs must look repository-owned to pass."""
    for vm in expected.vmid_expectations:
        record = vm_index.get(vm["vmid"])
        if record is None:
            _emit(results, "PASS", f"api.vmid.{vm['vmid']}", f"VMID {vm['vmid']} is free")
            continue
        try:
            config = client.get_json(f"/nodes/{urllib.parse.quote(str(record.get('node') or vm['node']))}/qemu/{vm['vmid']}/config")
        except RuntimeError as exc:
            _emit(results, "FAIL", f"api.vmid.{vm['vmid']}", _redact(f"unable to read existing VM config: {exc}", secrets))
            continue
        actual_tags = _normalize_string_list(config.get("tags") or record.get("tags"))
        description = str(config.get("description") or record.get("description") or "")
        if record.get("name") == vm["name"] and (set(vm["tags"]).issubset(actual_tags) or vm["cluster_marker"] in description or "managed-by-opentofu" in actual_tags):
            _emit(results, "PASS", f"api.vmid.{vm['vmid']}", f"VMID {vm['vmid']} is already owned by this repository")
        else:
            observed = record.get("name") or "<unknown>"
            _emit(results, "FAIL", f"api.vmid.{vm['vmid']}", f"VMID {vm['vmid']} is occupied by unexpected VM {observed}")


def _mapping_detail_from_index(items: list[dict[str, Any]], mapping_name: str) -> dict[str, Any] | None:
    """Accept either list or detail-style PCI mapping responses."""
    for item in items:
        candidate = item.get("name") or item.get("id") or item.get("mapping")
        if candidate == mapping_name:
            return item
    return None


def _mapping_nodes(detail: dict[str, Any] | None) -> set[str] | None:
    """Normalize mapping node lists from the different PVE API shapes."""
    if detail is None:
        return None
    nodes = detail.get("nodes")
    if isinstance(nodes, dict):
        return {str(node) for node in nodes}
    if isinstance(nodes, list):
        extracted = {str(item) for item in nodes if isinstance(item, str)}
        if extracted:
            return extracted
        extracted = {str(item.get("node")) for item in nodes if isinstance(item, dict) and item.get("node")}
        return extracted or None
    map_entries = detail.get("map")
    if isinstance(map_entries, list):
        extracted = {str(item.get("node")) for item in map_entries if isinstance(item, dict) and item.get("node")}
        return extracted or None
    return None


def _check_pci_mappings(client: ProxmoxAPI, expected: DerivedResources, model: dict[str, Any], results: list[CheckResult], secrets: list[str]) -> None:
    """Check passthrough mappings when the endpoint is present; warn on gaps."""
    try:
        mapping_index = _api_items(client.get_json("/cluster/mapping/pci"))
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            # Older/limited API surfaces do not expose cluster mapping reads.
            _emit(results, "SKIP", "api.pci", "PVE API does not expose PCI mapping reads on this endpoint; skipped")
            return
        _emit(results, "WARN", "api.pci", _redact(f"PCI mapping checks unavailable: {exc}", secrets))
        return

    for mapping_name, mapping in model["cluster"]["pci_mappings"].items():
        detail = None
        if mapping_index:
            detail = _mapping_detail_from_index(mapping_index, mapping_name)
        if detail is None:
            try:
                detail = cast(dict[str, Any], client.get_json(f"/cluster/mapping/pci/{urllib.parse.quote(mapping_name)}"))
            except RuntimeError:
                detail = None

        present_nodes = _mapping_nodes(detail)
        declared_nodes = set(mapping.get("nodes", {}))
        used_nodes = {node for node, names in expected.mappings_by_node.items() if mapping_name in names}
        if present_nodes is None:
            if used_nodes:
                _emit(results, "WARN", f"api.pci.{mapping_name}", f"PCI mapping {mapping_name} exists but node compatibility could not be verified by the API")
            continue
        for node in used_nodes:
            if node in present_nodes:
                _emit(results, "PASS", f"api.pci.{mapping_name}.{node}", f"PCI mapping {mapping_name} is available on {node}")
            else:
                _emit(results, "FAIL", f"api.pci.{mapping_name}.{node}", f"PCI mapping {mapping_name} is missing or incompatible on {node}")
        for node in declared_nodes - used_nodes:
            if node not in present_nodes:
                _emit(results, "WARN", f"api.pci.{mapping_name}.optional.{node}", f"unused declared PCI mapping node {node} is unavailable")


def run_api_checks(runtime: RuntimeConfig, api_client: ProxmoxAPI, model: dict[str, Any], expected: DerivedResources, results: list[CheckResult]) -> None:
    """Run the API-first read-only checks in dependency order."""
    secrets = [runtime.api_token_secret, api_client.api_token_secret]
    node_names = _node_index(api_client, results, secrets)
    if node_names is None:
        return
    present_nodes = _check_required_nodes(expected, node_names, results)
    _check_bridges(api_client, expected, present_nodes, results, secrets)
    _check_storage(api_client, expected, present_nodes, results, secrets)
    vm_index = _cluster_vm_index(api_client, results, secrets)
    if vm_index is not None:
        _check_templates(api_client, expected, vm_index, results, secrets)
        _check_vmids(api_client, expected, vm_index, results, secrets)
    _check_pci_mappings(api_client, expected, model, results, secrets)
