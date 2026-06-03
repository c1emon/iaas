"""Thin Ansible filter facade for switch platform profiles."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ANSIBLE_DIR = Path(__file__).resolve().parents[1]
if str(ANSIBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ANSIBLE_DIR))

try:
    from ansible.module_utils.switch_profiles.read import (
        build_raw_export_plan,
        build_read_command_plan,
        map_cli_outputs,
        parse_read_facts,
    )
except ModuleNotFoundError:
    from module_utils.switch_profiles.read import (
        build_raw_export_plan,
        build_read_command_plan,
        map_cli_outputs,
        parse_read_facts,
    )


def switch_read_command_plan(gather_subset: Any, profile: str = "sks8300") -> list[dict[str, Any]]:
    """Build a profile-driven read-only command plan."""
    return build_read_command_plan(gather_subset, profile)


def switch_cli_output_map(command_plan: list[dict[str, Any]], cli_results: Any) -> dict[str, str]:
    """Map CLI results to command IDs from the command plan."""
    return map_cli_outputs(command_plan, cli_results)


def switch_parse_facts(
    outputs: dict[str, str],
    profile: str = "sks8300",
    gather_subset: Any = None,
    inventory_hostname: str = "",
) -> dict[str, Any]:
    """Parse mapped command output through the selected profile."""
    return parse_read_facts(outputs, profile, gather_subset, inventory_hostname)


def switch_raw_export_plan(
    command_plan: list[dict[str, Any]],
    outputs: dict[str, str],
    profile: str = "sks8300",
) -> list[dict[str, Any]]:
    """Build raw export items from command-level policy."""
    return build_raw_export_plan(command_plan, outputs, profile)


class FilterModule:
    """Ansible filter entrypoint."""

    def filters(self) -> dict[str, Any]:
        return {
            "switch_read_command_plan": switch_read_command_plan,
            "switch_cli_output_map": switch_cli_output_map,
            "switch_parse_facts": switch_parse_facts,
            "switch_raw_export_plan": switch_raw_export_plan,
        }
