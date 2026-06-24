"""Environment parsing for preflight runtime credentials.

The online preflight is intentionally explicit: API checks require the PVE
token variables, while SSH adjunct checks remain optional and are skipped when
not provided.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import ValidationError


@dataclass(frozen=True)
class RuntimeConfig:
    """Normalized runtime inputs for API and optional SSH checks."""
    endpoint: str
    api_username: str
    api_token_id: str
    api_token_secret: str
    insecure: bool
    ssh_host: str | None
    ssh_user: str | None


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    """Accept Terraform-style boolean strings from the environment."""
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError(f"TF_VAR_pve_insecure must be a boolean-like value, got {value!r}")


def _load_runtime_config(environ: dict[str, str] | None = None, *, require_api: bool) -> RuntimeConfig:
    """Load config once; callers choose whether missing API vars are fatal."""
    env = os.environ if environ is None else environ
    endpoint = env.get("TF_VAR_pve_endpoint", "").strip()
    api_username = env.get("TF_VAR_pve_api_username", "").strip()
    api_token_id = env.get("TF_VAR_pve_api_token_id", "").strip()
    api_token_secret = env.get("TF_VAR_pve_api_token_secret", "").strip()
    insecure = _parse_bool(env.get("TF_VAR_pve_insecure"), default=False)

    if require_api:
        missing = [name for name, value in (
            ("TF_VAR_pve_endpoint", endpoint),
            ("TF_VAR_pve_api_username", api_username),
            ("TF_VAR_pve_api_token_id", api_token_id),
            ("TF_VAR_pve_api_token_secret", api_token_secret),
        ) if not value]
        if missing:
            raise ValidationError(f"missing required PVE runtime environment variables: {', '.join(missing)}")

    ssh_host = env.get("PVE_HOST", "").strip() or None
    ssh_user = env.get("PVE_SSH_USER", "").strip() or None
    return RuntimeConfig(
        endpoint=endpoint,
        api_username=api_username,
        api_token_id=api_token_id,
        api_token_secret=api_token_secret,
        insecure=insecure,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
    )


def load_runtime_config(environ: dict[str, str] | None = None) -> RuntimeConfig:
    """Load runtime config for the normal API-first preflight path."""
    return _load_runtime_config(environ, require_api=True)


def load_runtime_context(environ: dict[str, str] | None = None) -> RuntimeConfig:
    """Load runtime context when API credentials are already provided externally."""
    return _load_runtime_config(environ, require_api=False)
