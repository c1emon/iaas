"""Validation helpers for service metadata inventory YAML."""

from __future__ import annotations

from typing import Any

import re

from scripts.common.errors import require
from scripts.common.validation import as_list, as_mapping, require_non_empty_string, require_positive_int, require_unknown_keys


SERVICE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENDPOINT_NAME_RE = SERVICE_NAME_RE
ALLOWED_EXPOSURES = {"internal", "lan", "vpn", "public"}
ALLOWED_AUTHS = {"none", "app", "basic", "sso", "client-cert", "vpn", "unknown"}
ALLOWED_PROTOCOLS = {
    "amqp",
    "dns",
    "grpc",
    "http",
    "https",
    "imap",
    "kafka",
    "ldap",
    "memcached",
    "mongodb",
    "mqtt",
    "mysql",
    "nats",
    "postgres",
    "postgresql",
    "rabbitmq",
    "rdp",
    "redis",
    "s3",
    "sip",
    "smtp",
    "smb",
    "ssh",
    "tcp",
    "udp",
}


def _require_slug(value: Any, context: str, pattern: re.Pattern[str]) -> str:
    text = require_non_empty_string(value, context)
    require(text == text.lower(), f"{context}: must use lower-case slug format")
    require(pattern.fullmatch(text) is not None, f"{context}: must match slug format")
    return text


def _require_lower_choice(value: Any, context: str, allowed: set[str]) -> str:
    text = require_non_empty_string(value, context)
    require(text == text.lower(), f"{context}: must be lower-case")
    require(text in allowed, f"{context}: unsupported value {text}")
    return text


def load_vm_names(vms_doc: dict[str, Any]) -> set[str]:
    """Collect declared VM names from inventory/vms.yml."""
    require_unknown_keys(vms_doc, {"schema_version", "vms"}, "vms inventory")
    require(vms_doc.get("schema_version") == 1, "vms inventory: schema_version must be 1")
    vm_entries = as_list(vms_doc.get("vms"), "vms inventory.vms")
    names: set[str] = set()
    for index, vm in enumerate(vm_entries):
        vm_map = as_mapping(vm, f"vms inventory.vms[{index}]")
        name = require_non_empty_string(vm_map.get("name"), f"vms inventory.vms[{index}].name")
        names.add(name)
    return names


def validate_services(doc: dict[str, Any], vm_names: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Validate the service inventory and return normalized services plus warnings."""
    require_unknown_keys(doc, {"schema_version", "services"}, "services inventory")
    require(doc.get("schema_version") == 1, "services inventory: schema_version must be 1")
    services = as_list(doc.get("services"), "services inventory.services")
    seen_names: set[str] = set()
    normalized: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    for service_index, service in enumerate(services):
        service_map = as_mapping(service, f"services inventory.services[{service_index}]")
        require_unknown_keys(service_map, {"name", "owner_vm", "description", "endpoints"}, f"services inventory.services[{service_index}]")

        name = _require_slug(service_map.get("name"), f"services inventory.services[{service_index}].name", SERVICE_NAME_RE)
        require(name not in seen_names, f"services inventory.services[{service_index}]: duplicate service name {name}")
        seen_names.add(name)

        owner_vm = require_non_empty_string(service_map.get("owner_vm"), f"services inventory.services[{service_index}].owner_vm")
        require(owner_vm in vm_names, f"services inventory.services[{service_index}]: owner_vm {owner_vm} is not declared in inventory/vms.yml")

        description = service_map.get("description")
        if description is not None:
            description = require_non_empty_string(description, f"services inventory.services[{service_index}].description")

        endpoints = as_list(service_map.get("endpoints"), f"services inventory.services[{service_index}].endpoints")
        require(endpoints, f"services inventory.services[{service_index}]: endpoints must not be empty")

        normalized_endpoints: list[dict[str, Any]] = []
        seen_endpoint_names: set[str] = set()
        for endpoint_index, endpoint in enumerate(endpoints):
            endpoint_map = as_mapping(endpoint, f"services inventory.services[{service_index}].endpoints[{endpoint_index}]")
            require_unknown_keys(
                endpoint_map,
                {"name", "fqdn", "port", "protocol", "exposure", "auth", "dns_hint", "reverse_proxy_hint", "opnsense_hint"},
                f"services inventory.services[{service_index}].endpoints[{endpoint_index}]",
            )

            endpoint_name = endpoint_map.get("name")
            if endpoint_name is not None:
                endpoint_name = _require_slug(endpoint_name, f"services inventory.services[{service_index}].endpoints[{endpoint_index}].name", ENDPOINT_NAME_RE)
                require(
                    endpoint_name not in seen_endpoint_names,
                    f"services inventory.services[{service_index}].endpoints[{endpoint_index}]: duplicate endpoint name {endpoint_name}",
                )
                seen_endpoint_names.add(endpoint_name)

            fqdn = endpoint_map.get("fqdn")
            if fqdn is not None:
                fqdn = require_non_empty_string(fqdn, f"services inventory.services[{service_index}].endpoints[{endpoint_index}].fqdn")

            port = require_positive_int(endpoint_map.get("port"), f"services inventory.services[{service_index}].endpoints[{endpoint_index}].port")
            require(port <= 65535, f"services inventory.services[{service_index}].endpoints[{endpoint_index}].port: must be within 1-65535")

            protocol = _require_lower_choice(endpoint_map.get("protocol"), f"services inventory.services[{service_index}].endpoints[{endpoint_index}].protocol", ALLOWED_PROTOCOLS)
            exposure = _require_lower_choice(endpoint_map.get("exposure"), f"services inventory.services[{service_index}].endpoints[{endpoint_index}].exposure", ALLOWED_EXPOSURES)
            auth = _require_lower_choice(endpoint_map.get("auth"), f"services inventory.services[{service_index}].endpoints[{endpoint_index}].auth", ALLOWED_AUTHS)

            dns_hint = endpoint_map.get("dns_hint")
            if dns_hint is not None:
                dns_hint = require_non_empty_string(dns_hint, f"services inventory.services[{service_index}].endpoints[{endpoint_index}].dns_hint")
            reverse_proxy_hint = endpoint_map.get("reverse_proxy_hint")
            if reverse_proxy_hint is not None:
                reverse_proxy_hint = require_non_empty_string(reverse_proxy_hint, f"services inventory.services[{service_index}].endpoints[{endpoint_index}].reverse_proxy_hint")
            opnsense_hint = endpoint_map.get("opnsense_hint")
            if opnsense_hint is not None:
                opnsense_hint = require_non_empty_string(opnsense_hint, f"services inventory.services[{service_index}].endpoints[{endpoint_index}].opnsense_hint")

            endpoint_record = {
                "name": endpoint_name,
                "fqdn": fqdn,
                "port": port,
                "protocol": protocol,
                "exposure": exposure,
                "auth": auth,
                "dns_hint": dns_hint,
                "reverse_proxy_hint": reverse_proxy_hint,
                "opnsense_hint": opnsense_hint,
            }
            normalized_endpoints.append(endpoint_record)

            endpoint_label = endpoint_name or f"{name}:{protocol}:{port}"
            if exposure in {"lan", "vpn", "public"} and fqdn is None:
                warnings.append({
                    "service": name,
                    "endpoint": endpoint_label,
                    "code": "missing-fqdn",
                    "message": "non-internal endpoint lacks fqdn",
                })
            if exposure == "public":
                warnings.append({
                    "service": name,
                    "endpoint": endpoint_label,
                    "code": "public-exposure",
                    "message": "public exposure requires operator review",
                })
            if exposure == "public" and auth == "none":
                warnings.append({
                    "service": name,
                    "endpoint": endpoint_label,
                    "code": "public-unauthenticated",
                    "message": "public exposure with auth none",
                })
            if auth == "unknown":
                warnings.append({
                    "service": name,
                    "endpoint": endpoint_label,
                    "code": "auth-unknown",
                    "message": "auth unknown needs review",
                })

        normalized.append({
            "name": name,
            "owner_vm": owner_vm,
            "description": description,
            "endpoints": normalized_endpoints,
        })

    return normalized, warnings
