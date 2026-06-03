"""Switch profile registry."""

from __future__ import annotations

from typing import Any

from .errors import UnsupportedSwitchProfileError
from .sks8300.profile import PROFILE as SKS8300_PROFILE

PROFILES: dict[str, Any] = {
    SKS8300_PROFILE.name: SKS8300_PROFILE,
}


def get_profile(name: str) -> Any:
    """Return a registered profile or raise a clear validation error."""
    normalized = (name or "").strip().lower()
    if normalized in PROFILES:
        return PROFILES[normalized]
    supported = ", ".join(sorted(PROFILES))
    raise UnsupportedSwitchProfileError(
        f"Unsupported switch_platform_profile '{name}'. Supported profiles: {supported}"
    )


def supported_profiles() -> list[str]:
    """Return registered profile names."""
    return sorted(PROFILES)
