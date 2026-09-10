"""Run the managed activation guards with inert command substitutes."""

from copy import deepcopy
import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "automation/ansible"


@pytest.mark.parametrize("destination,invert,valid", [
    (["opt8"], True, True), (["opt8"], False, False),
    (["opt9"], True, False), (["opt9"], False, True),
])
def test_direct_ansible_destination_inversion(tmp_path, destination, invert, valid):
    source = yaml.safe_load((ANSIBLE / "playbooks/opnsense/manage-filter-rules.yml").read_text())[0]
    check = next(task for task in source["tasks"] if task["name"].startswith("Assert deny rules"))
    play = tmp_path / "inversion.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"opnsense_filter_rules": [{"scope": "test", "slug": "deny", "interface": ["opt8"],
                  "action": "block", "destination_net": destination, "destination_invert": invert}]},
        "tasks": [check],
    }]))
    result = subprocess.run(["uv", "run", "ansible-playbook", "-i", "localhost,", str(play)],
                            cwd=ROOT, capture_output=True, text=True)
    assert (result.returncode == 0) == valid, result.stdout + result.stderr


@pytest.mark.parametrize("resource,key", [
    ("aliases", "alias"), ("gateways", "gateway"), ("vips", "vip"), ("filter-rules", "filter_rule"),
])
def test_managed_activation_recovery(tmp_path, resource, key):
    source = yaml.safe_load((ANSIBLE / f"playbooks/opnsense/manage-{resource}.yml").read_text())[0]
    guard = source["tasks"][0]
    activation = source["tasks"][-1]
    original_reload = activation["block"][0]
    assert "oxlorg.opnsense.reload" in original_reload
    mutation = next(task for task in source["tasks"] if task.get("register") == f"opnsense_{key}_apply")
    module = next(name for name in mutation if name.startswith("oxlorg.opnsense."))
    assert mutation[module]["reload"] is False
    for changed, force, check, reload_fails, crud_fails, expected in [
        (False, False, False, False, False, "no-op"),
        (True, False, False, True, False, "activation failed"),
        (False, True, False, False, False, "activation succeeded"),
        (True, True, True, False, False, "no-op"),
        (False, "true", False, False, False, "must be a YAML or JSON boolean"),
        (True, True, False, False, True, "partial batch"),
    ]:
        block = deepcopy(activation)
        block["block"][0] = {
            "name": original_reload["name"],
            "ansible.builtin.command": {"argv": ["/usr/bin/false" if reload_fails else "/usr/bin/true"]},
            "changed_when": True,
        }
        tasks = [guard]
        if crud_fails:
            tasks.append({"ansible.builtin.fail": {"msg": "partial batch: saved first item; second item failed"}})
        tasks.append(block)
        play = tmp_path / "check.yml"
        play.write_text(yaml.safe_dump([{
            "hosts": "localhost", "connection": "local", "gather_facts": False,
            "vars": {f"opnsense_{key}_apply": {"changed": changed}, "opnsense_force_reload": force},
            "tasks": tasks,
        }]))
        result = subprocess.run([
            "uv", "run", "ansible-playbook", "-i", "localhost,", str(play),
            *(["--check"] if check else []),
        ], cwd=ROOT, env=os.environ | {"ANSIBLE_CONFIG": str(ANSIBLE / "ansible.cfg")},
            capture_output=True, text=True)
        assert (result.returncode == 0) == (expected in {"no-op", "activation succeeded"}), result.stdout + result.stderr
        if expected == "no-op":
            assert '"msg": "OPNsense' not in result.stdout
        else:
            assert expected in result.stdout
        if crud_fails:
            assert "Activate saved" not in result.stdout
