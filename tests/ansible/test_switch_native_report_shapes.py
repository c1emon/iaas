"""Report the pinned Collection's real check-mode result shapes without a device."""

import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "automation/ansible"
sys.path.insert(0, str(ANSIBLE / "collections"))
from ansible_collections.c1emon.xikeos.plugins.module_utils.network.xikeos.lifecycle import run_resource_module_lifecycle

spec = importlib.util.spec_from_file_location("native_operation_reports", ANSIBLE / "filter_plugins/operation_reports.py")
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)


class Result(Exception):
    def __init__(self, payload):
        self.payload = payload


class PreviewModule:
    check_mode = True

    def exit_json(self, **payload):
        raise Result(payload)

    def fail_json(self, **payload):
        pytest.fail(str(payload))


def native_preview(kind, desired):
    module_name = "interfaces" if kind == "base_interfaces" else kind
    module = importlib.import_module(f"ansible_collections.c1emon.xikeos.plugins.modules.xikeos_{module_name}")
    planner = module.build_commands if kind == "base_interfaces" else module.build_lifecycle_commands
    with pytest.raises(Result) as result:
        run_resource_module_lifecycle(
            module=PreviewModule(), config=desired, state="merged", gather=lambda _: {},
            build_commands=planner, build_after=module.build_after_state,
            apply_config=lambda *_: pytest.fail("preview must not mutate a switch"),
        )
    payload = result.value.payload
    assert isinstance(payload["before"], dict) and isinstance(payload["after"], dict)
    return payload


def test_native_interface_shapes_reach_the_real_report_task(tmp_path):
    requests = {
        "base_interfaces": [{"name": "GigabitEthernet1/0/1", "description": "private-description"}],
        "lag_interfaces": [{"name": "port-channel 1", "mode": "static", "members": ["GigabitEthernet1/0/2"]}],
        "l2_interfaces": [{"name": "GigabitEthernet1/0/3", "mode": "access", "access_vlan": 20}],
        "l3_interfaces": [{"name": "20", "ipv4": [{"address": "192.0.2.8", "subnet_mask": "255.255.255.0"}]}],
    }
    previews = {kind: {"results": [native_preview(kind, desired)]} for kind, desired in requests.items()}
    summary = reports.switch_plan_summary(previews)
    assert summary["changed_objects"] == 4
    assert {item["object"] for item in summary["changes"]} == {
        "GigabitEthernet1/0/1", "port-channel 1", "GigabitEthernet1/0/3", "vlan-interface 20",
    }
    assert all(item["change"] == "added" for item in summary["changes"])
    assert "private-description" not in json.dumps(summary)
    assert "192.0.2.8" not in json.dumps(summary)
    for registered in previews.values():
        registered["results"].append({"before": registered["results"][0]["after"],
                                      "after": registered["results"][0]["after"]})
    assert reports.switch_plan_summary(previews)["changed_objects"] == 4
    task = next(task for task in yaml.safe_load((ANSIBLE / "roles/switch_config/tasks/diff.yml").read_text())
                if task["name"] == "Report sanitized object changes")
    result = subprocess.run(
        ["uv", "run", "ansible-playbook", "-i", "sw-a,", "/dev/stdin"],
        input=yaml.safe_dump([{"hosts": "all", "gather_facts": False, "connection": "local",
                              "vars": {"switch_config_collection_preview": previews}, "tasks": [task]}]),
        cwd=ROOT, env=os.environ | {"ANSIBLE_CONFIG": str(ANSIBLE / "ansible.cfg")},
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed_objects: 4" in result.stdout
    assert "private-description" not in result.stdout and "192.0.2.8" not in result.stdout


def test_mapping_identity_conflicts_are_rejected():
    with pytest.raises(ValueError, match="ambiguous object identity"):
        reports.switch_plan_summary({"base_interfaces": {"results": [{
            "before": {}, "after": {"port-a": {"name": "port-b"}},
        }]}})
