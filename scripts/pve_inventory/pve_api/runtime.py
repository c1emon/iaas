"""Shared runtime parsing for repository-owned PVE online checks."""

from __future__ import annotations

import os
from dataclasses import dataclass

from scripts.common.errors import ValidationError


@dataclass(frozen=True)
class PveApiRuntimeConfig:
    """Normalized API credentials and TLS mode."""

    endpoint: str
    api_username: str
    api_token_id: str
    api_token_secret: str
    insecure: bool


@dataclass(frozen=True)
class PveOnlineRuntimeContext(PveApiRuntimeConfig):
    """API credentials plus optional SSH adjunct context."""

    ssh_host: str | None = None
    ssh_user: str | None = None


def parse_pve_bool(value: str | None, *, default: bool = False) -> bool:
    """Parse Terraform-style boolean text with a stable validation error."""

    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError(f"TF_VAR_pve_insecure must be a boolean-like value, got {value!r}")


def _load_base_runtime_config(environ: dict[str, str] | None = None, *, require_api: bool) -> tuple[str, str, str, str, bool]:
    env = os.environ if environ is None else environ
    endpoint = env.get("TF_VAR_pve_endpoint", "").strip()
    api_username = env.get("TF_VAR_pve_api_username", "").strip()
    api_token_id = env.get("TF_VAR_pve_api_token_id", "").strip()
    api_token_secret = env.get("TF_VAR_pve_api_token_secret", "").strip()
    insecure = parse_pve_bool(env.get("TF_VAR_pve_insecure"), default=False)

    if require_api:
        missing = [name for name, value in (
            ("TF_VAR_pve_endpoint", endpoint),
            ("TF_VAR_pve_api_username", api_username),
            ("TF_VAR_pve_api_token_id", api_token_id),
            ("TF_VAR_pve_api_token_secret", api_token_secret),
        ) if not value]
        if missing:
            raise ValidationError(f"missing required PVE runtime environment variables: {', '.join(missing)}")

    return endpoint, api_username, api_token_id, api_token_secret, insecure


def load_api_runtime_config(environ: dict[str, str] | None = None) -> PveApiRuntimeConfig:
    """Load the API-only runtime config used by health checks."""

    endpoint, api_username, api_token_id, api_token_secret, insecure = _load_base_runtime_config(environ, require_api=True)
    return PveApiRuntimeConfig(
        endpoint=endpoint,
        api_username=api_username,
        api_token_id=api_token_id,
        api_token_secret=api_token_secret,
        insecure=insecure,
    )


def load_online_runtime_context(environ: dict[str, str] | None = None) -> PveOnlineRuntimeContext:
    """Load the preflight runtime context, including optional SSH inputs."""

    endpoint, api_username, api_token_id, api_token_secret, insecure = _load_base_runtime_config(environ, require_api=False)
    env = os.environ if environ is None else environ
    ssh_host = env.get("PVE_HOST", "").strip() or None
    ssh_user = env.get("PVE_SSH_USER", "").strip() or None
    return PveOnlineRuntimeContext(
        endpoint=endpoint,
        api_username=api_username,
        api_token_id=api_token_id,
        api_token_secret=api_token_secret,
        insecure=insecure,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
    )


__all__ = [
    "PveApiRuntimeConfig",
    "PveOnlineRuntimeContext",
    "load_api_runtime_config",
    "load_online_runtime_context",
    "parse_pve_bool",
]
