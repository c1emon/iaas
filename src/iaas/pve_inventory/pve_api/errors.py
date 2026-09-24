"""Safe repository exceptions for read-only PVE API access."""

from __future__ import annotations

from typing import ClassVar

from iaas.common.errors import Diagnostic


def redact_sensitive_text(text: str, secrets: list[str]) -> str:
    """Redact any known secrets from operator-visible text."""
    redacted = text
    for secret in sorted({value for value in secrets if value}, key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")
    return redacted


class PveApiError(RuntimeError):
    """Base safe exception for proxmoxer failures."""

    diagnostic_code: ClassVar[str] = "api_failure"

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        safe_status = status_code if type(status_code) is int and 100 <= status_code <= 599 else None
        self.diagnostic = Diagnostic("pve_api", self.diagnostic_code, status_code=safe_status)


class PveApiAuthenticationError(PveApiError):
    """Authentication or authorization failure."""

    diagnostic_code = "authentication_failed"


class PveApiNotConfiguredError(PveApiError):
    """Optional endpoint is missing or not configured (404)."""

    diagnostic_code = "endpoint_unavailable"


class PveApiUnavailableError(PveApiError):
    """Endpoint reached but the service was unavailable."""

    diagnostic_code = "service_unavailable"
