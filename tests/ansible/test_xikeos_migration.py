"""Smoke checks for native XikeOS switch automation migration."""

from pathlib import Path
import os
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
ENV_ANSIBLE_DIR = ROOT / "tests" / "fixtures" / "environment" / "ansible"
OPERATIONS_DIR = ROOT / "docs" / "operations"


def test_dependency_metadata_includes_native_collection() -> None:
    requirements = (ANSIBLE_DIR / "requirements.yml").read_text()
    assert "name: c1emon.xikeos" in requirements
    assert 'version: ">=0.2.1,<0.3.0"' in requirements


def test_switch_inventory_uses_native_network_os() -> None:
    group_vars = (ENV_ANSIBLE_DIR / "group_vars/switches.yml").read_text()
    assert "ansible_connection: ansible.netcommon.network_cli" in group_vars
    assert "ansible_network_os: c1emon.xikeos.xikeos" in group_vars
    assert "ansible_network_os: cisco.ios.ios" not in group_vars


def test_readonly_workflow_uses_xikeos_facts() -> None:
    playbook = (ANSIBLE_DIR / "playbooks/switches/readonly-facts.yml").read_text()
    export = (ANSIBLE_DIR / "playbooks/switches/tasks/export-readonly-facts.yml").read_text()
    assert "c1emon.xikeos.xikeos_facts" in playbook
    assert "switch_readonly_facts" not in playbook
    assert "switch_native_facts" in export
    assert "switch_xikeos_facts_module" in export
    assert "{{ switch_facts" not in export


def test_switch_readonly_facts_role_directory_is_removed() -> None:
    assert not (ANSIBLE_DIR / "roles/switch_readonly_facts").exists()
    assert not (ANSIBLE_DIR / "roles/switch_readonly_facts/README.md").exists()


def test_switch_config_defaults_use_native_resource_inputs() -> None:
    defaults = (ANSIBLE_DIR / "roles/switch_config/defaults/main.yml").read_text()
    assert "switch_config_allowed_states" in defaults
    assert "switch_config_resources" in defaults
    assert "switch_config_intent" not in defaults
    assert "switch_config_allowed_operations" not in defaults


def test_switch_config_validate_contract_rejects_legacy_inputs() -> None:
    validate = (ANSIBLE_DIR / "roles/switch_config/tasks/validate.yml").read_text()
    assert "switch_config_intent is not defined" in validate
    assert "switch_config_commands is not defined" in validate
    assert "switch_config_resources.keys() | difference(switch_config_supported_resources)" in validate
    assert "item.state is defined" in validate
    assert "item.config is defined" in validate
    assert "item.state in switch_config_allowed_states" in validate


def test_switch_config_main_only_imports_new_task_phases() -> None:
    main = (ANSIBLE_DIR / "roles/switch_config/tasks/main.yml").read_text()
    assert "safety policy validation" in main
    assert "collection preview orchestration" in main
    assert "apply gate and orchestration" in main
    assert "safety report export" in main


def test_operator_manual_describes_switch_config_safety_boundary() -> None:
    manual = (OPERATIONS_DIR / "01-switch.md").read_text()
    assert "switch_config_resources" in manual
    assert "switch_config_apply" in manual
    assert "switch_readonly_facts" not in manual


def test_switch_config_diff_and_apply_use_deterministic_module_order() -> None:
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
        assert positions == sorted(positions), filename


def test_operator_manual_switch_example_uses_resource_schema() -> None:
    manual = (OPERATIONS_DIR / "01-switch.md").read_text()
    example = manual.split("### `switch_config_resources` 结构", 1)[1].split("仓库拒绝", 1)[0]
    assert "switch_config_resources:" in manual
    assert "state: merged" in example
    assert "config:" in example
    assert "switch_config_intent" not in example


def test_switch_config_plan_resolves_relocated_vlan_source_with_jinja(tmp_path: Path) -> None:
    playbook = yaml.safe_load(
        (ANSIBLE_DIR / "playbooks/switches/config-plan.yml").read_text(encoding="utf-8")
    )
    probe = [
        {
            "hosts": "sw-core",
            "gather_facts": False,
            "connection": "local",
            "vars": {"switch_vlan_source": playbook[0]["vars"]["switch_vlan_source"]},
            "tasks": [
                {
                    "ansible.builtin.include_vars": {"file": "{{ switch_vlan_source }}"},
                },
                {
                    "ansible.builtin.assert": {
                        "that": [
                            "switch_config_resources is mapping",
                            "switch_config_resources.vlans is sequence",
                        ]
                    }
                },
            ],
        }
    ]
    result = subprocess.run(
        [
            "uv",
            "run",
            "ansible-playbook",
            "-i",
            str(ENV_ANSIBLE_DIR / "inventory.yml"),
            "/dev/stdin",
        ],
        cwd=ROOT,
        input=yaml.safe_dump(probe, sort_keys=False),
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "ANSIBLE_CONFIG": str(ANSIBLE_DIR / "ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
