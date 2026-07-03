"""Validation helpers for the foundation recovery inventory YAML.

The validator keeps the inventory offline-only: it checks structure,
references, restore ordering, storage facts, and obvious secret leakage
without contacting foundation services or network devices.
"""

from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Any
import re

from scripts.common.errors import require
from scripts.common.validation import as_list, as_mapping, require_bool, require_non_empty_string, require_positive_int, require_unknown_keys


HOST_KIND_CHOICES = {"bare-metal", "vm", "appliance", "external-dependency"}
SERVICE_RUNTIME_CHOICES = {"compose", "systemd", "appliance", "external", "unknown"}
SERVICE_TIER_CHOICES = {"critical", "required", "important", "optional"}
HEALTH_TYPE_CHOICES = {"tcp", "http", "https", "dns", "api"}
REFERENCE_PREFIXES = ("op://", "ref:", "vault://", "sops://")
REFERENCE_KEYS = {"secret_ref", "credential_ref", "token_ref", "certificate_ref"}
SENSITIVE_KEY_RE = re.compile(r"(?:password|passwd|secret|token|apikey|api_key|private_key|private-key|credential|hash|cert_private_key)", re.I)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [^-]+PRIVATE KEY-----", re.I)
BCRYPT_RE = re.compile(r"^\$2[abyx]\$")
ARGON2_RE = re.compile(r"^\$argon2(?:id|i|d)\$")
AKIA_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
LONG_TOKEN_RE = re.compile(r"^[A-Za-z0-9+/=_-]{40,}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HOST_PORT_RE = re.compile(r"^[^\s:]+:\d{1,5}$")


def _require_slug(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    require(text == text.lower(), f"{context}: must use lower-case slug format")
    require(SLUG_RE.fullmatch(text) is not None, f"{context}: must match slug format")
    return text


def _require_choice(value: Any, context: str, allowed: set[str]) -> str:
    text = require_non_empty_string(value, context)
    require(text == text.lower(), f"{context}: must be lower-case")
    require(text in allowed, f"{context}: unsupported value {text}")
    return text


def _is_reference_text(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(REFERENCE_PREFIXES)


def _scan_non_sensitive(node: Any, context: str) -> None:
    """Reject obvious secret material while allowing explicit secret references."""
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            key_context = f"{context}.{key_text}"
            # Keys with secret-shaped names must carry a reference string, not plaintext.
            if SENSITIVE_KEY_RE.search(key_text):
                require(_is_reference_text(value), f"{key_context}: sensitive keys must use an external secret reference")
            if key_text in REFERENCE_KEYS:
                require(_is_reference_text(value), f"{key_context}: secret references must use op://, ref:, vault://, or sops://")
            _scan_non_sensitive(value, key_context)
        return
    if isinstance(node, list):
        for index, value in enumerate(node):
            _scan_non_sensitive(value, f"{context}[{index}]")
        return
    if isinstance(node, str) and not _is_reference_text(node):
        require(PRIVATE_KEY_RE.search(node) is None, f"{context}: contains private key material")
        require(BCRYPT_RE.search(node) is None and ARGON2_RE.search(node) is None, f"{context}: contains password hash material")
        require(AKIA_RE.search(node) is None, f"{context}: contains access key material")
        require(not (len(node) >= 40 and LONG_TOKEN_RE.fullmatch(node)), f"{context}: contains high-risk token-like material")


def _require_string_list(value: Any, context: str) -> list[str]:
    items = as_list(value, context)
    result: list[str] = []
    for index, item in enumerate(items):
        result.append(require_non_empty_string(item, f"{context}[{index}]"))
    return result


def _require_positive_int_list(value: Any, context: str) -> list[int]:
    items = as_list(value, context)
    result: list[int] = []
    for index, item in enumerate(items):
        result.append(require_positive_int(item, f"{context}[{index}]"))
    return result


def _normalize_host(host: dict[str, Any], index: int, seen_names: set[str]) -> tuple[dict[str, Any], str]:
    require_unknown_keys(host, {"name", "kind", "management_identity", "extra_addresses", "accepted_spof", "notes"}, f"foundation inventory.foundation_hosts[{index}]")
    name = _require_slug(host.get("name"), f"foundation inventory.foundation_hosts[{index}].name")
    require(name not in seen_names, f"foundation inventory.foundation_hosts[{index}]: duplicate host name {name}")
    seen_names.add(name)
    kind = _require_choice(host.get("kind"), f"foundation inventory.foundation_hosts[{index}].kind", HOST_KIND_CHOICES)
    management_identity = require_non_empty_string(host.get("management_identity"), f"foundation inventory.foundation_hosts[{index}].management_identity")

    extra_addresses_raw = host.get("extra_addresses")
    extra_addresses: list[str] = []
    if extra_addresses_raw is not None:
        extra_addresses = _require_string_list(extra_addresses_raw, f"foundation inventory.foundation_hosts[{index}].extra_addresses")

    accepted_spof = host.get("accepted_spof", False)
    if "accepted_spof" in host:
        accepted_spof = require_bool(accepted_spof, f"foundation inventory.foundation_hosts[{index}].accepted_spof")
    notes = host.get("notes")
    if notes is not None:
        notes = require_non_empty_string(notes, f"foundation inventory.foundation_hosts[{index}].notes")

    normalized = {
        "name": name,
        "kind": kind,
        "management_identity": management_identity,
        "extra_addresses": extra_addresses,
        "accepted_spof": accepted_spof,
        "notes": notes,
    }
    return normalized, name


def _validate_health_check(service_name: str, service_index: int, health_check: dict[str, Any]) -> dict[str, Any]:
    """Normalize the declared read-only probe for one service."""
    require_unknown_keys(
        health_check,
        {"type", "target", "expected_status", "record_type", "resolver", "expected_answer", "timeout_seconds"},
        f"foundation inventory.foundation_services[{service_index}].health_check",
    )
    probe_type = _require_choice(health_check.get("type"), f"foundation inventory.foundation_services[{service_index}].health_check.type", HEALTH_TYPE_CHOICES)
    target = require_non_empty_string(health_check.get("target"), f"foundation inventory.foundation_services[{service_index}].health_check.target")
    timeout_seconds = health_check.get("timeout_seconds")
    if timeout_seconds is not None:
        timeout_seconds = require_positive_int(timeout_seconds, f"foundation inventory.foundation_services[{service_index}].health_check.timeout_seconds")

    expected_status = health_check.get("expected_status")
    if expected_status is not None:
        expected_status = _require_positive_int_list(expected_status, f"foundation inventory.foundation_services[{service_index}].health_check.expected_status")
        for status in expected_status:
            require(100 <= status <= 599, f"foundation inventory.foundation_services[{service_index}].health_check.expected_status: HTTP status must be within 100-599")

    record_type = health_check.get("record_type")
    resolver = health_check.get("resolver")
    expected_answer = health_check.get("expected_answer")

    if probe_type in {"http", "https", "api"}:
        require(target.startswith(("http://", "https://")), f"foundation inventory.foundation_services[{service_index}].health_check.target: must look like a URL")
    elif probe_type == "tcp":
        require(HOST_PORT_RE.fullmatch(target) is not None, f"foundation inventory.foundation_services[{service_index}].health_check.target: must look like host:port")
        if expected_status is not None:
            require(False, f"foundation inventory.foundation_services[{service_index}].health_check.expected_status: not valid for tcp health checks")
    elif probe_type == "dns":
        if resolver is not None:
            resolver = require_non_empty_string(resolver, f"foundation inventory.foundation_services[{service_index}].health_check.resolver")
        if record_type is not None:
            record_type = _require_choice(record_type, f"foundation inventory.foundation_services[{service_index}].health_check.record_type", {"a", "aaaa", "cname", "txt", "srv", "any"})
        if expected_answer is not None:
            if isinstance(expected_answer, list):
                expected_answer = _require_string_list(expected_answer, f"foundation inventory.foundation_services[{service_index}].health_check.expected_answer")
            else:
                expected_answer = require_non_empty_string(expected_answer, f"foundation inventory.foundation_services[{service_index}].health_check.expected_answer")
    else:
        require(False, f"foundation inventory.foundation_services[{service_index}].health_check.type: unsupported value {probe_type}")

    return {
        "type": probe_type,
        "target": target,
        "expected_status": expected_status,
        "record_type": record_type,
        "resolver": resolver,
        "expected_answer": expected_answer,
        "timeout_seconds": timeout_seconds,
        "service": service_name,
    }


def _validate_backup_restore(service_index: int, backup_restore: dict[str, Any]) -> dict[str, Any]:
    require_unknown_keys(
        backup_restore,
        {"profile", "restore_runbook", "backup_location", "tested", "notes"},
        f"foundation inventory.foundation_services[{service_index}].backup_restore",
    )
    profile = require_non_empty_string(backup_restore.get("profile"), f"foundation inventory.foundation_services[{service_index}].backup_restore.profile")
    restore_runbook = require_non_empty_string(backup_restore.get("restore_runbook"), f"foundation inventory.foundation_services[{service_index}].backup_restore.restore_runbook")
    backup_location = backup_restore.get("backup_location")
    if backup_location is not None:
        backup_location = require_non_empty_string(backup_location, f"foundation inventory.foundation_services[{service_index}].backup_restore.backup_location")
    tested = backup_restore.get("tested")
    if tested is not None:
        tested = require_bool(tested, f"foundation inventory.foundation_services[{service_index}].backup_restore.tested")
    notes = backup_restore.get("notes")
    if notes is not None:
        notes = require_non_empty_string(notes, f"foundation inventory.foundation_services[{service_index}].backup_restore.notes")
    return {
        "profile": profile,
        "restore_runbook": restore_runbook,
        "backup_location": backup_location,
        "tested": tested,
        "notes": notes,
    }


def _validate_break_glass(service_index: int, break_glass: dict[str, Any]) -> dict[str, Any]:
    require_unknown_keys(
        break_glass,
        {"method", "access_path", "secret_ref", "notes"},
        f"foundation inventory.foundation_services[{service_index}].break_glass",
    )
    method = require_non_empty_string(break_glass.get("method"), f"foundation inventory.foundation_services[{service_index}].break_glass.method")
    access_path = require_non_empty_string(break_glass.get("access_path"), f"foundation inventory.foundation_services[{service_index}].break_glass.access_path")
    secret_ref = break_glass.get("secret_ref")
    if secret_ref is not None:
        secret_ref = require_non_empty_string(secret_ref, f"foundation inventory.foundation_services[{service_index}].break_glass.secret_ref")
        require(secret_ref.startswith(REFERENCE_PREFIXES), f"foundation inventory.foundation_services[{service_index}].break_glass.secret_ref: must use op://, ref:, vault://, or sops://")
    notes = break_glass.get("notes")
    if notes is not None:
        notes = require_non_empty_string(notes, f"foundation inventory.foundation_services[{service_index}].break_glass.notes")
    return {
        "method": method,
        "access_path": access_path,
        "secret_ref": secret_ref,
        "notes": notes,
    }


def _normalize_service(
    service: dict[str, Any],
    index: int,
    seen_names: set[str],
    host_kinds: dict[str, str],
    host_names: set[str],
    service_names: set[str],
    external_host_names: set[str],
    restore_orders: set[int],
) -> dict[str, Any]:
    require_unknown_keys(
        service,
        {"name", "host", "external_dependency", "runtime", "tier", "required_before_k3s", "restore_order", "dependencies", "health_check", "backup_restore", "break_glass", "config_source", "known_risks", "notes"},
        f"foundation inventory.foundation_services[{index}]",
    )
    name = _require_slug(service.get("name"), f"foundation inventory.foundation_services[{index}].name")
    require(name not in seen_names, f"foundation inventory.foundation_services[{index}]: duplicate service name {name}")
    seen_names.add(name)

    host = service.get("host")
    if host is not None:
        host = require_non_empty_string(host, f"foundation inventory.foundation_services[{index}].host")
        require(host in host_names, f"foundation inventory.foundation_services[{index}]: unknown host ref {host}")

    external_dependency = service.get("external_dependency", False)
    if "external_dependency" in service:
        external_dependency = require_bool(external_dependency, f"foundation inventory.foundation_services[{index}].external_dependency")

    if host is None and not external_dependency:
        require(False, f"foundation inventory.foundation_services[{index}]: must reference a declared host or mark itself as an external dependency")
    if host is not None and external_dependency and host_kinds.get(host) != "external-dependency":
        require(False, f"foundation inventory.foundation_services[{index}]: external_dependency may only be set when the host is an external-dependency host")

    runtime = _require_choice(service.get("runtime"), f"foundation inventory.foundation_services[{index}].runtime", SERVICE_RUNTIME_CHOICES)
    tier = _require_choice(service.get("tier"), f"foundation inventory.foundation_services[{index}].tier", SERVICE_TIER_CHOICES)

    required_before_k3s = service.get("required_before_k3s", False)
    if "required_before_k3s" in service:
        required_before_k3s = require_bool(required_before_k3s, f"foundation inventory.foundation_services[{index}].required_before_k3s")

    restore_order = service.get("restore_order")
    if required_before_k3s:
        restore_order = require_positive_int(restore_order, f"foundation inventory.foundation_services[{index}].restore_order")
        require(restore_order not in restore_orders, f"foundation inventory.foundation_services[{index}]: duplicate restore_order {restore_order}")
        restore_orders.add(restore_order)
    elif restore_order is not None:
        restore_order = require_positive_int(restore_order, f"foundation inventory.foundation_services[{index}].restore_order")

    dependencies_raw = service.get("dependencies", [])
    dependencies = _require_string_list(dependencies_raw, f"foundation inventory.foundation_services[{index}].dependencies") if dependencies_raw is not None else []
    for dependency in dependencies:
        require(
            dependency in service_names or dependency in external_host_names,
            f"foundation inventory.foundation_services[{index}].dependencies: unknown dependency ref {dependency}",
        )

    health_check_raw = service.get("health_check")
    health_check = None
    if health_check_raw is not None:
        health_check = _validate_health_check(name, index, as_mapping(health_check_raw, f"foundation inventory.foundation_services[{index}].health_check"))

    backup_restore_raw = service.get("backup_restore")
    backup_restore = None
    if backup_restore_raw is not None:
        backup_restore = _validate_backup_restore(index, as_mapping(backup_restore_raw, f"foundation inventory.foundation_services[{index}].backup_restore"))

    break_glass_raw = service.get("break_glass")
    break_glass = None
    if break_glass_raw is not None:
        break_glass = _validate_break_glass(index, as_mapping(break_glass_raw, f"foundation inventory.foundation_services[{index}].break_glass"))

    if required_before_k3s or tier == "critical":
        require(health_check is not None, f"foundation inventory.foundation_services[{index}]: critical or required-before-K3s services must declare a health check")
        require(backup_restore is not None, f"foundation inventory.foundation_services[{index}]: critical or required-before-K3s services must declare backup/restore metadata")
        require(break_glass is not None, f"foundation inventory.foundation_services[{index}]: critical or required-before-K3s services must declare break-glass metadata")

    config_source = service.get("config_source")
    if config_source is not None:
        config_source = require_non_empty_string(config_source, f"foundation inventory.foundation_services[{index}].config_source")
    known_risks_raw = service.get("known_risks", [])
    known_risks = _require_string_list(known_risks_raw, f"foundation inventory.foundation_services[{index}].known_risks") if known_risks_raw is not None else []
    notes = service.get("notes")
    if notes is not None:
        notes = require_non_empty_string(notes, f"foundation inventory.foundation_services[{index}].notes")

    normalized = {
        "name": name,
        "host": host,
        "external_dependency": external_dependency,
        "runtime": runtime,
        "tier": tier,
        "required_before_k3s": required_before_k3s,
        "restore_order": restore_order,
        "dependencies": dependencies,
        "health_check": health_check,
        "backup_restore": backup_restore,
        "break_glass": break_glass,
        "config_source": config_source,
        "known_risks": known_risks,
        "notes": notes,
    }
    service_names.add(name)
    return normalized


def _normalize_storage_network(network: dict[str, Any], index: int, seen_names: set[str], seen_vlan_ids: set[int]) -> dict[str, Any]:
    """Validate storage-network facts without probing or mutating the network."""
    require_unknown_keys(network, {"name", "vlan_id", "subnet", "truenas_endpoint", "notes"}, f"foundation inventory.storage_networks[{index}]")
    name = _require_slug(network.get("name"), f"foundation inventory.storage_networks[{index}].name")
    require(name not in seen_names, f"foundation inventory.storage_networks[{index}]: duplicate storage network name {name}")
    seen_names.add(name)
    vlan_id = require_positive_int(network.get("vlan_id"), f"foundation inventory.storage_networks[{index}].vlan_id")
    require(vlan_id not in seen_vlan_ids, f"foundation inventory.storage_networks[{index}]: duplicate vlan_id {vlan_id}")
    seen_vlan_ids.add(vlan_id)
    subnet = require_non_empty_string(network.get("subnet"), f"foundation inventory.storage_networks[{index}].subnet")
    # Facts only: ensure the subnet parses, then confirm the TrueNAS endpoint lives inside it.
    network_obj = ip_network(subnet, strict=False)
    truenas_endpoint = require_non_empty_string(network.get("truenas_endpoint"), f"foundation inventory.storage_networks[{index}].truenas_endpoint")
    endpoint_address = ip_address(truenas_endpoint)
    require(endpoint_address in network_obj, f"foundation inventory.storage_networks[{index}].truenas_endpoint: must be inside subnet {subnet}")
    notes = network.get("notes")
    if notes is not None:
        notes = require_non_empty_string(notes, f"foundation inventory.storage_networks[{index}].notes")
    return {
        "name": name,
        "vlan_id": vlan_id,
        "subnet": subnet,
        "truenas_endpoint": truenas_endpoint,
        "notes": notes,
    }


def _normalize_k3s_storage_access(doc: dict[str, Any], storage_network_names: set[str]) -> dict[str, Any]:
    """Validate the first-phase storage access scope and keep it VM-only."""
    require_unknown_keys(doc, {"phase_1", "notes"}, "foundation inventory.k3s_storage_access")
    phase_1 = as_mapping(doc.get("phase_1"), "foundation inventory.k3s_storage_access.phase_1")
    require_unknown_keys(phase_1, {"node_classes", "storage_networks", "notes"}, "foundation inventory.k3s_storage_access.phase_1")
    node_classes = _require_string_list(phase_1.get("node_classes"), "foundation inventory.k3s_storage_access.phase_1.node_classes")
    require(node_classes == ["vm"], "foundation inventory.k3s_storage_access.phase_1.node_classes: first phase must be VM-only")
    phase_storage_networks = _require_string_list(phase_1.get("storage_networks"), "foundation inventory.k3s_storage_access.phase_1.storage_networks")
    require(set(phase_storage_networks) == storage_network_names, "foundation inventory.k3s_storage_access.phase_1.storage_networks: must match declared storage_networks")
    notes = phase_1.get("notes")
    if notes is not None:
        notes = require_non_empty_string(notes, "foundation inventory.k3s_storage_access.phase_1.notes")
    top_notes = doc.get("notes")
    if top_notes is not None:
        top_notes = require_non_empty_string(top_notes, "foundation inventory.k3s_storage_access.notes")
    return {"phase_1": {"node_classes": node_classes, "storage_networks": phase_storage_networks, "notes": notes}, "notes": top_notes}


def validate_foundation_inventory(doc: dict[str, Any]) -> dict[str, Any]:
    """Validate the foundation inventory and return a normalized model."""
    require_unknown_keys(doc, {"schema_version", "foundation_hosts", "foundation_services", "storage_networks", "k3s_storage_access"}, "foundation inventory")
    require(doc.get("schema_version") == 1, "foundation inventory: schema_version must be 1")
    _scan_non_sensitive(doc, "foundation inventory")

    hosts = as_list(doc.get("foundation_hosts"), "foundation inventory.foundation_hosts")
    services = as_list(doc.get("foundation_services"), "foundation inventory.foundation_services")
    storage_networks = as_list(doc.get("storage_networks"), "foundation inventory.storage_networks")
    k3s_storage_access_raw = as_mapping(doc.get("k3s_storage_access"), "foundation inventory.k3s_storage_access")

    normalized_hosts: list[dict[str, Any]] = []
    normalized_services: list[dict[str, Any]] = []
    normalized_storage_networks: list[dict[str, Any]] = []
    seen_host_names: set[str] = set()
    seen_service_names: set[str] = set()
    host_kinds: dict[str, str] = {}
    restore_orders: set[int] = set()

    for index, host in enumerate(hosts):
        host_map = as_mapping(host, f"foundation inventory.foundation_hosts[{index}]")
        normalized_host, host_name = _normalize_host(host_map, index, seen_host_names)
        host_kinds[host_name] = normalized_host["kind"]
        normalized_hosts.append(normalized_host)

    host_names = set(host_kinds)
    external_host_names = {name for name, kind in host_kinds.items() if kind == "external-dependency"}
    service_name_pool = {require_non_empty_string(as_mapping(service, f"foundation inventory.foundation_services[{index}]").get("name"), f"foundation inventory.foundation_services[{index}].name") for index, service in enumerate(services)}

    for index, service in enumerate(services):
        service_map = as_mapping(service, f"foundation inventory.foundation_services[{index}]")
        normalized_services.append(
            _normalize_service(service_map, index, seen_service_names, host_kinds, host_names, service_name_pool, external_host_names, restore_orders)
        )

    for index, network in enumerate(storage_networks):
        network_map = as_mapping(network, f"foundation inventory.storage_networks[{index}]")
        normalized_storage_networks.append(_normalize_storage_network(network_map, index, {item["name"] for item in normalized_storage_networks}, {item["vlan_id"] for item in normalized_storage_networks}))

    storage_network_names = {network["name"] for network in normalized_storage_networks}
    normalized_k3s_storage_access = _normalize_k3s_storage_access(k3s_storage_access_raw, storage_network_names)

    required_orders = [service["restore_order"] for service in normalized_services if service["required_before_k3s"]]
    require(required_orders == sorted(required_orders), "foundation inventory: required-before-K3s services must be declared in restore-order sequence")

    for service in normalized_services:
        if service["host"] is not None and host_kinds.get(service["host"]) == "external-dependency":
            require(service["external_dependency"], f"foundation inventory.foundation_services[{service['name']}]: external dependency hosts must be explicitly marked external_dependency")

    return {
        "schema_version": 1,
        "foundation_hosts": normalized_hosts,
        "foundation_services": normalized_services,
        "storage_networks": normalized_storage_networks,
        "k3s_storage_access": normalized_k3s_storage_access,
    }
