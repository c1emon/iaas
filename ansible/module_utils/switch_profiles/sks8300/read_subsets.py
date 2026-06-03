"""SKS8300 read-only gather subset registry."""

from __future__ import annotations

from dataclasses import dataclass



@dataclass(frozen=True)
class ReadSubset:
    """One read-only gather subset."""

    name: str
    command_ids: tuple[str, ...]
    fact_keys: tuple[str, ...]


DEFAULT_SETUP_COMMANDS = ("disable_pagination",)

READ_SUBSETS: dict[str, ReadSubset] = {
    "default": ReadSubset("default", (), ()),
    "device": ReadSubset("device", ("show_version",), ("device",)),
    "vlans": ReadSubset(
        "vlans",
        ("show_running_config", "show_vlan", "show_vlan_brief"),
        ("vlans",),
    ),
    "interfaces": ReadSubset("interfaces", ("show_running_config",), ("interfaces",)),
}
