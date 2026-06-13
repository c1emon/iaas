"""Smoke checks for native XikeOS switch automation migration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANSIBLE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANSIBLE_DIR))

from module_utils.switch_profiles.sks8300.resources import build_plan  # noqa: E402


class XikeOSMigrationSmokeTest(unittest.TestCase):
    def test_dependency_metadata_includes_native_collection(self) -> None:
        requirements = (ANSIBLE_DIR / "requirements.yml").read_text()
        self.assertIn("name: c1emon.xikeos", requirements)

    def test_switch_inventory_uses_native_network_os(self) -> None:
        group_vars = (ANSIBLE_DIR / "inventories/group_vars/switches.yml").read_text()
        self.assertIn("ansible_connection: ansible.netcommon.network_cli", group_vars)
        self.assertIn("ansible_network_os: c1emon.xikeos.xikeos", group_vars)
        self.assertNotIn("ansible_network_os: cisco.ios.ios", group_vars)

    def test_readonly_workflow_uses_xikeos_command(self) -> None:
        collect = (ANSIBLE_DIR / "roles/switch_readonly_facts/tasks/collect.yml").read_text()
        self.assertIn("c1emon.xikeos.xikeos_command", collect)
        self.assertNotIn("ansible.netcommon.cli_command", collect)

    def test_vlan_and_interface_plan_maps_to_collection_operations(self) -> None:
        current = {
            "vlans": [{"id": 10, "name": "OLD", "state": "present"}],
            "interfaces": [{"name": "Ethernet1/0/3", "mode": "access", "access_vlan": 1}],
        }
        intent = {
            "vlans": [
                {"id": 10, "name": "DATA", "state": "present"},
                {"id": 20, "name": "VOICE", "state": "present"},
            ],
            "interfaces": [
                {"name": "Ethernet1/0/3", "mode": "trunk", "tagged_vlans": [10, 20]},
            ],
        }
        plan = build_plan(current, intent, ["create", "update", "remove", "no-op"])

        self.assertTrue(plan["changed"])
        self.assertEqual(
            plan["collection"]["vlan_merge_config"],
            [
                {"vlan_id": 10, "name": "DATA", "state": "active"},
                {"vlan_id": 20, "name": "VOICE", "state": "active"},
            ],
        )
        self.assertEqual(
            plan["collection"]["l2_interface_merge_config"],
            [{"name": "Ethernet1/0/3", "mode": "trunk", "trunk_allowed_vlan": "10,20"}],
        )
        self.assertEqual(plan["collection"]["unsupported"], [])


if __name__ == "__main__":
    unittest.main()
