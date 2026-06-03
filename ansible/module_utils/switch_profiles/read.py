"""Read-only switch profile orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import normalize_cli_result
from .registry import get_profile


def build_read_command_plan(gather_subset: Any, profile: str = "sks8300") -> list[dict[str, Any]]:
    """Build a safe read-only command plan for a profile."""
    return get_profile(profile).build_read_command_plan(gather_subset)


def map_cli_outputs(command_plan: Sequence[Mapping[str, Any]], cli_results: Any) -> dict[str, str]:
    """Map network_cli results to stable command IDs from the plan."""
    if cli_results is None:
        text_outputs: list[str] = []
    elif isinstance(cli_results, str):
        text_outputs = [cli_results]
    else:
        text_outputs = [normalize_cli_result(item) for item in cli_results]

    result: dict[str, str] = {}
    for command, output in zip(command_plan, text_outputs, strict=False):
        command_id = str(command.get("id", ""))
        if command_id:
            result[command_id] = output
    for command in command_plan:
        command_id = str(command.get("id", ""))
        if command_id:
            result.setdefault(command_id, "")
    return result


def parse_read_facts(
    outputs: Mapping[str, str],
    profile: str = "sks8300",
    gather_subset: Any = None,
    inventory_hostname: str = "",
) -> dict[str, Any]:
    """Parse mapped command outputs into structured read-only facts."""
    return get_profile(profile).parse_read_facts(outputs, gather_subset, inventory_hostname)


def build_raw_export_plan(
    command_plan: Sequence[Mapping[str, Any]],
    outputs: Mapping[str, str],
    profile: str = "sks8300",
) -> list[dict[str, Any]]:
    """Build raw export entries according to command-level policy."""
    return get_profile(profile).build_raw_export_plan(command_plan, outputs)
