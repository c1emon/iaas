"""Compatibility filters for parsing SKS8300 switch CLI output."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ANSIBLE_DIR = Path(__file__).resolve().parents[1]
if str(ANSIBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ANSIBLE_DIR))

try:
    from ansible.module_utils.switch_profiles.common import command_key, normalize_cli_result
    from ansible.module_utils.switch_profiles.sks8300.parsers import (
        parse_switch_interfaces,
        parse_switch_show_version,
        parse_switch_vlans,
        switch_cli_facts,
    )
    from ansible.module_utils.switch_profiles.sks8300.redaction import redact_switch_running_config
except ModuleNotFoundError:
    from module_utils.switch_profiles.common import command_key, normalize_cli_result
    from module_utils.switch_profiles.sks8300.parsers import (
        parse_switch_interfaces,
        parse_switch_show_version,
        parse_switch_vlans,
        switch_cli_facts,
    )
    from module_utils.switch_profiles.sks8300.redaction import redact_switch_running_config


def normalize_switch_cli_outputs(commands: list[str], outputs: Any) -> dict[str, str]:
    """Map network CLI command output to legacy command keys."""
    if outputs is None:
        text_outputs = []
    elif isinstance(outputs, str):
        text_outputs = [outputs]
    else:
        text_outputs = [normalize_cli_result(output) for output in outputs]

    show_commands = [command for command in commands if command.lower().startswith("show ")]
    result = {command_key(command): "" for command in show_commands}

    if len(text_outputs) == len(commands):
        for command, output in zip(commands, text_outputs, strict=False):
            if command.lower().startswith("show "):
                result[command_key(command)] = output
        return result

    if len(text_outputs) == len(show_commands):
        for command, output in zip(show_commands, text_outputs, strict=False):
            result[command_key(command)] = output
        return result

    transcript = "\n".join(text_outputs)
    if transcript:
        lower_transcript = transcript.lower()
        for index, command in enumerate(show_commands):
            start = lower_transcript.find(command.lower())
            if start == -1:
                continue
            following_starts = [
                position
                for next_command in show_commands[index + 1 :]
                if (position := lower_transcript.find(next_command.lower(), start + len(command))) != -1
            ]
            end = min(following_starts) if following_starts else len(transcript)
            result[command_key(command)] = transcript[start:end].strip()

    return result


class FilterModule:
    """Ansible filter entrypoint."""

    def filters(self) -> dict[str, Any]:
        return {
            "normalize_switch_cli_outputs": normalize_switch_cli_outputs,
            "redact_switch_running_config": redact_switch_running_config,
            "parse_switch_show_version": parse_switch_show_version,
            "parse_switch_vlans": parse_switch_vlans,
            "parse_switch_interfaces": parse_switch_interfaces,
            "switch_cli_facts": switch_cli_facts,
        }
