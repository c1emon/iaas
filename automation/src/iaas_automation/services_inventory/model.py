"""Model assembly for validated service metadata."""

from __future__ import annotations

from typing import Any


def build_model(services: list[dict[str, Any]], warnings: list[dict[str, str]]) -> dict[str, Any]:
    """Combine validated service data into the renderer model."""
    return {
        "services": services,
        "warnings": warnings,
    }
