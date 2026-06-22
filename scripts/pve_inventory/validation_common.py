"""Shared validation helpers for PVE inventory source-of-truth YAML."""

from __future__ import annotations

import re
from typing import Any, cast

from .errors import require


def as_mapping(value: Any, context: str) -> dict[str, Any]:
    """Assert that a value is a mapping and cast it for type-checkers."""
    require(isinstance(value, dict), f"{context}: expected mapping")
    return cast(dict[str, Any], value)


def as_list(value: Any, context: str) -> list[Any]:
    """Assert that a value is a list and cast it for type-checkers."""
    require(isinstance(value, list), f"{context}: expected list")
    return cast(list[Any], value)


def require_positive_int(value: Any, context: str) -> int:
    """Assert that a value is a positive integer and return it."""
    require(isinstance(value, int) and value > 0, f"{context}: must be a positive integer")
    return cast(int, value)


def require_bool(value: Any, context: str) -> bool:
    """Assert that a value is a boolean and return it."""
    require(isinstance(value, bool), f"{context}: must be a boolean")
    return cast(bool, value)


def require_non_empty_string(value: Any, context: str) -> str:
    """Assert that a value is a non-empty string and return it."""
    require(isinstance(value, str) and value, f"{context}: must be a non-empty string")
    return cast(str, value)


def require_unknown_keys(mapping: dict[str, Any], allowed: set[str], context: str) -> None:
    """Reject keys outside a strict schema."""
    unknown = sorted(set(mapping) - allowed)
    require(not unknown, f"{context}: unknown keys {', '.join(unknown)}")


def require_url_like(value: Any, context: str) -> str:
    """Assert that a value looks like a conservative HTTP(S) URL."""
    text = require_non_empty_string(value, context)
    require(re.match(r"^https?://[^\s]+$", text) is not None, f"{context}: must look like a URL")
    return text
