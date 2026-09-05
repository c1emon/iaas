"""Normalize the narrow, environment-owned VM baseline egress policy."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from ansible.errors import AnsibleFilterError


_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_HOST = re.compile(r"^\.?[A-Za-z0-9][A-Za-z0-9.-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT = re.compile(r"^[0-9A-F]{40}(?:[0-9A-F]{24})?$")
_POLICY_KEYS = {
    "state",
    "sources",
    "keyrings",
    "custom_cas",
    "proxy",
    "extra_bypass",
    "exclusive_sources",
    "shell_proxy",
    "git_proxy",
}


def _fail(message: str) -> None:
    raise AnsibleFilterError(f"vm_baseline_egress_policy: {message}")


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{context} must be a mapping")
    return value


def _list(value: Any, context: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail(f"{context} must be a list")
    return value


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{context} must be a non-empty string")
    return value


def _identifier(value: Any, context: str) -> str:
    result = _string(value, context)
    if not _IDENTIFIER.fullmatch(result):
        _fail(f"{context} must be a lowercase role-owned identifier")
    return result


def _sha256(value: Any, context: str) -> str:
    result = _string(value, context).lower()
    if not _SHA256.fullmatch(result):
        _fail(f"{context} must be an exact SHA-256 digest")
    return result


def _endpoint(value: Any, context: str, *, allow_secret: bool = False) -> str:
    endpoint = _string(value, context)
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
        _fail(f"{context} must be an http(s) endpoint without a path")
    if not allow_secret and (parsed.username is not None or parsed.password is not None):
        _fail(f"{context} must not contain credentials")
    return endpoint.rstrip("/")


def _bypass(value: Any, context: str) -> str:
    destination = _string(value, context)
    try:
        ipaddress.ip_network(destination, strict=False)
        return destination
    except ValueError:
        pass
    if not _HOST.fullmatch(destination) or "://" in destination or "/" in destination:
        _fail(f"{context} must be a host, domain, address, or subnet")
    return destination.lower()


def _keys(value: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        _fail(f"{context} has unknown keys: {', '.join(unknown)}")


def _role_path(directory: str, identifier: str, suffix: str) -> str:
    return f"{directory}/vm-baseline-{identifier}{suffix}"


def _normalize_keyring(raw: Any, index: int, state: str) -> dict[str, Any]:
    value = _mapping(raw, f"keyrings[{index}]")
    _keys(value, {"id", "kind", "artifact", "sha256", "path", "fingerprint"}, f"keyrings[{index}]")
    identifier = _identifier(value.get("id"), f"keyrings[{index}].id")
    kind = _string(value.get("kind"), f"keyrings[{index}].kind")
    result: dict[str, Any] = {
        "id": identifier,
        "kind": kind,
        "managed_path": _role_path("/etc/apt/keyrings", identifier, ".gpg"),
    }
    if state == "absent":
        if kind not in {"role_managed", "package_managed"}:
            _fail(f"keyrings[{index}].kind must be role_managed or package_managed")
        return result
    if kind == "role_managed":
        artifact = _string(value.get("artifact"), f"keyrings[{index}].artifact")
        if not artifact.startswith("/"):
            _fail(f"keyrings[{index}].artifact must be an absolute controller path")
        result.update(artifact=artifact, sha256=_sha256(value.get("sha256"), f"keyrings[{index}].sha256"))
    elif kind == "package_managed":
        path = _string(value.get("path"), f"keyrings[{index}].path")
        if not path.startswith(("/etc/apt/keyrings/", "/usr/share/keyrings/")):
            _fail(f"keyrings[{index}].path must be an allowed APT keyring path")
        fingerprint = _string(value.get("fingerprint"), f"keyrings[{index}].fingerprint").replace(" ", "").upper()
        if not _FINGERPRINT.fullmatch(fingerprint):
            _fail(f"keyrings[{index}].fingerprint must be an exact OpenPGP fingerprint")
        result.update(path=path, fingerprint=fingerprint)
    else:
        _fail(f"keyrings[{index}].kind must be role_managed or package_managed")
    return result


def _normalize_source(raw: Any, index: int, keyrings: dict[str, dict[str, Any]], state: str) -> dict[str, Any]:
    value = _mapping(raw, f"sources[{index}]")
    _keys(value, {"id", "uri", "suites", "components", "keyring"}, f"sources[{index}]")
    identifier = _identifier(value.get("id"), f"sources[{index}].id")
    result: dict[str, Any] = {"id": identifier, "path": _role_path("/etc/apt/sources.list.d", identifier, ".sources")}
    if state == "absent":
        return result
    uri = _endpoint(value.get("uri"), f"sources[{index}].uri")
    suites = [_string(item, f"sources[{index}].suites") for item in _list(value.get("suites"), f"sources[{index}].suites")]
    components = [_string(item, f"sources[{index}].components") for item in _list(value.get("components"), f"sources[{index}].components")]
    if not suites or not components:
        _fail(f"sources[{index}] requires non-empty suites and components")
    keyring_id = _identifier(value.get("keyring"), f"sources[{index}].keyring")
    if keyring_id not in keyrings:
        _fail(f"sources[{index}].keyring must reference a declared keyring")
    result.update(uri=uri, suites=suites, components=components, keyring=keyrings[keyring_id])
    return result


def _normalize_ca(raw: Any, index: int, state: str) -> dict[str, Any]:
    value = _mapping(raw, f"custom_cas[{index}]")
    _keys(value, {"id", "artifact", "sha256"}, f"custom_cas[{index}]")
    identifier = _identifier(value.get("id"), f"custom_cas[{index}].id")
    result: dict[str, Any] = {"id": identifier, "path": _role_path("/usr/local/share/ca-certificates", identifier, ".crt")}
    if state == "absent":
        return result
    artifact = _string(value.get("artifact"), f"custom_cas[{index}].artifact")
    if not artifact.startswith("/"):
        _fail(f"custom_cas[{index}].artifact must be an absolute controller path")
    result.update(artifact=artifact, sha256=_sha256(value.get("sha256"), f"custom_cas[{index}].sha256"))
    return result


def _normalize_tool_proxy(raw: Any, name: str) -> dict[str, Any]:
    value = _mapping(raw, name)
    _keys(value, {"enabled", "endpoint"}, name)
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        _fail(f"{name}.enabled must be boolean")
    if not enabled:
        return {"enabled": False}
    return {"enabled": True, "endpoint": _endpoint(value.get("endpoint"), f"{name}.endpoint")}


def normalize(policy: Any, pve_nics: Any) -> dict[str, Any]:
    """Return validated policy data without accepting inventory-shaped policy inputs."""

    value = _mapping(policy, "policy")
    _keys(value, _POLICY_KEYS, "policy")
    state = value.get("state")
    if state not in {"present", "absent"}:
        _fail("state must be present or absent")
    keyrings_list = [_normalize_keyring(item, index, state) for index, item in enumerate(_list(value.get("keyrings", []), "keyrings"))]
    keyrings = {item["id"]: item for item in keyrings_list}
    if len(keyrings) != len(keyrings_list):
        _fail("keyring ids must be unique")
    sources = [_normalize_source(item, index, keyrings, state) for index, item in enumerate(_list(value.get("sources", []), "sources"))]
    cas = [_normalize_ca(item, index, state) for index, item in enumerate(_list(value.get("custom_cas", []), "custom_cas"))]
    if len({item["id"] for item in sources}) != len(sources) or len({item["id"] for item in cas}) != len(cas):
        _fail("source and custom CA ids must be unique")
    if state == "present" and not sources:
        _fail("present policy requires at least one source")

    proxy = _mapping(value.get("proxy", {"mode": "direct"}), "proxy")
    _keys(proxy, {"mode", "endpoint", "secret_ref"}, "proxy")
    mode = proxy.get("mode", "direct")
    if mode not in {"direct", "proxy"}:
        _fail("proxy.mode must be direct or proxy")
    normalized_proxy: dict[str, Any] = {"mode": mode}
    if mode == "proxy":
        normalized_proxy["endpoint"] = _endpoint(proxy.get("endpoint"), "proxy.endpoint")
        if "secret_ref" in proxy:
            secret_ref = _string(proxy["secret_ref"], "proxy.secret_ref")
            if not secret_ref.startswith("op://"):
                _fail("proxy.secret_ref must be an external op:// reference")
            normalized_proxy["secret_ref"] = secret_ref

    extra_bypass = [_bypass(item, "extra_bypass") for item in _list(value.get("extra_bypass", []), "extra_bypass")]
    nic_bypass: list[str] = []
    for index, raw_nic in enumerate(_list(pve_nics, "pve_nics")):
        nic = _mapping(raw_nic, f"pve_nics[{index}]")
        nic_bypass.append(_bypass(nic.get("ip_address"), f"pve_nics[{index}].ip_address"))
        nic_bypass.append(_bypass(nic.get("network_cidr"), f"pve_nics[{index}].network_cidr"))
    source_hosts = sorted({urlparse(source["uri"]).hostname for source in sources if "uri" in source})

    exclusive_sources = value.get("exclusive_sources", False)
    if not isinstance(exclusive_sources, bool):
        _fail("exclusive_sources must be boolean")
    shell_proxy = _normalize_tool_proxy(value.get("shell_proxy", {}), "shell_proxy")
    git_proxy = _normalize_tool_proxy(value.get("git_proxy", {}), "git_proxy")
    return {
        "state": state,
        "keyrings": keyrings_list,
        "sources": sources,
        "custom_cas": cas,
        "proxy": normalized_proxy,
        "exclusive_sources": exclusive_sources,
        "apt_direct_hosts": source_hosts,
        "tool_bypass": sorted(set(nic_bypass + extra_bypass)),
        "shell_proxy": shell_proxy,
        "git_proxy": git_proxy,
        "proxy_path": "/etc/apt/apt.conf.d/80-vm-baseline-proxy",
        "auth_path": "/etc/apt/auth.conf.d/80-vm-baseline-auth.conf",
        "shell_path": "/etc/profile.d/vm-baseline-proxy.sh",
        "git_path": "/etc/gitconfig.d/vm-baseline-proxy.conf",
    }


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {"vm_baseline_egress_normalize": normalize}
