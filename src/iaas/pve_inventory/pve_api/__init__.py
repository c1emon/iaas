"""Read-only PVE API adapter package backed by proxmoxer."""

from .client import HealthApiRuntimeConfig, ReadOnlyPveApi
from .errors import (
    PveApiAuthenticationError,
    PveApiError,
    PveApiTlsError,
    PveApiNotConfiguredError,
    PveApiUnavailableError,
    redact_sensitive_text,
)
from .protocol import PveReadOnlyApi
from .runtime import PveApiRuntimeConfig, PveOnlineRuntimeContext, load_api_runtime_config, load_online_runtime_context, parse_pve_bool

__all__ = [
    "PveApiAuthenticationError",
    "PveApiError",
    "PveApiTlsError",
    "PveApiNotConfiguredError",
    "PveApiUnavailableError",
    "PveApiRuntimeConfig",
    "PveOnlineRuntimeContext",
    "PveReadOnlyApi",
    "HealthApiRuntimeConfig",
    "ReadOnlyPveApi",
    "load_api_runtime_config",
    "load_online_runtime_context",
    "parse_pve_bool",
    "redact_sensitive_text",
]
