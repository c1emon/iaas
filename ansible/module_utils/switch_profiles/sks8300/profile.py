"""SKS8300 read-only profile implementation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..common import coerce_string_list, is_mutating_command
from ..errors import UnsupportedGatherSubsetError, UnsafeCommandError
from .commands import COMMANDS, CommandDefinition
from .parsers import parse_switch_interfaces, parse_switch_show_version, parse_switch_vlans
from .read_subsets import DEFAULT_SETUP_COMMANDS, READ_SUBSETS
from .redaction import redact_switch_running_config


@dataclass(frozen=True)
class SKS8300Profile:
    """SKS8300-series profile."""

    name: str = "sks8300"

    def normalize_gather_subset(self, gather_subset: Any) -> list[str]:
        """Validate and normalize gather subsets, always including default."""
        requested = coerce_string_list(gather_subset) or ["device", "vlans", "interfaces"]
        normalized = [item.strip().lower() for item in requested if item.strip()]
        if "all" in normalized:
            normalized = [name for name in READ_SUBSETS if name != "default"]
        ordered = ["default"]
        for subset in normalized:
            if subset == "default":
                continue
            if subset not in READ_SUBSETS:
                supported = ", ".join(sorted(READ_SUBSETS))
                raise UnsupportedGatherSubsetError(
                    f"Unsupported switch_readonly_gather_subset '{subset}'. Supported subsets: {supported}"
                )
            if subset not in ordered:
                ordered.append(subset)
        return ordered

    def _validate_command(self, definition: CommandDefinition) -> None:
        if not definition.read_only or is_mutating_command(definition.command):
            raise UnsafeCommandError(
                f"Refusing non-read-only command definition '{definition.id}': {definition.command}"
            )

    def build_read_command_plan(self, gather_subset: Any) -> list[dict[str, Any]]:
        """Build a deduplicated read-only command plan."""
        command_ids: list[str] = list(DEFAULT_SETUP_COMMANDS)
        for subset in self.normalize_gather_subset(gather_subset):
            command_ids.extend(READ_SUBSETS[subset].command_ids)

        plan: list[dict[str, Any]] = []
        seen: set[str] = set()
        for command_id in command_ids:
            if command_id in seen:
                continue
            definition = COMMANDS[command_id]
            self._validate_command(definition)
            plan.append(definition.as_plan_item())
            seen.add(command_id)
        return plan

    def parse_read_facts(
        self,
        outputs: Mapping[str, str],
        gather_subset: Any,
        inventory_hostname: str = "",
    ) -> dict[str, Any]:
        """Parse selected gather subsets into the existing structured schema."""
        subsets = self.normalize_gather_subset(gather_subset)
        running_config = outputs.get("show_running_config", outputs.get("running_config", ""))
        facts: dict[str, Any] = {"inventory_hostname": inventory_hostname}
        if "device" in subsets:
            facts["device"] = parse_switch_show_version(outputs.get("show_version", ""))
        if "vlans" in subsets:
            facts["vlans"] = parse_switch_vlans(
                running_config,
                outputs.get("show_vlan_brief", ""),
                outputs.get("show_vlan", ""),
            )
        if "interfaces" in subsets:
            facts["interfaces"] = parse_switch_interfaces(running_config)
        return facts

    def build_raw_export_plan(
        self,
        command_plan: Sequence[Mapping[str, Any]],
        outputs: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        """Build raw export items using command-level policy."""
        export_items: list[dict[str, Any]] = []
        for command in command_plan:
            command_id = str(command.get("id", ""))
            policy = str(command.get("raw_export", "never"))
            if not command_id or policy == "never":
                continue
            content = outputs.get(command_id, "")
            if policy == "redacted_only":
                content = redact_switch_running_config(content)
            export_items.append(
                {
                    "id": command_id,
                    "filename": command.get("filename") or f"{command_id.replace('_', '-')}.txt",
                    "sensitive": bool(command.get("sensitive", False)),
                    "raw_export": policy,
                    "content": content,
                }
            )
        return export_items


PROFILE = SKS8300Profile()
