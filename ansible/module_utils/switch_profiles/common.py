"""Common helpers shared by switch profiles."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

MUTATING_COMMAND_RE = re.compile(
    r"^\s*(?:config|configure|write|copy|reload|delete|clear|format)\b",
    re.IGNORECASE,
)


def command_key(command: str) -> str:
    """Return the legacy normalized key for a CLI command."""
    return command.strip().replace(" ", "_").replace("-", "_")


def coerce_string_list(value: Any) -> list[str]:
    """Coerce Ansible scalar/list values to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def normalize_cli_result(output: Any) -> str:
    """Normalize one network_cli result item to stdout text."""
    if output is None:
        return ""
    if isinstance(output, dict):
        stdout = output.get("stdout", output.get("output", ""))
        if isinstance(stdout, list):
            return "\n".join(str(line) for line in stdout)
        return str(stdout)
    return str(output)


def is_mutating_command(command: str) -> bool:
    """Return whether a CLI command matches known mutating prefixes."""
    return bool(MUTATING_COMMAND_RE.search(command or ""))
