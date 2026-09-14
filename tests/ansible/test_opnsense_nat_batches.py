"""Run the three OPNsense batch entrypoints with a stateful local module."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "automation/ansible"

CASES = {
    "nat_destination": {
        "playbook": "manage-dnat.yml",
        "item_tasks": "tasks/manage-dnat-item.yml",
        "resource": "dnat",
        "key": "opnsense_dnat_rules",
        "fixture": "dnat.yml",
    },
    "nat_one_to_one": {
        "playbook": "manage-one-to-one-nat.yml",
        "item_tasks": "tasks/manage-one-to-one-nat-item.yml",
        "resource": "one-to-one-nat",
        "key": "opnsense_one_to_one_nat_rules",
        "fixture": "one-to-one-nat.yml",
    },
    "rule_interface_group": {
        "playbook": "manage-interface-groups.yml",
        "item_tasks": "tasks/manage-interface-group-item.yml",
        "resource": "interface-groups",
        "key": "opnsense_interface_groups",
        "fixture": "interface-groups.yml",
    },
}


FAKE_MODULE = r'''
from ansible.module_utils.basic import AnsibleModule
import json
from pathlib import Path

m = AnsibleModule(
    argument_spec={
        "action": {"type": "str", "required": True},
        "resource": {"type": "str", "required": True},
        "state_file": {"type": "str", "required": True},
        "desired": {"type": "dict", "default": {}},
    },
    supports_check_mode=True,
)
path = Path(m.params["state_file"])
state = json.loads(path.read_text())
action = m.params["action"]
resource = m.params["resource"]

def save():
    path.write_text(json.dumps(state))

if action == "read":
    m.exit_json(changed=False, data=state["records"])

if action == "activate":
    state["activations"].append(resource)
    save()
    if state["activation_fail"]:
        m.fail_json(msg="synthetic activation failed")
    m.exit_json(changed=True, response={"status": "ok"})

desired = m.params["desired"]
identity_field = "name" if resource == "interface-groups" else "description"
identity = desired.get(identity_field)
existing = next((item for item in state["records"] if item.get(identity_field) == identity), None)
if desired.get("state") == "absent":
    changed = existing is not None
else:
    changed = existing != desired

if m.check_mode:
    m.exit_json(changed=changed)

state["mutation_attempts"].append(identity)
if state["fail_at"] and len(state["mutation_attempts"]) == state["fail_at"]:
    save()
    m.fail_json(msg="synthetic batch item failure")

if changed:
    state["writes"].append(identity)
    state["records"] = [
        item for item in state["records"] if item.get(identity_field) != identity
    ]
    if desired.get("state") != "absent":
        state["records"].append(desired)
save()
m.exit_json(changed=changed)
'''


def _initial_state(*, fail_at=0, activation_fail=False):
    return {
        "records": [],
        "mutation_attempts": [],
        "writes": [],
        "activations": [],
        "fail_at": fail_at,
        "activation_fail": activation_fail,
    }


def _records(resource, count):
    case = CASES[resource]
    document = yaml.safe_load(
        (ROOT / "tests/fixtures/opnsense-nat" / case["fixture"]).read_text()
    )
    record = document[case["key"]][0]
    records = []
    for index in range(count):
        item = deepcopy(record)
        if resource == "rule_interface_group":
            item["name"] = ("InsideA", "InsideB", "InsideC")[index]
        else:
            item["slug"] = ("web-a", "web-b", "web-c")[index]
        records.append(item)
    return records


def _identity(resource, record):
    return record["name"] if resource == "rule_interface_group" else (
        f"iaas:opnsense:{CASES[resource]['resource']}:{record['scope']}:{record['slug']}"
    )


def _replace_modules(node, *, resource, state_file, item_tasks):
    providers = {
        "oxlorg.opnsense.list": "read",
        "oxlorg.opnsense.nat_destination": "mutate",
        "oxlorg.opnsense.nat_one_to_one": "mutate",
        "oxlorg.opnsense.rule_interface_group": "mutate",
        "oxlorg.opnsense.reload": "activate",
        "oxlorg.opnsense.raw": "activate",
    }
    if isinstance(node, list):
        return [
            _replace_modules(item, resource=resource, state_file=state_file, item_tasks=item_tasks)
            for item in node
        ]
    if not isinstance(node, dict):
        return node

    result = {}
    for key, value in node.items():
        if key in providers:
            action = providers[key]
            args = {"action": action, "resource": resource, "state_file": str(state_file)}
            if action == "mutate":
                args["desired"] = value
            result["test_opnsense_batch"] = args
        elif key == "ansible.builtin.include_tasks" and value == item_tasks:
            result[key] = str(state_file.parent / "managed-item.yml")
        else:
            result[key] = _replace_modules(
                value, resource=resource, state_file=state_file, item_tasks=item_tasks
            )
    return result


def run_play(tmp_path, resource, records, *, force=False, check=False, fail_at=0,
             activation_fail=False, state_file=None):
    case = CASES[resource]
    state_file = state_file or tmp_path / "state.json"
    if not state_file.exists():
        state_file.write_text(json.dumps(_initial_state(
            fail_at=fail_at, activation_fail=activation_fail
        )))

    library = tmp_path / "library"
    library.mkdir(exist_ok=True)
    (library / "test_opnsense_batch.py").write_text(FAKE_MODULE)
    local_temp = tmp_path / "local"
    local_temp.mkdir(exist_ok=True)

    source = yaml.safe_load((ANSIBLE / "playbooks/opnsense" / case["playbook"]).read_text())[0]
    item_source = yaml.safe_load((ANSIBLE / "playbooks/opnsense" / case["item_tasks"]).read_text())
    read = next(task for task in source["tasks"] if "oxlorg.opnsense.list" in task)
    preflight = next(task for task in source["tasks"] if task["name"].lower().startswith("preflight"))
    initialize = next(task for task in source["tasks"] if task["name"].startswith("Initialize"))
    reconciliation = next(task for task in source["tasks"] if task["name"].startswith("Reconcile"))
    activation = source["tasks"][-1]

    transformed_item = _replace_modules(
        item_source, resource=case["resource"], state_file=state_file,
        item_tasks=case["item_tasks"],
    )
    (state_file.parent / "managed-item.yml").write_text(yaml.safe_dump(transformed_item))
    tasks = _replace_modules(
        [read, preflight, initialize, reconciliation, activation],
        resource=case["resource"], state_file=state_file, item_tasks=case["item_tasks"],
    )
    play = {
        "hosts": "localhost",
        "connection": "local",
        "gather_facts": False,
        "vars": {
            case["key"]: records,
            "managed_resource": case["resource"],
            "managed_resource_key": case["key"],
            "opnsense_api_host": "synthetic.invalid",
            "opnsense_api_key": "synthetic",
            "opnsense_api_secret": "synthetic",
            "opnsense_ssl_verify": False,
            "opnsense_force_reload": force,
        },
        "tasks": tasks,
    }
    play_path = tmp_path / "batch.yml"
    play_path.write_text(yaml.safe_dump([play]))
    result = subprocess.run(
        ["uv", "run", "ansible-playbook", "-i", "localhost,", str(play_path),
         *( ["--check"] if check else [] )],
        cwd=ROOT,
        env=os.environ | {
            "ANSIBLE_CONFIG": str(ANSIBLE / "ansible.cfg"),
            "ANSIBLE_LIBRARY": str(library),
            "ANSIBLE_LOCAL_TEMP": str(local_temp),
        },
        capture_output=True,
        text=True,
    )
    return result, json.loads(state_file.read_text())


@pytest.mark.parametrize("resource", list(CASES))
def test_two_changed_items_activate_once(tmp_path, resource):
    records = _records(resource, 2)
    result, state = run_play(tmp_path, resource, records)
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["writes"] == [_identity(resource, item) for item in records]
    assert state["activations"] == [CASES[resource]["resource"]]


@pytest.mark.parametrize("resource", list(CASES))
def test_partial_failure_stops_third_item_and_activation(tmp_path, resource):
    records = _records(resource, 3)
    result, state = run_play(tmp_path, resource, records, fail_at=2)
    assert result.returncode != 0
    assert state["mutation_attempts"] == [_identity(resource, item) for item in records[:2]]
    assert state["writes"] == [_identity(resource, records[0])]
    assert state["records"] and state["activations"] == []
    assert "later" in result.stdout and "activation" in result.stdout


@pytest.mark.parametrize("resource", list(CASES))
def test_force_reload_recovers_without_new_changes(tmp_path, resource):
    records = _records(resource, 2)
    result, state = run_play(tmp_path, resource, records)
    assert result.returncode == 0, result.stdout + result.stderr
    result, state = run_play(tmp_path, resource, records, force=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["writes"] == [_identity(resource, item) for item in records]
    assert state["activations"] == [CASES[resource]["resource"]] * 2


@pytest.mark.parametrize("resource", list(CASES))
def test_check_mode_does_not_write_or_activate(tmp_path, resource):
    records = _records(resource, 2)
    state_file = tmp_path / "state.json"
    initial = _initial_state()
    state_file.write_text(json.dumps(initial))
    result, state = run_play(tmp_path, resource, records, check=True, force=True,
                             state_file=state_file)
    assert result.returncode == 0, result.stdout + result.stderr
    assert state == initial


@pytest.mark.parametrize("resource", list(CASES))
def test_empty_batch_does_not_activate(tmp_path, resource):
    result, state = run_play(tmp_path, resource, [])
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["records"] == state["writes"] == state["mutation_attempts"] == []
    assert state["activations"] == []


@pytest.mark.parametrize("resource", list(CASES))
def test_activation_failure_reports_saved_configuration(tmp_path, resource):
    records = _records(resource, 2)
    result, state = run_play(tmp_path, resource, records, activation_fail=True)
    assert result.returncode != 0
    assert state["writes"] == [_identity(resource, item) for item in records]
    assert state["activations"] == [CASES[resource]["resource"]]
    assert "activation failed" in result.stdout
    assert "saved configuration may differ" in result.stdout
