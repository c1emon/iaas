"""Pure, non-secret platform handoff validation and rendering."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import yaml

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.validation import as_mapping, require_non_empty_string, require_unknown_keys
from iaas_automation.k3s_automation.config import _secret_ref
from iaas_automation.k3s_automation.operations import validate_deployment_scope


def _git_url(value: Any) -> str:
    text = require_non_empty_string(value, "platform_repository.url")
    require(not any(character.isspace() for character in text), "platform_repository.url: must not contain whitespace")
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("platform_repository.url: must be a valid https or ssh Git URL") from exc
    require(parsed.scheme in {"https", "ssh"} and parsed.hostname is not None, "platform_repository.url: must use https or ssh with a host")
    require(port is None or port > 0, "platform_repository.url: port must be valid")
    require(parsed.password is None, "platform_repository.url: passwords are not allowed")
    require(not parsed.query and not parsed.fragment, "platform_repository.url: query strings and fragments are not allowed")
    if parsed.scheme == "https":
        require(parsed.username is None, "platform_repository.url: HTTPS user information is not allowed")
    require(parsed.path not in {"", "/"}, "platform_repository.url: must include a repository path")
    return text


def _repository_path(value: Any) -> str:
    text = require_non_empty_string(value, "platform_repository.path")
    path = PurePosixPath(text)
    require(not path.is_absolute() and str(path) not in {".", ""}, "platform_repository.path: must be repository-relative")
    require(".." not in path.parts and "." not in path.parts, "platform_repository.path: must be normalized and safe")
    return str(path)


def _api_endpoint(address: Any) -> str:
    text = require_non_empty_string(address, "K3s API endpoint")
    try:
        parsed = ipaddress.ip_address(text)
    except ValueError:
        return f"https://{text}:6443"
    host = f"[{parsed.compressed}]" if parsed.version == 6 else parsed.compressed
    return f"https://{host}:6443"


def build_handoff(intent_doc: dict[str, Any], model: Mapping[str, Any], scope: str) -> dict[str, Any]:
    """Compose the minimum non-secret handoff form from validated inputs."""
    require_unknown_keys(intent_doc, {"schema_version", "platform"}, "handoff intent")
    require(intent_doc.get("schema_version") == 1, "handoff intent.schema_version: must be 1")
    platform = as_mapping(intent_doc.get("platform"), "platform")
    require_unknown_keys(platform, {"repository", "bootstrap_credential_ref"}, "platform")
    repository = as_mapping(platform.get("repository"), "platform.repository")
    require_unknown_keys(repository, {"url", "revision", "path"}, "platform_repository")
    selected = validate_deployment_scope(model, scope)
    cluster = as_mapping(model.get("cluster"), "composed model.cluster")
    endpoint = as_mapping(cluster.get("api_endpoint"), "composed model.cluster.api_endpoint")
    return {
        "schema_version": 1,
        "cluster": {
            "name": require_non_empty_string(cluster.get("name"), "composed model.cluster.name"),
            "version": require_non_empty_string(cluster.get("version"), "composed model.cluster.version"),
            "api_endpoint": _api_endpoint(endpoint.get("address")),
            "scope": {"class": "whole-cluster"},
        },
        "platform": {
            "repository": {
                "url": _git_url(repository.get("url")),
                "revision": require_non_empty_string(repository.get("revision"), "platform_repository.revision"),
                "path": _repository_path(repository.get("path")),
            },
            "bootstrap_credential_ref": _secret_ref(platform.get("bootstrap_credential_ref"), "bootstrap_credential_ref"),
            "reconciliation": "not-qualified",
        },
        "_validated_scope": list(selected),
    }


def attach_ca_fingerprint(handoff: Mapping[str, Any], fingerprint: str) -> dict[str, Any]:
    """Return the final bundle after the read-only CA identity check."""
    require(isinstance(fingerprint, str) and fingerprint.startswith("sha256:") and len(fingerprint) == 71, "CA fingerprint: must be sha256:<lowercase-hex>")
    digest = fingerprint.removeprefix("sha256:")
    require(all(character in "0123456789abcdef" for character in digest), "CA fingerprint: must be sha256:<lowercase-hex>")
    bundle = {key: value for key, value in handoff.items() if key != "_validated_scope"}
    cluster = dict(as_mapping(bundle["cluster"], "handoff.cluster"))
    cluster["server_ca_sha256"] = fingerprint
    bundle["cluster"] = cluster
    return bundle


def render_bundle(bundle: Mapping[str, Any]) -> str:
    """Render deterministic YAML without resolving any credential reference."""
    require("_validated_scope" not in bundle, "handoff bundle: readiness CA identity is required before rendering")
    return yaml.safe_dump(dict(bundle), sort_keys=True, default_flow_style=False, explicit_start=True)
