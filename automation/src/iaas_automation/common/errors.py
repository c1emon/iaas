"""Shared validation errors and helpers."""

from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    pass


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ValidationError(message)
