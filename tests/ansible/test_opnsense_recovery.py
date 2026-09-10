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
    if resource == 'aliases':
        mutation = yaml.safe_load((ANSIBLE / 'playbooks/opnsense/tasks/apply-alias-batch.yml').read_text())[0]
    else:
        reconciliation = next(task for task in source["tasks"] if task["name"].startswith("Reconcile declared"))
        mutation = reconciliation["block"][0]
    module = next(name for name in mutation if name.startswith("oxlorg.opnsense."))
    assert mutation[module]["reload"] is False
    for changed, force, check, reload_fails, expected in [
        (False, False, False, False, "no-op"),
        (True, False, False, True, "activation failed"),
        (False, True, False, False, "activation succeeded"),
        (True, True, True, False, "no-op"),
        (False, "true", False, False, "must be a YAML or JSON boolean"),
    ]:
        block = deepcopy(activation)
        block["block"][0] = {
            "name": original_reload["name"],
            "ansible.builtin.command": {"argv": ["/usr/bin/false" if reload_fails else "/usr/bin/true"]},
            "changed_when": True,
        }
        tasks = [guard, block]
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


@pytest.mark.parametrize("resource", ["gateways", "vips", "filter-rules"])
def test_actual_crud_failure_reports_saved_partial_configuration(tmp_path, resource):
    """Run the product's CRUD block/rescue with an inert write-then-fail adapter."""
    source = yaml.safe_load((ANSIBLE / f"playbooks/opnsense/manage-{resource}.yml").read_text())[0]
    reconciliation = deepcopy(next(task for task in source["tasks"] if task["name"].startswith("Reconcile declared")))
    mutation = reconciliation['block'][0]
    module = next(name for name in mutation if name.startswith('oxlorg.opnsense.'))
    mutation.pop(module)
    # Each failed invocation leaves a marker proving an earlier item was saved.
    marker = tmp_path / 'saved'
    script = ("from pathlib import Path; import sys; p=Path(sys.argv[1]); "
              "sys.exit(1) if p.exists() else p.write_text('saved first item')")
    if resource == 'filter-rules':
        script = "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('saved first item'); sys.exit(1)"
    mutation['ansible.builtin.command'] = {'argv': [
        'uv', 'run', 'python', '-c', script, str(marker),
    ]}
    document = yaml.safe_load((ROOT / 'tests/fixtures/environment/ansible/vars/opnsense' / f'{resource}.yml').read_text())
    if resource == 'filter-rules':
        document['opnsense_filter_rule_apply_rules'] = document.pop('opnsense_filter_rules')
    else:
        key = next(iter(document))
        document[key] = [document[key][0], deepcopy(document[key][0])]
    activation = deepcopy(source['tasks'][-1])
    activation['block'][0] = {'name': 'Unexpected activation', 'ansible.builtin.command': {'argv': ['/usr/bin/true']}}
    play = tmp_path / 'crud.yml'
    play.write_text(yaml.safe_dump([{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                                   'vars': document, 'tasks': [reconciliation, activation]}]))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(play)], cwd=ROOT,
                            env=os.environ | {'ANSIBLE_CONFIG': str(ANSIBLE / 'ansible.cfg')},
                            capture_output=True, text=True)
    assert result.returncode != 0 and marker.read_text() == 'saved first item', result.stdout + result.stderr
    assert 'Partial configuration changes may have been saved' in result.stdout
    assert 'activation was not attempted' in result.stdout
    assert 'No rollback was performed' in result.stdout and 'opnsense_force_reload=true' in result.stdout
    assert 'TASK [Unexpected activation]' not in result.stdout
