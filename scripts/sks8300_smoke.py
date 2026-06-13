#!/usr/bin/env python3
"""Matrix smoke check for SKS8300 declarative resource behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ansible.module_utils.switch_profiles.sks8300 import resources


VLAN_10 = 10
VLAN_20 = 20
VLAN_30 = 30
VLAN_50 = 50
PORT_1 = "Ethernet1/0/1"
PORT_7 = "Ethernet1/0/7"


def _iface(
    name: str,
    mode: str,
    *,
    access_vlan: int | None = None,
    tagged_vlans: list[int] | None = None,
    untagged_vlans: list[int] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "mode": mode}
    if access_vlan is not None:
        entry["access_vlan"] = access_vlan
    if tagged_vlans is not None:
        entry["tagged_vlans"] = tagged_vlans
    if untagged_vlans is not None:
        entry["untagged_vlans"] = untagged_vlans
    return entry


def _current_facts(entries: list[dict[str, Any]]) -> dict[str, Any]:
    current: list[dict[str, Any]] = []
    for entry in entries:
        current.append(
            {
                "name": entry["name"],
                "mode": entry["mode"],
                "access_vlan": entry.get("access_vlan", 1),
                "tagged_vlans": list(entry.get("tagged_vlans", [])),
                "untagged_vlans": list(entry.get("untagged_vlans", [])),
            }
        )
    return {"interfaces": current}


def _base_current_facts() -> dict[str, Any]:
    return {
        "interfaces": [
            {"name": PORT_1, "mode": "access", "access_vlan": 1, "tagged_vlans": [], "untagged_vlans": []},
            {"name": PORT_7, "mode": "access", "access_vlan": 1, "tagged_vlans": [], "untagged_vlans": []},
        ]
    }


def _trunk_current_facts() -> dict[str, Any]:
    return {
        "interfaces": [
            {"name": PORT_1, "mode": "trunk", "access_vlan": None, "tagged_vlans": [VLAN_10], "untagged_vlans": []},
        ]
    }


def _single_current_facts(mode: str) -> dict[str, Any]:
    current = _iface(PORT_1, mode)
    if mode == "access":
        current["access_vlan"] = VLAN_10
    elif mode == "trunk":
        current["tagged_vlans"] = [VLAN_10]
    elif mode == "hybrid":
        current["tagged_vlans"] = [VLAN_10]
        current["untagged_vlans"] = [VLAN_50]
    return _current_facts([current])


def _desired_for_mode(mode: str) -> dict[str, Any]:
    if mode == "access":
        return _iface(PORT_1, mode, access_vlan=VLAN_20)
    if mode == "trunk":
        return _iface(PORT_1, mode, tagged_vlans=[VLAN_20, VLAN_50])
    if mode == "hybrid":
        return _iface(PORT_1, mode, tagged_vlans=[VLAN_20], untagged_vlans=[VLAN_50])
    raise AssertionError(f"unsupported mode: {mode}")


def _render_expected(entries: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    for entry in entries:
        commands.append(f"interface {entry['name']}")
        mode = entry["mode"]
        if mode == "access":
            commands.append(f"switchport access vlan {entry['access_vlan']}")
        elif mode == "trunk":
            commands.extend(
                [
                    "switchport mode trunk",
                    f"switchport trunk allowed vlan {';'.join(str(vlan) for vlan in entry['tagged_vlans'])}",
                ]
            )
        elif mode == "hybrid":
            commands.extend(
                [
                    "switchport mode hybrid",
                    f"switchport hybrid allowed vlan {';'.join(str(vlan) for vlan in entry['tagged_vlans'])} tag",
                    f"switchport hybrid allowed vlan {';'.join(str(vlan) for vlan in entry['untagged_vlans'])} untag",
                ]
            )
        else:
            raise AssertionError(f"unsupported mode: {mode}")
        commands.append("exit")
    return commands


def main() -> None:
    cases = [
        (
            "access single-port",
            [_iface(PORT_1, "access", access_vlan=VLAN_10)],
            [_iface(PORT_1, "access", access_vlan=VLAN_30)],
        ),
        (
            "access two-port",
            [
                _iface(PORT_1, "access", access_vlan=VLAN_10),
                _iface(PORT_7, "access", access_vlan=VLAN_20),
            ],
            [
                _iface(PORT_1, "access", access_vlan=VLAN_30),
                _iface(PORT_7, "access", access_vlan=VLAN_20),
            ],
        ),
        (
            "trunk single-port",
            [_iface(PORT_1, "trunk", tagged_vlans=[VLAN_10])],
            [_iface(PORT_1, "trunk", tagged_vlans=[VLAN_30])],
        ),
        (
            "trunk two-port",
            [
                _iface(PORT_1, "trunk", tagged_vlans=[VLAN_10, VLAN_20]),
                _iface(PORT_7, "trunk", tagged_vlans=[VLAN_20, VLAN_30]),
            ],
            [
                _iface(PORT_1, "trunk", tagged_vlans=[VLAN_30]),
                _iface(PORT_7, "trunk", tagged_vlans=[VLAN_20, VLAN_30]),
            ],
        ),
        (
            "hybrid single-port",
            [
                _iface(
                    PORT_1,
                    "hybrid",
                    tagged_vlans=[VLAN_20],
                    untagged_vlans=[VLAN_10],
                )
            ],
            [
                _iface(
                    PORT_1,
                    "hybrid",
                    tagged_vlans=[VLAN_20],
                    untagged_vlans=[VLAN_30],
                )
            ],
        ),
        (
            "hybrid two-port",
            [
                _iface(
                    PORT_1,
                    "hybrid",
                    tagged_vlans=[VLAN_10, VLAN_20],
                    untagged_vlans=[VLAN_30],
                ),
                _iface(
                    PORT_7,
                    "hybrid",
                    tagged_vlans=[VLAN_20, VLAN_30],
                    untagged_vlans=[VLAN_10],
                ),
            ],
            [
                _iface(
                    PORT_1,
                    "hybrid",
                    tagged_vlans=[VLAN_10, VLAN_20],
                    untagged_vlans=[VLAN_10],
                ),
                _iface(
                    PORT_7,
                    "hybrid",
                    tagged_vlans=[VLAN_20, VLAN_30],
                    untagged_vlans=[VLAN_10],
                ),
            ],
        ),
    ]

    for label, intent_entries, bad_entries in cases:
        intent = {"interfaces": intent_entries}
        plan = resources.build_plan(_base_current_facts(), intent)
        assert plan["changed"] is True, label
        assert plan["verify"]["status"] == "not_run", label
        assert plan["rendered_commands"] == _render_expected(intent_entries), label

        verified = resources.verify_intent(_current_facts(intent_entries), intent)
        assert verified == {"ok": True, "status": "passed", "failures": []}, label

        negative = resources.verify_intent(_current_facts(bad_entries), intent)
        assert negative["ok"] is False, label
        assert negative["status"] == "failed", label
        assert negative["failures"], label

    trunk_to_hybrid = {"interfaces": [_iface(PORT_1, "hybrid", tagged_vlans=[VLAN_10], untagged_vlans=[VLAN_50])]}
    plan = resources.build_plan(_trunk_current_facts(), trunk_to_hybrid)
    assert plan["rendered_commands"] == [
        f"interface {PORT_1}",
        "switchport mode access",
        "switchport mode hybrid",
        f"switchport hybrid allowed vlan {VLAN_10} tag",
        f"switchport hybrid allowed vlan {VLAN_50} untag",
        "exit",
    ]

    expected_transitions = {
        ("access", "trunk"): ["switchport mode trunk"],
        ("access", "hybrid"): ["switchport mode hybrid"],
        ("trunk", "access"): ["switchport mode access"],
        ("trunk", "hybrid"): ["switchport mode access", "switchport mode hybrid"],
        ("hybrid", "access"): ["switchport mode access"],
        ("hybrid", "trunk"): ["switchport mode trunk"],
    }
    for from_mode in ("access", "trunk", "hybrid"):
        for to_mode in ("access", "trunk", "hybrid"):
            if from_mode == to_mode:
                continue
            plan = resources.build_plan(_single_current_facts(from_mode), {"interfaces": [_desired_for_mode(to_mode)]})
            commands = plan["rendered_commands"]
            assert commands[0] == f"interface {PORT_1}", (from_mode, to_mode, commands)
            transition = expected_transitions[(from_mode, to_mode)]
            assert commands[1 : 1 + len(transition)] == transition, (from_mode, to_mode, commands)

    print("SKS8300 smoke check passed")


if __name__ == "__main__":
    main()
