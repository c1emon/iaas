"""SKS8300 read-only command catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandDefinition:
    """One SKS8300 command definition."""

    id: str
    command: str
    read_only: bool = True
    sensitive: bool = False
    raw_export: str = "allowed"
    filename: str = ""
    structured_source: bool = True

    def as_plan_item(self) -> dict[str, object]:
        """Return an Ansible-friendly command plan item."""
        return {
            "id": self.id,
            "command": self.command,
            "read_only": self.read_only,
            "sensitive": self.sensitive,
            "raw_export": self.raw_export,
            "filename": self.filename,
            "structured_source": self.structured_source,
        }


COMMANDS: dict[str, CommandDefinition] = {
    "disable_pagination": CommandDefinition(
        id="disable_pagination",
        command="terminal length 0",
        raw_export="never",
        filename="disable-pagination.txt",
        structured_source=False,
    ),
    "show_version": CommandDefinition(
        id="show_version",
        command="show version",
        filename="show-version.txt",
    ),
    "show_vlan": CommandDefinition(
        id="show_vlan",
        command="show vlan",
        filename="show-vlan.txt",
    ),
    "show_vlan_brief": CommandDefinition(
        id="show_vlan_brief",
        command="show vlan brief",
        filename="show-vlan-brief.txt",
    ),
    "show_running_config": CommandDefinition(
        id="show_running_config",
        command="show running-config",
        sensitive=True,
        raw_export="redacted_only",
        filename="show-running-config.txt",
    ),
}
