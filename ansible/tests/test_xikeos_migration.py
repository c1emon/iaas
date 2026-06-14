"""Smoke checks for native XikeOS switch automation migration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANSIBLE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANSIBLE_DIR))


class XikeOSMigrationSmokeTest(unittest.TestCase):
    def test_dependency_metadata_includes_native_collection(self) -> None:
        requirements = (ANSIBLE_DIR / "requirements.yml").read_text()
        self.assertIn("name: c1emon.xikeos", requirements)
        self.assertIn('version: ">=0.2.0,<0.3.0"', requirements)

    def test_switch_inventory_uses_native_network_os(self) -> None:
        group_vars = (ANSIBLE_DIR / "inventories/group_vars/switches.yml").read_text()
        self.assertIn("ansible_connection: ansible.netcommon.network_cli", group_vars)
        self.assertIn("ansible_network_os: c1emon.xikeos.xikeos", group_vars)
        self.assertNotIn("ansible_network_os: cisco.ios.ios", group_vars)

    def test_readonly_workflow_uses_xikeos_facts(self) -> None:
        collect = (ANSIBLE_DIR / "roles/switch_readonly_facts/tasks/collect.yml").read_text()
        export = (ANSIBLE_DIR / "playbooks/switches/tasks/export-readonly-facts.yml").read_text()
        self.assertIn("c1emon.xikeos.xikeos_facts", collect)
        self.assertNotIn("ansible.netcommon.cli_command", collect)
        self.assertNotIn("c1emon.xikeos.xikeos_command", collect)
        self.assertIn("switch_native_facts", export)
        self.assertNotIn("{{ switch_facts", export)

    def test_switch_config_defaults_use_native_resource_inputs(self) -> None:
        defaults = (ANSIBLE_DIR / "roles/switch_config/defaults/main.yml").read_text()
        self.assertIn("switch_config_allowed_states", defaults)
        self.assertIn("switch_config_resources", defaults)
        self.assertNotIn("switch_config_intent", defaults)
        self.assertNotIn("switch_config_allowed_operations", defaults)

    def test_switch_config_validate_contract_rejects_legacy_inputs(self) -> None:
        validate = (ANSIBLE_DIR / "roles/switch_config/tasks/validate.yml").read_text()
        self.assertIn("switch_config_intent is not defined", validate)
        self.assertIn("switch_config_commands is not defined", validate)
        self.assertIn("switch_config_resources.keys() | difference(switch_config_supported_resources)", validate)
        self.assertIn("item.state is defined", validate)
        self.assertIn("item.config is defined", validate)
        self.assertIn("item.state in switch_config_allowed_states", validate)

    def test_switch_config_main_only_imports_new_task_phases(self) -> None:
        main = (ANSIBLE_DIR / "roles/switch_config/tasks/main.yml").read_text()
        self.assertNotIn("collect_current.yml", main)
        self.assertNotIn("plan.yml", main)
        self.assertNotIn("verify.yml", main)

    def test_switch_config_diff_and_apply_use_deterministic_module_order(self) -> None:
        expected_modules = [
            "c1emon.xikeos.xikeos_vlans",
            "c1emon.xikeos.xikeos_interfaces",
            "c1emon.xikeos.xikeos_lag_interfaces",
            "c1emon.xikeos.xikeos_l2_interfaces",
            "c1emon.xikeos.xikeos_l3_interfaces",
            "c1emon.xikeos.xikeos_static_routes",
            "c1emon.xikeos.xikeos_acls",
        ]
        for filename in ("roles/switch_config/tasks/diff.yml", "roles/switch_config/tasks/apply.yml"):
            content = (ANSIBLE_DIR / filename).read_text()
            positions = [content.index(module) for module in expected_modules]
            self.assertEqual(positions, sorted(positions), filename)

    def test_switch_config_config_vars_example_uses_resource_schema(self) -> None:
        readme = (ANSIBLE_DIR / "roles/switch_config/README.md").read_text()
        example = readme.split("## Resource input contract", 1)[1].split("Supported resource groups", 1)[0]
        self.assertIn("switch_config_resources:", readme)
        self.assertIn("state: merged", example)
        self.assertIn("config:", example)
        self.assertNotIn("switch_config_intent", example)


if __name__ == "__main__":
    unittest.main()
