"""Small, bounded HTTP JSON reads for already-admitted adapters."""

from .read import (
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    HttpResponse,
    HttpSession,
    ReadBudget,
    TransportFailure,
    read_json,
)

__all__ = [
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_MAX_TOTAL_BYTES",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS",
    "HttpResponse",
    "HttpSession",
    "ReadBudget",
    "TransportFailure",
    "read_json",
]
