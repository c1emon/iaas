"""Read-only PVE API adapter package backed by proxmoxer."""

from .client import HealthApiRuntimeConfig, ReadOnlyPveApi
from .errors import (
    PveApiAuthenticationError,
    PveApiError,
    PveApiNotConfiguredError,
    PveApiUnavailableError,
    redact_sensitive_text,
)

__all__ = [
    "PveApiAuthenticationError",
    "PveApiError",
    "PveApiNotConfiguredError",
    "PveApiUnavailableError",
    "HealthApiRuntimeConfig",
    "ReadOnlyPveApi",
    "redact_sensitive_text",
]
