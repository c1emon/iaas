"""Shared validation errors and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_CODES: dict[str, frozenset[str]] = {
    "validation": frozenset({"invalid_value"}),
    "conversion": frozenset({"invalid_value", "invalid_boolean", "malformed_native_selector",
                             "malformed_provider_row", "conflicting_native_alias",
                             "invalid_identity_or_reference", "invalid_configuration"}),
    "http_transport": frozenset({"http_failure", "timeout", "transport_failure", "malformed_json",
                                 "malformed_response_body", "response_bound_exceeded",
                                 "observation_deadline_exhausted"}),
    "pve_api": frozenset({"api_failure", "authentication_failed", "endpoint_unavailable", "service_unavailable"}),
}
_FIELD_NAMES = frozenset({"value", "row", "selected", "identity", "references"})


@dataclass(frozen=True)
class Diagnostic:
    """Small safe description; never accepts backend messages or arbitrary context."""

    component: str
    code: str
    field_path: tuple[str | int, ...] | None = None
    status_code: int | None = None

    def __post_init__(self) -> None:
        if self.component not in _CODES or self.code not in _CODES[self.component]:
            raise ValueError("unsupported diagnostic component or code")
        if self.field_path is not None:
            # Runtime dataclass callers may not have passed static type checks.
            if not isinstance(self.field_path, tuple) or not self.field_path:  # pyright: ignore[reportUnnecessaryIsInstance]
                raise ValueError("invalid diagnostic field path")
            for part in self.field_path:
                if not ((type(part) is int and part >= 0) or (isinstance(part, str) and part in _FIELD_NAMES)):
                    raise ValueError("invalid diagnostic field path")
        if self.status_code is not None and (type(self.status_code) is not int or not 100 <= self.status_code <= 599):
            raise ValueError("invalid diagnostic HTTP status")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"component": self.component, "code": self.code}
        if self.field_path is not None:
            result["field_path"] = list(self.field_path)
        if self.status_code is not None:
            result["status_code"] = self.status_code
        return result


class ValidationError(ValueError):
    def __init__(self, *args: object, diagnostic: Diagnostic | None = None) -> None:
        super().__init__(*args)
        self.diagnostic = diagnostic


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ValidationError(message)
