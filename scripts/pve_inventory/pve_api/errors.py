"""Safe repository exceptions for read-only PVE API access."""

from __future__ import annotations


def redact_sensitive_text(text: str, secrets: list[str]) -> str:
    """Redact any known secrets from operator-visible text."""
    redacted = text
    for secret in sorted({value for value in secrets if value}, key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")
    return redacted


class PveApiError(RuntimeError):
    """Base safe exception for proxmoxer failures."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PveApiAuthenticationError(PveApiError):
    """Authentication or authorization failure."""


class PveApiNotConfiguredError(PveApiError):
    """Optional endpoint is missing or not configured (404)."""


class PveApiUnavailableError(PveApiError):
    """Endpoint reached but the service was unavailable."""
