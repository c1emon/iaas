"""Declarative switch configuration profile orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .registry import get_profile


def build_config_collect_command_plan(intent: Any, profile: str = "sks8300") -> list[dict[str, Any]]:
    """Build the read command plan needed to collect current state for config planning."""
    return get_profile(profile).build_config_collect_command_plan(intent)


def build_config_plan(
    current_facts: Mapping[str, Any],
    intent: Any,
    allowed_operations: Sequence[str] | None = None,
    profile: str = "sks8300",
) -> dict[str, Any]:
    """Validate intent, diff against current state, render commands, and report the plan."""
    return get_profile(profile).build_config_plan(current_facts, intent, allowed_operations)


def verify_config_intent(
    current_facts: Mapping[str, Any],
    intent: Any,
    profile: str = "sks8300",
) -> dict[str, Any]:
    """Verify current state satisfies declared configuration intent."""
    return get_profile(profile).verify_config_intent(current_facts, intent)


def config_gather_subsets_for_intent(intent: Any, profile: str = "sks8300") -> list[str]:
    """Return parser gather subsets needed by the declared config intent."""
    return get_profile(profile).config_gather_subsets_for_intent(intent)
