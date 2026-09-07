"""Validate K3s intent and compose it with generated VM facts."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit

import yaml

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.validation import as_list, as_mapping, require_bool, require_non_empty_string, require_unknown_keys


K3S_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+\+k3s\d+$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-.][a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
REGISTRY_REWRITE_PATTERN_RE = re.compile(
    r"^\^[a-z0-9]+(?:(?:\\\.|[_-])[a-z0-9]+)*"
    r"(?:/[a-z0-9]+(?:(?:\\\.|[_-])[a-z0-9]+)*)*"
    r"(?:/\(\.\*\))?\$?$"
)
REGISTRY_REWRITE_REPLACEMENT_RE = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*"
    r"(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*"
    r"(?:/\$1)?$"
)
SUPPORTED_ARCHITECTURES = {"amd64"}
NODE_NETWORK_ROLES = {"cluster", "management"}


def _choice(value: Any, context: str, allowed: set[str]) -> str:
    text = require_non_empty_string(value, context)
    require(text in allowed, f"{context}: must be one of {', '.join(sorted(allowed))}")
    return text


def _secret_ref(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    require(not any(character.isspace() for character in text), f"{context}: must not contain whitespace")
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(f"{context}: must be a valid op://vault/item/field external secret reference") from exc
    path_parts = parsed.path.removeprefix("/").split("/")
    require(
        parsed.scheme == "op"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and port is None
        and parsed.path.startswith("/")
        and len(path_parts) in {2, 3}
        and all(path_parts)
        and not parsed.query
        and not parsed.fragment,
        f"{context}: must be an op://vault/item/field external secret reference",
    )
    return text


def _sha256(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    require(SHA256_RE.fullmatch(text) is not None, f"{context}: must be a lower-case SHA-256 digest")
    return text


def _url(value: Any, context: str, *, https_only: bool) -> str:
    text = require_non_empty_string(value, context)
    require(not any(character.isspace() for character in text), f"{context}: must not contain whitespace")
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(f"{context}: must contain a valid host and port") from exc
    allowed_schemes = {"https"} if https_only else {"http", "https"}
    label = "HTTPS" if https_only else "HTTP(S)"
    require(parsed.scheme in allowed_schemes and parsed.hostname is not None, f"{context}: must be a valid {label} URL")
    require(port is None or port > 0, f"{context}: port must be between 1 and 65535")
    require(parsed.username is None and parsed.password is None, f"{context}: credentials must use an external secret reference")
    require(not parsed.query and not parsed.fragment, f"{context}: query strings and fragments are not allowed")
    return text


def _registry_name(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    require(text == text.lower() and not any(character.isspace() for character in text), f"{context}: must be lower-case")
    try:
        parsed = urlsplit(f"//{text}")
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(f"{context}: must be a registry host with an optional valid port") from exc
    host = parsed.hostname
    require(
        host is not None
        and parsed.username is None
        and parsed.password is None
        and not parsed.path
        and not parsed.query
        and not parsed.fragment,
        f"{context}: must be a registry host with an optional port",
    )
    require(port is None or port > 0, f"{context}: port must be between 1 and 65535")
    assert host is not None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        labels = host.split(".")
        require(
            all(DNS_LABEL_RE.fullmatch(label) is not None for label in labels)
            and not all(label.isdigit() for label in labels),
            f"{context}: must contain a valid DNS name or IP address",
        )
    require("." in text or ":" in text or port is not None, f"{context}: must contain a dot or explicit port")
    return text


def _network(value: Any, context: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    text = require_non_empty_string(value, context)
    try:
        return ipaddress.ip_network(text, strict=True)
    except ValueError as exc:
        raise ValidationError(f"{context}: must be a canonical network CIDR") from exc


def _address(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    try:
        return str(ipaddress.ip_address(text))
    except ValueError as exc:
        raise ValidationError(f"{context}: must be an IP address") from exc


def _endpoint_address(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        require(SLUG_RE.fullmatch(text) is not None and "." in text, f"{context}: must be an IP address or DNS name")
        return text
    require(
        not (
            address.is_unspecified
            or address.is_loopback
            or address.is_multicast
            or address.is_link_local
            or address.is_reserved
        ),
        f"{context}: must be a stable unicast IP address or DNS name",
    )
    return str(address)


def _generated_hosts(inventory_doc: dict[str, Any]) -> dict[str, Any]:
    all_group = as_mapping(inventory_doc.get("all"), "inventory.all")
    children = as_mapping(all_group.get("children"), "inventory.all.children")
    pve_vms = as_mapping(children.get("pve_vms"), "inventory.all.children.pve_vms")
    return as_mapping(pve_vms.get("hosts"), "inventory.all.children.pve_vms.hosts")


def _host_networks(host: dict[str, Any], context: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for index, raw_nic in enumerate(as_list(host.get("pve_nics"), f"{context}.pve_nics")):
        nic = as_mapping(raw_nic, f"{context}.pve_nics[{index}]")
        networks.append(_network(nic.get("network_cidr"), f"{context}.pve_nics[{index}].network_cidr"))
    return networks


def _compose_node(
    node_doc: dict[str, Any],
    index: int,
    hosts: dict[str, Any],
    node_network_role: str,
) -> tuple[dict[str, Any], list[ipaddress.IPv4Network | ipaddress.IPv6Network]]:
    context = f"nodes[{index}]"
    require_unknown_keys(node_doc, {"vm_ref", "role", "bootstrap"}, context)
    vm_ref = require_non_empty_string(node_doc.get("vm_ref"), f"{context}.vm_ref")
    require(vm_ref in hosts, f"{context}.vm_ref: {vm_ref} is not present in generated pve_vms inventory")
    role = _choice(node_doc.get("role"), f"{context}.role", {"server", "agent"})
    bootstrap = require_bool(node_doc.get("bootstrap"), f"{context}.bootstrap")
    require(role == "server" or not bootstrap, f"{context}.bootstrap: only a server may bootstrap the cluster")

    host = as_mapping(hosts[vm_ref], f"inventory host {vm_ref}")
    require(host.get("ansible_connection") == "ssh", f"inventory host {vm_ref}.ansible_connection: must be ssh")
    ansible_host = _address(host.get("ansible_host"), f"inventory host {vm_ref}.ansible_host")
    ansible_user = require_non_empty_string(host.get("ansible_user"), f"inventory host {vm_ref}.ansible_user")
    architecture = require_non_empty_string(host.get("pve_architecture"), f"inventory host {vm_ref}.pve_architecture")
    require(architecture in SUPPORTED_ARCHITECTURES, f"inventory host {vm_ref}.pve_architecture: unsupported architecture {architecture}")

    raw_nics = as_list(host.get("pve_nics"), f"inventory host {vm_ref}.pve_nics")
    matching_nics: list[dict[str, Any]] = []
    connection_nics: list[dict[str, Any]] = []
    for nic_index, raw_nic in enumerate(raw_nics):
        nic = as_mapping(raw_nic, f"inventory host {vm_ref}.pve_nics[{nic_index}]")
        if nic.get("role") == node_network_role:
            matching_nics.append(nic)
        if nic.get("ansible_connection") is True:
            connection_nics.append(nic)
    require(len(connection_nics) == 1, f"inventory host {vm_ref}: expected exactly one ansible_connection NIC")
    connection_ip = _address(connection_nics[0].get("ip_address"), f"inventory host {vm_ref}: connection NIC ip_address")
    require(connection_ip == ansible_host, f"inventory host {vm_ref}: connection NIC ip_address must match ansible_host")
    require(len(matching_nics) == 1, f"inventory host {vm_ref}: expected exactly one NIC with role {node_network_role}")
    nic = matching_nics[0]
    node_ip = _address(nic.get("ip_address"), f"inventory host {vm_ref}: node NIC ip_address")
    prefix_length = nic.get("prefix_length")
    require(isinstance(prefix_length, int) and not isinstance(prefix_length, bool), f"inventory host {vm_ref}: node NIC prefix_length must be an integer")
    node_network = _network(nic.get("network_cidr"), f"inventory host {vm_ref}: node NIC network_cidr")
    try:
        node_interface = ipaddress.ip_interface(f"{node_ip}/{prefix_length}")
    except ValueError as exc:
        raise ValidationError(f"inventory host {vm_ref}: node NIC address/prefix is invalid") from exc
    require(node_interface.network == node_network, f"inventory host {vm_ref}: node NIC address/prefix must match network_cidr")
    require(node_interface.ip != node_network.network_address, f"inventory host {vm_ref}: node NIC IP must be a usable host address")
    if isinstance(node_network, ipaddress.IPv4Network):
        require(node_interface.ip != node_network.broadcast_address, f"inventory host {vm_ref}: node NIC IP must be a usable host address")

    composed = {
        "vm_ref": vm_ref,
        "role": role,
        "bootstrap": bootstrap,
        "ansible_host": ansible_host,
        "ansible_user": ansible_user,
        "architecture": architecture,
        "node_nic": require_non_empty_string(nic.get("name"), f"inventory host {vm_ref}: node NIC name"),
        "node_ip": node_ip,
        "prefix_length": prefix_length,
        "node_network": str(node_network),
    }
    return composed, _host_networks(host, f"inventory host {vm_ref}")


def _validate_artifacts(value: Any, architectures: set[str], version: str) -> dict[str, Any]:
    artifacts = as_mapping(value, "cluster.artifacts")
    require(set(artifacts) == architectures, f"cluster.artifacts: must contain exactly {', '.join(sorted(architectures))}")
    normalized: dict[str, Any] = {}
    for architecture in sorted(artifacts):
        context = f"cluster.artifacts.{architecture}"
        artifact = as_mapping(artifacts[architecture], context)
        require_unknown_keys(artifact, {"url", "sha256", "proxy_url", "credential_ref"}, context)
        proxy_url = artifact.get("proxy_url")
        credential_ref = artifact.get("credential_ref")
        url = _url(artifact.get("url"), f"{context}.url", https_only=True)
        require(
            f"/{version}/" in urlsplit(url).path,
            f"{context}.url: must contain the exact cluster.version as a path segment",
        )
        normalized[architecture] = {
            "url": url,
            "sha256": _sha256(artifact.get("sha256"), f"{context}.sha256"),
            "proxy_url": _url(proxy_url, f"{context}.proxy_url", https_only=False) if proxy_url is not None else None,
            "credential_ref": _secret_ref(credential_ref, f"{context}.credential_ref") if credential_ref is not None else None,
        }
    return normalized


def _validate_components(value: Any) -> dict[str, Any]:
    components = as_mapping(value, "cluster.components")
    require_unknown_keys(components, {"external_cni", "disable_network_policy", "disable"}, "cluster.components")
    require(require_bool(components.get("external_cni"), "cluster.components.external_cni"), "cluster.components.external_cni: must be true in the first version")
    require(
        require_bool(components.get("disable_network_policy"), "cluster.components.disable_network_policy"),
        "cluster.components.disable_network_policy: must be true with external CNI",
    )
    disabled = as_list(components.get("disable"), "cluster.components.disable")
    require(all(isinstance(item, str) for item in disabled), "cluster.components.disable: must contain strings")
    require(len(disabled) == len(set(disabled)), "cluster.components.disable: duplicate entries are not allowed")
    require(set(disabled) == {"servicelb", "traefik"}, "cluster.components.disable: must contain servicelb and traefik")
    return {"external_cni": True, "disable_network_policy": True, "disable": sorted(disabled)}


def _supports_registry_fallback_deny(version: str) -> bool:
    match = K3S_VERSION_RE.fullmatch(version)
    assert match is not None
    major, minor, patch = (int(part) for part in version.removeprefix("v").split("+", 1)[0].split("."))
    minimum_patches = {26: 13, 27: 10, 28: 6, 29: 1}
    if major != 1 or minor < 26:
        return False
    if minor > 29:
        return True
    return patch >= minimum_patches[minor]


def _validate_registry(value: Any, version: str) -> tuple[dict[str, Any], list[str]]:
    registry = as_mapping(value, "cluster.registry")
    require_unknown_keys(registry, {"fallback", "mirrors"}, "cluster.registry")
    fallback = _choice(registry.get("fallback"), "cluster.registry.fallback", {"allow", "deny"})
    require(
        fallback == "allow" or _supports_registry_fallback_deny(version),
        f"cluster.registry.fallback deny is not supported by K3s version {version}",
    )
    raw_mirrors = as_list(registry.get("mirrors"), "cluster.registry.mirrors")
    require(fallback == "allow" or raw_mirrors, "cluster.registry.mirrors: fallback deny requires at least one mirror")
    normalized: list[dict[str, Any]] = []
    endpoint_hosts: list[str] = []
    seen: set[str] = set()
    endpoint_policies: dict[str, dict[str, Any]] = {}
    for index, raw_mirror in enumerate(raw_mirrors):
        context = f"cluster.registry.mirrors[{index}]"
        mirror = as_mapping(raw_mirror, context)
        require_unknown_keys(
            mirror,
            {
                "registry",
                "endpoint",
                "ca_ref",
                "ca_sha256",
                "auth_ref",
                "client_cert_ref",
                "client_cert_sha256",
                "client_key_ref",
                "rewrites",
            },
            context,
        )
        name = _registry_name(mirror.get("registry"), f"{context}.registry")
        require(name not in seen, f"{context}.registry: duplicate registry {name}")
        seen.add(name)
        endpoint = _url(mirror.get("endpoint"), f"{context}.endpoint", https_only=True)
        endpoint_host = urlsplit(endpoint).hostname
        assert endpoint_host is not None
        endpoint_hosts.append(endpoint_host)
        ca_ref = mirror.get("ca_ref")
        ca_sha256 = mirror.get("ca_sha256")
        auth_ref = mirror.get("auth_ref")
        client_cert_ref = mirror.get("client_cert_ref")
        client_cert_sha256 = mirror.get("client_cert_sha256")
        client_key_ref = mirror.get("client_key_ref")
        require(
            (ca_ref is None) == (ca_sha256 is None),
            f"{context}: custom CA TLS material requires both ca_ref and ca_sha256",
        )
        client_tls_values = (client_cert_ref, client_cert_sha256, client_key_ref)
        require(
            all(item is None for item in client_tls_values) or all(item is not None for item in client_tls_values),
            f"{context}: client TLS material requires client_cert_ref, client_cert_sha256, and client_key_ref",
        )
        rewrites = as_mapping(mirror.get("rewrites", {}), f"{context}.rewrites")
        require(
            all(isinstance(key, str) and key and isinstance(item, str) and item for key, item in rewrites.items()),
            f"{context}.rewrites: keys and values must be non-empty strings",
        )
        for pattern, replacement in rewrites.items():
            require(
                REGISTRY_REWRITE_PATTERN_RE.fullmatch(pattern) is not None
                or pattern in {"(^.+$)", "^(.+)$"},
                f"{context}.rewrites: patterns must use the anchored literal RE2-compatible prefix subset",
            )
            require(
                REGISTRY_REWRITE_REPLACEMENT_RE.fullmatch(replacement) is not None,
                f"{context}.rewrites: replacement must use bounded repository path segments and optional $1",
            )
            require(
                "$1" not in replacement or pattern.endswith("(.*)") or pattern.endswith("(.*)$")
                or pattern in {"(^.+$)", "^(.+)$"},
                f"{context}.rewrites: replacement $1 requires the supported capture suffix",
            )
        normalized.append({
            "registry": name,
            "endpoint": endpoint,
            "ca_ref": _secret_ref(ca_ref, f"{context}.ca_ref") if ca_ref is not None else None,
            "ca_sha256": _sha256(ca_sha256, f"{context}.ca_sha256") if ca_sha256 is not None else None,
            "auth_ref": _secret_ref(auth_ref, f"{context}.auth_ref") if auth_ref is not None else None,
            "client_cert_ref": (
                _secret_ref(client_cert_ref, f"{context}.client_cert_ref")
                if client_cert_ref is not None
                else None
            ),
            "client_cert_sha256": (
                _sha256(client_cert_sha256, f"{context}.client_cert_sha256")
                if client_cert_sha256 is not None
                else None
            ),
            "client_key_ref": (
                _secret_ref(client_key_ref, f"{context}.client_key_ref")
                if client_key_ref is not None
                else None
            ),
            "rewrites": dict(sorted(rewrites.items())),
        })
        authority = urlsplit(endpoint).netloc.lower()
        policy = {key: normalized[-1][key] for key in (
            "auth_ref", "ca_ref", "ca_sha256", "client_cert_ref", "client_cert_sha256", "client_key_ref"
        )}
        require(
            authority not in endpoint_policies or endpoint_policies[authority] == policy,
            f"{context}: conflicting authentication or TLS policy for shared endpoint {authority}",
        )
        endpoint_policies[authority] = policy
    return {"fallback": fallback, "mirrors": normalized}, endpoint_hosts


def _validate_no_proxy_item(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    require(not any(character.isspace() for character in text), f"{context}: must not contain whitespace")
    if "/" in text:
        network = _network(text, context)
        minimum_prefix = 8 if network.version == 4 else 32
        require(network.prefixlen >= minimum_prefix, f"{context}: overbroad network bypass is not allowed")
        public_minimum_prefix = 24 if network.version == 4 else 64
        if not (network.is_private or network.is_loopback or network.is_link_local):
            require(
                network.prefixlen >= public_minimum_prefix,
                f"{context}: overbroad public network bypass is not allowed",
            )
        return str(network)
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        require(
            not text.startswith(".") and text.count(".") >= 2 and SLUG_RE.fullmatch(text) is not None,
            f"{context}: must be an explicit fully-qualified host, IP, or bounded subnet",
        )
        return text


def _validate_service_proxy(value: Any) -> tuple[dict[str, Any], list[str]]:
    proxy = as_mapping(value, "cluster.service_proxy")
    require_unknown_keys(proxy, {"state", "url", "credential_ref", "extra_no_proxy"}, "cluster.service_proxy")
    state = _choice(proxy.get("state"), "cluster.service_proxy.state", {"absent", "present"})
    url = proxy.get("url")
    credential_ref = proxy.get("credential_ref")
    if state == "present":
        normalized_url = _url(url, "cluster.service_proxy.url", https_only=False)
        normalized_ref = _secret_ref(credential_ref, "cluster.service_proxy.credential_ref") if credential_ref is not None else None
    else:
        require(url is None and credential_ref is None, "cluster.service_proxy: absent state must not declare url or credential_ref")
        normalized_url = None
        normalized_ref = None
    extras = [
        _validate_no_proxy_item(item, f"cluster.service_proxy.extra_no_proxy[{index}]")
        for index, item in enumerate(as_list(proxy.get("extra_no_proxy", []), "cluster.service_proxy.extra_no_proxy"))
    ]
    require(len(extras) == len(set(extras)), "cluster.service_proxy.extra_no_proxy: duplicate entry")
    return {"state": state, "url": normalized_url, "credential_ref": normalized_ref}, extras


def _snapshot(value: Any, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot = as_mapping(value, "cluster.snapshot")
    require_unknown_keys(snapshot, {"source_vm_ref"}, "cluster.snapshot")
    source = require_non_empty_string(snapshot.get("source_vm_ref"), "cluster.snapshot.source_vm_ref")
    source_node = next((node for node in nodes if node["vm_ref"] == source), None)
    require(source_node is not None and source_node["role"] == "server", "cluster.snapshot.source_vm_ref: must reference a declared server")
    return {
        "source_vm_ref": source,
        "directory": "/var/lib/rancher/k3s/server/db/snapshots",
    }


def build_composed_model(intent_doc: dict[str, Any], inventory_doc: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic K3s intent composed with generated VM host facts."""
    require_unknown_keys(intent_doc, {"schema_version", "cluster", "nodes"}, "intent")
    require(intent_doc.get("schema_version") == 1, "intent.schema_version: must be 1")
    cluster = as_mapping(intent_doc.get("cluster"), "cluster")
    require_unknown_keys(
        cluster,
        {
            "name",
            "version",
            "datastore",
            "node_network_role",
            "cluster_domain",
            "server_token_ref",
            "api_endpoint",
            "networking",
            "artifacts",
            "components",
            "registry",
            "service_proxy",
            "snapshot",
        },
        "cluster",
    )
    name = require_non_empty_string(cluster.get("name"), "cluster.name")
    require(SLUG_RE.fullmatch(name) is not None, "cluster.name: must be a lower-case slug")
    version = require_non_empty_string(cluster.get("version"), "cluster.version")
    require(K3S_VERSION_RE.fullmatch(version) is not None, "cluster.version: must be an exact vX.Y.Z+k3sN version")
    require(cluster.get("datastore") == "embedded-etcd", "cluster.datastore: must be embedded-etcd")
    node_network_role = _choice(cluster.get("node_network_role"), "cluster.node_network_role", NODE_NETWORK_ROLES)
    cluster_domain = require_non_empty_string(cluster.get("cluster_domain"), "cluster.cluster_domain")
    require(SLUG_RE.fullmatch(cluster_domain) is not None and "." in cluster_domain, "cluster.cluster_domain: must be a DNS name")
    server_token_ref = _secret_ref(cluster.get("server_token_ref"), "cluster.server_token_ref")

    hosts = _generated_hosts(inventory_doc)
    raw_nodes = as_list(intent_doc.get("nodes"), "nodes")
    require(raw_nodes, "nodes: must not be empty")
    nodes: list[dict[str, Any]] = []
    vm_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    seen_refs: set[str] = set()
    seen_node_ips: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        node, host_networks = _compose_node(as_mapping(raw_node, f"nodes[{index}]"), index, hosts, node_network_role)
        require(node["vm_ref"] not in seen_refs, f"nodes[{index}].vm_ref: duplicate {node['vm_ref']}")
        require(node["node_ip"] not in seen_node_ips, f"nodes[{index}]: duplicate derived node IP {node['node_ip']}")
        seen_refs.add(node["vm_ref"])
        seen_node_ips.add(node["node_ip"])
        nodes.append(node)
        vm_networks.extend(host_networks)

    servers = [node for node in nodes if node["role"] == "server"]
    bootstrap_servers = [node for node in servers if node["bootstrap"]]
    require(len(servers) == 1 or (len(servers) >= 3 and len(servers) % 2 == 1), "nodes: embedded-etcd requires one or an odd number of at least three servers")
    require(len(bootstrap_servers) == 1, "nodes: exactly one server must set bootstrap true")

    networking = as_mapping(cluster.get("networking"), "cluster.networking")
    require_unknown_keys(networking, {"pod_cidr", "service_cidr"}, "cluster.networking")
    pod_network = _network(networking.get("pod_cidr"), "cluster.networking.pod_cidr")
    service_network = _network(networking.get("service_cidr"), "cluster.networking.service_cidr")
    require(pod_network.version == service_network.version, "cluster.networking: pod_cidr and service_cidr must use the same address family")
    minimum_service_prefix = 12 if service_network.version == 4 else 112
    require(
        service_network.prefixlen >= minimum_service_prefix,
        f"cluster.networking.service_cidr: maximum supported size is /{minimum_service_prefix}",
    )
    require(
        all(ipaddress.ip_address(node["node_ip"]).version == pod_network.version for node in nodes),
        "cluster.networking: derived node IPs must use the cluster address family",
    )
    require(not pod_network.overlaps(service_network), "cluster.networking: pod_cidr and service_cidr must not overlap")
    for candidate_name, candidate in (("pod_cidr", pod_network), ("service_cidr", service_network)):
        for vm_network in vm_networks:
            if candidate.version == vm_network.version:
                require(not candidate.overlaps(vm_network), f"cluster.networking.{candidate_name}: must not overlap VM subnet {vm_network}")

    endpoint_doc = as_mapping(cluster.get("api_endpoint"), "cluster.api_endpoint")
    mode = _choice(endpoint_doc.get("mode"), "cluster.api_endpoint.mode", {"bootstrap", "fixed"})
    if mode == "bootstrap":
        require_unknown_keys(endpoint_doc, {"mode"}, "cluster.api_endpoint")
        endpoint = {"mode": mode, "address": bootstrap_servers[0]["node_ip"], "tls_sans": []}
    else:
        require_unknown_keys(endpoint_doc, {"mode", "address"}, "cluster.api_endpoint")
        address = _endpoint_address(endpoint_doc.get("address"), "cluster.api_endpoint.address")
        require(address not in seen_node_ips, "cluster.api_endpoint.address: fixed endpoint must not repeat a selected node IP")
        endpoint = {"mode": mode, "address": address, "tls_sans": [address]}

    architectures = {node["architecture"] for node in nodes}
    components = _validate_components(cluster.get("components"))
    registry, registry_hosts = _validate_registry(cluster.get("registry"), version)
    artifacts = _validate_artifacts(cluster.get("artifacts"), architectures, version)
    service_proxy, extra_no_proxy = _validate_service_proxy(cluster.get("service_proxy"))
    no_proxy = {
        "localhost",
        "127.0.0.1",
        "::1",
        cluster_domain,
        endpoint["address"],
        str(pod_network),
        str(service_network),
        *(node["node_ip"] for node in nodes),
        *(node["node_network"] for node in nodes),
        *registry_hosts,
        *extra_no_proxy,
    }
    service_proxy["no_proxy"] = sorted(no_proxy)

    normalized_cluster = {
        "name": name,
        "version": version,
        "datastore": "embedded-etcd",
        "node_network_role": node_network_role,
        "cluster_domain": cluster_domain,
        "server_token_ref": server_token_ref,
        "api_endpoint": endpoint,
        "networking": {"pod_cidr": str(pod_network), "service_cidr": str(service_network)},
        "artifacts": artifacts,
        "components": components,
        "registry": registry,
        "service_proxy": service_proxy,
        "snapshot": _snapshot(cluster.get("snapshot"), nodes),
    }
    return {"schema_version": 1, "cluster": normalized_cluster, "nodes": nodes}


def render_review(model: dict[str, Any]) -> str:
    """Render a deterministic non-secret review document."""
    return yaml.safe_dump(model, sort_keys=True, default_flow_style=False, explicit_start=True)
