"""SKS8300 CLI output parsers."""

from __future__ import annotations

import re
from typing import Any

MAC_RE = re.compile(r"\b[0-9a-f]{2}(?:[:-][0-9a-f]{2}){5}\b", re.IGNORECASE)


def _first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def _normalize_mac(value: str) -> str:
    return value.replace("-", ":").upper()


def _parse_vlan_ids(value: str) -> list[int]:
    vlan_ids: set[int] = set()
    for token in re.split(r"[;,\s]+", value.strip()):
        if not token:
            continue
        if "-" in token:
            start, end = token.split("-", 1)
            if start.isdigit() and end.isdigit():
                vlan_ids.update(range(int(start), int(end) + 1))
            continue
        if token.isdigit():
            vlan_ids.add(int(token))
    return sorted(vlan_ids)


def parse_switch_show_version(output: str) -> dict[str, Any]:
    """Parse SKS8300-like show version output into device facts."""
    mac_addresses = [_normalize_mac(value) for value in MAC_RE.findall(output)]
    return {
        "model": _first_match(
            output,
            [
                r"\b(?:model|device\s+model|product\s+model|product\s+name)\s*[:=]\s*([^\r\n]+)",
                r"\b(SKS\d+[-\w]*)\b",
            ],
        ),
        "software_version": _first_match(
            output,
            [
                r"\b(?:software\s+version|system\s+software\s+version|version)\s*[:=]\s*([^\r\n]+)",
                r"\b(V\d+SP\d+)\b",
            ],
        ),
        "bootrom_version": _first_match(
            output,
            [
                r"\b(?:boot\s*rom|bootrom)(?:\s+version)?\s*[:=]\s*([^\r\n]+)",
                r"\b(BootRom\s+Version\s+[^\r\n]+)",
            ],
        ),
        "serial_number": _first_match(
            output,
            [r"\b(?:serial\s*(?:number|num|no\.?|#)|sn)\s*[:=]\s*([^\r\n]+)"],
        ),
        "cpu_mac": _normalize_mac(_first_match(output, [r"\bcpu\s+mac(?:\s+address)?\s*[:=]?\s*([0-9a-f:-]{17})"])),
        "vlan_mac": _normalize_mac(_first_match(output, [r"\bvlan\s+mac(?:\s+address)?\s*[:=]?\s*([0-9a-f:-]{17})"])),
        "uptime": _first_match(output, [r"\buptime(?:\s+is)?\s*[:=]?\s*([^\r\n]+)"]),
        "mac_addresses": sorted(set(mac_addresses)),
    }


def parse_switch_vlans(config: str, show_vlan_brief: str = "", show_vlan: str = "") -> list[dict[str, Any]]:
    """Parse VLAN ID/name facts from running-config and show vlan tables."""
    vlans: dict[int, dict[str, Any]] = {}
    current_vlan: int | None = None

    for line in config.splitlines():
        vlan_match = re.match(r"^\s*vlan\s+(\d+)\s*$", line, re.IGNORECASE)
        if vlan_match:
            current_vlan = int(vlan_match.group(1))
            vlans.setdefault(current_vlan, {"id": current_vlan, "name": ""})
            continue
        name_match = re.match(r"^\s*name\s+(.+?)\s*$", line, re.IGNORECASE)
        if current_vlan is not None and name_match:
            vlans.setdefault(current_vlan, {"id": current_vlan, "name": ""})["name"] = name_match.group(1).strip()
            continue
        if line.strip() in {"!", "exit"} or re.match(r"^\S", line):
            current_vlan = None

    for line in show_vlan.splitlines():
        table_match = re.match(r"^\s*(\d{1,4})\s+(\S+)\s+(?:Static|Dynamic)\b", line, re.IGNORECASE)
        if not table_match:
            continue
        vlan_id = int(table_match.group(1))
        name = table_match.group(2).strip()
        if name.lower() in {"name", "vlan", "----"}:
            continue
        entry = vlans.setdefault(vlan_id, {"id": vlan_id, "name": ""})
        if not entry["name"]:
            entry["name"] = name

    existing_vlan_section = False
    for line in show_vlan_brief.splitlines():
        if re.search(r"Existing\s+Vlan", line, re.IGNORECASE):
            existing_vlan_section = True
            continue
        if existing_vlan_section:
            for vlan_id in _parse_vlan_ids(line):
                vlans.setdefault(vlan_id, {"id": vlan_id, "name": ""})
            existing_vlan_section = False

    return [vlans[vlan_id] for vlan_id in sorted(vlans)]


def parse_switch_interfaces(config: str) -> list[dict[str, Any]]:
    """Parse interface switchport mode and VLAN membership from running-config."""
    interfaces: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def finish_current() -> None:
        if current is None:
            return
        allowed = set(current["tagged_vlans"]) | set(current["untagged_vlans"])
        if current["access_vlan"] is not None:
            allowed.add(current["access_vlan"])
        current["allowed_vlans"] = sorted(allowed)
        interfaces.append(current.copy())

    for line in config.splitlines():
        interface_match = re.match(r"^\s*interface\s+(.+?)\s*$", line, re.IGNORECASE)
        if interface_match:
            finish_current()
            name = interface_match.group(1).strip()
            current = {
                "name": name,
                "mode": "svi" if name.lower().startswith("vlan") else "unknown",
                "access_vlan": None,
                "tagged_vlans": [],
                "untagged_vlans": [],
                "allowed_vlans": [],
            }
            continue

        if current is None:
            continue

        stripped = line.strip()
        if stripped == "!":
            finish_current()
            current = None
            continue

        mode_match = re.match(r"switchport\s+mode\s+(access|trunk|hybrid)\b", stripped, re.IGNORECASE)
        if mode_match:
            current["mode"] = mode_match.group(1).lower()
            continue

        access_match = re.match(r"switchport\s+access\s+vlan\s+(.+)$", stripped, re.IGNORECASE)
        if access_match:
            vlan_ids = _parse_vlan_ids(access_match.group(1))
            if vlan_ids:
                current["access_vlan"] = vlan_ids[0]
                current["untagged_vlans"] = sorted(set(current["untagged_vlans"]) | {vlan_ids[0]})
                if current["mode"] == "unknown":
                    current["mode"] = "access"
            continue

        trunk_match = re.match(r"switchport\s+trunk\s+allowed\s+vlan\s+(.+)$", stripped, re.IGNORECASE)
        if trunk_match:
            vlan_ids = _parse_vlan_ids(trunk_match.group(1))
            current["tagged_vlans"] = sorted(set(current["tagged_vlans"]) | set(vlan_ids))
            if current["mode"] == "unknown":
                current["mode"] = "trunk"
            continue

        hybrid_match = re.match(
            r"switchport\s+hybrid\s+allowed\s+vlan\s+(.+?)(?:\s+(tag|untag))?$", stripped, re.IGNORECASE
        )
        if hybrid_match:
            vlan_ids = _parse_vlan_ids(hybrid_match.group(1))
            tag_mode = (hybrid_match.group(2) or "untag").lower()
            key = "tagged_vlans" if tag_mode == "tag" else "untagged_vlans"
            current[key] = sorted(set(current[key]) | set(vlan_ids))
            if current["mode"] == "unknown":
                current["mode"] = "hybrid"
            continue

    finish_current()
    return interfaces


def switch_cli_facts(outputs: dict[str, str], inventory_hostname: str = "") -> dict[str, Any]:
    """Build combined structured switch facts from collected CLI output."""
    running_config = outputs.get("running_config", outputs.get("show_running_config", ""))
    return {
        "inventory_hostname": inventory_hostname,
        "device": parse_switch_show_version(outputs.get("show_version", "")),
        "vlans": parse_switch_vlans(
            running_config,
            outputs.get("show_vlan_brief", ""),
            outputs.get("show_vlan", ""),
        ),
        "interfaces": parse_switch_interfaces(running_config),
    }
