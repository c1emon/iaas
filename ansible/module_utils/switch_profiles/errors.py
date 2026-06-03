"""Shared switch profile errors."""

from __future__ import annotations


class SwitchProfileError(ValueError):
    """Base error for switch profile validation and planning."""


class UnsupportedSwitchProfileError(SwitchProfileError):
    """Raised when an unknown platform profile is requested."""


class UnsupportedGatherSubsetError(SwitchProfileError):
    """Raised when an unknown read-only gather subset is requested."""


class UnsafeCommandError(SwitchProfileError):
    """Raised when a command definition is not read-only safe."""
