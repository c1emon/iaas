"""Synthetic provider-stage coverage for the explicit OPNsense workflow."""

from pathlib import Path
import json
import os
import subprocess
from typing import Any

import pytest
import yaml

from iaas.opnsense_workflow.writer import (
    Writer,
    WriterError,
    provider_arguments,
)


ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "automation/ansible/playbooks/opnsense/workflow-stage.yml"
SAVE_TASKS = ROOT / "automation/ansible/playbooks/opnsense/tasks/workflow-stage-save.yml"
ACTIVATE_TASKS = ROOT / "automation/ansible/playbooks/opnsense/tasks/workflow-stage-activate.yml"


class FakeProvider:
    def __init__(self, *, save_result: dict[str, Any] | None = None,
                 activation_result: dict[str, Any] | None = None,
                 save_error: Exception | None = None,
                 activation_error: Exception | None = None) -> None:
        self.save_result = save_result or {"changed": True}
        self.activation_result = activation_result or {"response": {"status": "ok"}}
        self.save_error = save_error
        self.activation_error = activation_error
        self.save_calls: list[tuple[str, list[dict[str, Any]], bool]] = []
        self.activation_calls: list[str] = []

    def save(self, resource, records, *, reload):
        self.save_calls.append((resource, list(records), reload))
        if self.save_error:
            raise self.save_error
        return self.save_result

    def activate(self, resource):
        self.activation_calls.append(resource)
        if self.activation_error:
            raise self.activation_error
        return self.activation_result


def _record(path: str, key: str) -> dict[str, Any]:
    document = yaml.safe_load((ROOT / path).read_text())
    return document[key][0]


def test_save_does_not_activate_and_disables_provider_reload() -> None:
    provider = FakeProvider()
    writer = Writer(provider)
    record = _record("tests/fixtures/environment/ansible/vars/opnsense/vips.yml", "opnsense_vips")

    result = writer.save("vips", [record])

    assert result["status"] == "saved"
    assert result["save"]["status"] == "saved"
    assert provider.save_calls[0][0] == "vips"
    assert provider.save_calls[0][2] is False
    assert provider.activation_calls == []


def test_no_change_save_is_distinct_from_provider_acceptance() -> None:
    provider = FakeProvider(save_result={"changed": False})

    result = Writer(provider).save(
        "interface-groups",
        [_record("tests/fixtures/opnsense-nat/interface-groups.yml", "opnsense_interface_groups")],
    )

    assert result["status"] == "unchanged"
    assert result["activation"]["status"] == "not_attempted"


@pytest.mark.parametrize("error,expected", [(RuntimeError("write"), "failed"),
                                             (TimeoutError("timeout"), "unknown")])
def test_save_failure_and_timeout_are_preserved_without_activation(error, expected) -> None:
    provider = FakeProvider(save_error=error)
    record = _record("tests/fixtures/opnsense-nat/dnat.yml", "opnsense_dnat_rules")

    result = Writer(provider).save("dnat", [record])

    assert result["status"] == expected
    assert result["configuration"]["status"] == "unknown"
    assert provider.activation_calls == []


def test_activation_is_explicit_and_groups_request_acceptance_is_not_confirmation() -> None:
    provider = FakeProvider()
    writer = Writer(provider)

    result = writer.activate("interface-groups")

    assert result["status"] == "accepted"
    assert result["activation"]["status"] == "accepted"
    assert result["active_check"]["status"] == "not_attempted"
    assert provider.activation_calls == ["interface-groups"]


def test_provider_response_without_adapter_status_stays_unconfirmed() -> None:
    """A nested provider response is not the writer adapter's status field."""
    result = Writer(FakeProvider()).activate("dnat")

    assert result["status"] == "unconfirmed"
    assert result["activation"]["status"] == "unconfirmed"
    assert result["active_check"]["status"] == "not_attempted"


@pytest.mark.parametrize("resource", ["vips", "filter-rules", "dnat", "one-to-one-nat"])
def test_trusted_completion_status_is_preserved_for_reload_targets(resource: str) -> None:
    provider = FakeProvider(activation_result={"status": "confirmed"})

    result = Writer(provider).activate(resource)

    assert result["status"] == "confirmed"


def test_activation_confirmation_requires_independent_active_evidence() -> None:
    provider = FakeProvider(activation_result={"active_confirmed": True})

    result = Writer(provider).activate("dnat")

    assert result["status"] == "unconfirmed"


def test_runtime_writer_reads_protected_stage_facts(tmp_path) -> None:
    class Outputs:
        def path(self, category):
            directory = tmp_path / category
            directory.mkdir(exist_ok=True)
            return directory

    class Execution:
        outputs = Outputs()
        environ = {"OPNSENSE_API_KEY": "synthetic", "OPNSENSE_API_SECRET": "synthetic"}

        def run(self, phase, command, cwd):
            variables = Path(command[command.index("-e") + 1][1:]).read_text()
            values = json.loads(variables)
            assert values["opnsense_api_host"] == "2001:db8::1"
            assert values["opnsense_api_port"] == 8443
            result_path = values["opnsense_workflow_result_path"]
            Path(result_path).write_text(json.dumps({"status": "accepted", "changed": True}))

    record = _record("tests/fixtures/opnsense-nat/dnat.yml", "opnsense_dnat_rules")
    result = Writer(Execution(), {"host": "fw", "endpoint": "https://[2001:db8::1]:8443", "ssl_verify": True}).save("dnat", [record])

    assert result["status"] == "saved"
    assert result["changed"] is True


def test_runtime_writer_rejects_http_collection_endpoint() -> None:
    with pytest.raises(WriterError, match="HTTPS"):
        Writer(object(), {"host": "fw", "endpoint": "http://fw.example:8443", "ssl_verify": True})

    with pytest.raises(WriterError, match="port"):
        Writer(object(), {"host": "fw", "endpoint": "https://fw.example:0", "ssl_verify": True})


def test_runtime_writer_does_not_reuse_a_previous_stage_fact(tmp_path) -> None:
    class Outputs:
        def path(self, category):
            directory = tmp_path / category
            directory.mkdir(exist_ok=True)
            return directory

    class Execution:
        outputs = Outputs()
        calls = 0

        def run(self, phase, command, cwd):
            self.calls += 1
            if self.calls == 1:
                variables = Path(command[command.index("-e") + 1][1:]).read_text()
                result_path = json.loads(variables)["opnsense_workflow_result_path"]
                Path(result_path).write_text(json.dumps({"status": "accepted", "changed": True}))
            else:
                raise RuntimeError("synthetic stage failed before facts")

    execution = Execution()
    target = {"host": "fw", "endpoint": "https://fw.example", "ssl_verify": True}
    record = _record("tests/fixtures/opnsense-nat/dnat.yml", "opnsense_dnat_rules")
    writer = Writer(execution, target)

    assert writer.save("dnat", [record])["status"] == "saved"
    assert writer.save("dnat", [record])["status"] == "failed"


def test_stage_rejects_invalid_loaded_source_before_credentials(tmp_path) -> None:
    source = tmp_path / "invalid.yml"
    source.write_text("opnsense_aliases:\n  - name: BROKEN\n")
    inventory = tmp_path / "inventory.yml"
    inventory.write_text("all:\n  children:\n    opnsense:\n      hosts:\n        localhost:\n")
    result_path = tmp_path / "stage-result.json"
    result = subprocess.run(
        [
            "uv", "run", "ansible-playbook", "-i", str(inventory),
            "--limit", "localhost",
            "-e", f"opnsense_workflow_resource=aliases",
            "-e", f"opnsense_workflow_action=save",
            "-e", f"opnsense_workflow_source={source}",
            "-e", f"opnsense_workflow_result_path={result_path}",
            "-e", "opnsense_api_host=synthetic.invalid",
            "-e", "opnsense_ssl_verify=false",
            str(PLAYBOOK),
        ],
        cwd=ROOT,
        env=os.environ | {"ANSIBLE_CONFIG": str(ROOT / "automation/ansible/ansible.cfg")},
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "opnsense validation failed" in output
    assert "Assert OPNsense API credentials" not in output


def test_invalid_records_fail_before_provider_call() -> None:
    provider = FakeProvider()

    with pytest.raises(WriterError, match="invalid aliases"):
        Writer(provider).save("aliases", [{"name": "bad"}])

    assert provider.save_calls == []


def test_filter_context_is_retained_for_rule_safety_admission() -> None:
    provider = FakeProvider()
    record = {
        "scope": "demo",
        "slug": "deny-external",
        "state": "present",
        "enabled": True,
        "sequence": 10,
        "interface": ["lan"],
        "direction": "in",
        "action": "block",
        "quick": True,
        "ip_protocol": "inet",
        "protocol": "any",
        "source_net": "any",
        "destination_net": ["LOCAL_NETS"],
        "destination_invert": True,
    }
    context = {
        "interface_networks": {"lan": ["192.0.2.0/24"]},
        "aliases": [{
            "name": "LOCAL_NETS", "type": "network", "content": ["192.0.2.0/24"],
            "description": "synthetic", "enabled": True, "state": "present",
        }],
    }

    result = Writer(provider, documents={"filter-rules": {
        "opnsense_filter_rule_context": context,
    }}).save("filter-rules", [record])

    assert result["status"] == "saved"
    assert len(provider.save_calls) == 1

    # Exercise the loaded-value Ansible filter, not only Writer's initial check.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'workflow_admission', ROOT / 'automation/ansible/filter_plugins/opnsense_resources.py')
    assert spec is not None and spec.loader is not None
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    assert plugin.opnsense_resource_admission([record], 'filter-rules', context)
    with pytest.raises(ValueError):
        plugin.opnsense_resource_admission([record], 'filter-rules')


@pytest.mark.parametrize(
    "resource,path,key,module",
    [
        ("aliases", "tests/fixtures/environment/ansible/vars/opnsense/aliases.yml", "opnsense_aliases", "alias_multi"),
        ("vips", "tests/fixtures/environment/ansible/vars/opnsense/vips.yml", "opnsense_vips", "interface_vip"),
        ("gateways", "tests/fixtures/environment/ansible/vars/opnsense/gateways.yml", "opnsense_gateways", "gateway"),
        ("filter-rules", "tests/fixtures/environment/ansible/vars/opnsense/filter-rules.yml", "opnsense_filter_rules", "rule_multi"),
        ("dnat", "tests/fixtures/opnsense-nat/dnat.yml", "opnsense_dnat_rules", "nat_destination"),
        ("one-to-one-nat", "tests/fixtures/opnsense-nat/one-to-one-nat.yml", "opnsense_one_to_one_nat_rules", "nat_one_to_one"),
        ("interface-groups", "tests/fixtures/opnsense-nat/interface-groups.yml", "opnsense_interface_groups", "rule_interface_group"),
    ],
)
def test_provider_mapping_reuses_fixed_resource_contract(resource, path, key, module) -> None:
    record = _record(path, key)
    arguments = provider_arguments(resource, record)

    assert arguments
    if resource == "filter-rules":
        assert arguments["description"].startswith("iaas:opnsense:filter:")
        assert "scope" not in arguments and "slug" not in arguments
    elif resource in {"dnat", "one-to-one-nat", "interface-groups"}:
        assert module in {"nat_destination", "nat_one_to_one", "rule_interface_group"}
    elif resource in {"vips", "gateways"}:
        assert arguments["reload"] is False


def _walk(value):
    if isinstance(value, list):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)


def test_stage_playbook_keeps_save_and_activation_as_separate_tasks() -> None:
    source = yaml.safe_load(PLAYBOOK.read_text())
    save_source = yaml.safe_load(SAVE_TASKS.read_text())
    activate_source = yaml.safe_load(ACTIVATE_TASKS.read_text())

    assert any("workflow-stage-save.yml" in str(task.get("ansible.builtin.include_tasks", ""))
               for task in source[0]["tasks"])
    assert any("workflow-stage-activate.yml" in str(task.get("ansible.builtin.include_tasks", ""))
               for task in source[0]["tasks"])
    save_modules = [key for task in _walk(save_source) for key in task
                    if key.startswith("oxlorg.opnsense.")]
    assert save_modules
    for task in _walk(save_source):
        for key, value in task.items():
            if key.startswith("oxlorg.opnsense.") and isinstance(value, dict):
                assert value.get("reload", False) is False
    assert not any("reload" in task for task in _walk(activate_source))
    activation_text = ACTIVATE_TASKS.read_text()
    assert "status: confirmed" in activation_text
    assert "native success trusted; internal steps and active state not independently confirmed" in activation_text
    raw_calls = [task["oxlorg.opnsense.raw"] for task in _walk(activate_source)
                 if "oxlorg.opnsense.raw" in task]
    assert len(raw_calls) == 1
    assert source[0]["vars"]["opnsense_workflow_activation_targets"] == {
        "aliases": {"module": "firewall", "controller": "alias", "command": "reconfigure"},
        "vips": {"module": "interfaces", "controller": "vip_settings", "command": "reconfigure"},
        "gateways": {"module": "routing", "controller": "settings", "command": "reconfigure"},
        "filter-rules": {"module": "firewall", "controller": "filter", "command": "apply"},
        "dnat": {"module": "firewall", "controller": "d_nat", "command": "apply"},
        "one-to-one-nat": {"module": "firewall", "controller": "one_to_one", "command": "apply"},
        "interface-groups": {"module": "firewall", "controller": "group", "command": "reconfigure"},
    }


@pytest.mark.parametrize(
    ("response", "expected_ok"),
    [
        ({"response": {"status": "OK\n\n"}}, True),
        ({"response": {"status": "  ok  "}}, True),
        ({"response": {"status": "ok"}}, True),
        ({"response": {"status": "Error (1)"}}, False),
        ({"response": {"status": "   "}}, False),
        ({}, False),
        ({"response": {"status": True}}, False),
        ({"response": {"status": 0}}, False),
    ],
    ids=[
        "uppercase-newline", "lowercase-outer-whitespace", "lowercase", "error", "blank",
        "missing", "boolean", "integer",
    ],
)
def test_activation_failed_when_expression_runs_against_real_ansible(
    tmp_path, response, expected_ok
) -> None:
    source = yaml.safe_load(ACTIVATE_TASKS.read_text())
    failed_when = source[1]["block"][0]["failed_when"]
    playbook = tmp_path / "failed-when.yml"
    playbook.write_text(yaml.safe_dump([{
        "hosts": "localhost",
        "connection": "local",
        "gather_facts": False,
        "tasks": [
            {"ansible.builtin.set_fact": {
                "opnsense_workflow_activation_call": response,
            }},
            {
                "name": "Evaluate activation failed_when",
                "ansible.builtin.debug": {"msg": "synthetic activation"},
                "failed_when": failed_when,
            },
        ],
    }], sort_keys=False))
    result = subprocess.run(
        ["uv", "run", "ansible-playbook", "-i", "localhost,", str(playbook)],
        cwd=ROOT,
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(ROOT / "automation/ansible/ansible.cfg"),
            "ANSIBLE_FILTER_PLUGINS": str(ROOT / "automation/ansible/filter_plugins"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible"),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )

    if expected_ok:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, result.stdout + result.stderr


def test_activation_failure_classification_does_not_export_backend_data(tmp_path) -> None:
    source = yaml.safe_load(ACTIVATE_TASKS.read_text())
    record_failure = source[1]['rescue'][0]
    cases = [
        ({'response': {'status': 'OK\n'}}, 'ok_with_whitespace', [], False),
        ({'response': {'status': 'ok'}}, 'ok', [], False),
        ({'response': {'status': 'private-backend-token'}}, 'other', [], False),
        ({'msg': "API call failed: {'status_code': 403} private-backend-token"}, 'missing', ['403'], False),
        ({'msg': 'Got timeout private-backend-token'}, 'missing', [], True),
    ]
    tasks = []
    for call, expected, codes, timeout in cases:
        tasks.append({'name': 'Classify protected synthetic failure', 'vars': {
            'opnsense_workflow_resource': 'filter-rules', 'opnsense_workflow_activation_call': call,
            'expected_class': expected, 'expected_codes': codes, 'expected_timeout': timeout,
        }, 'block': [record_failure, {'ansible.builtin.assert': {'that': [
            'opnsense_workflow_activation_result.failure.response_status_class | trim == expected_class',
            'opnsense_workflow_activation_result.failure.http_status_codes == expected_codes',
            'opnsense_workflow_activation_result.failure.timeout_reported == expected_timeout',
            "'private-backend-token' not in (opnsense_workflow_activation_result | to_json)",
        ]}}]})
    playbook = tmp_path / 'classify.yml'
    playbook.write_text(yaml.safe_dump([{
        'hosts': 'localhost', 'connection': 'local', 'gather_facts': False, 'tasks': tasks,
    }], sort_keys=False))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(playbook)],
                            cwd=ROOT, env={
                                **os.environ,
                                'ANSIBLE_CONFIG': str(ROOT / 'automation/ansible/ansible.cfg'),
                                'ANSIBLE_FILTER_PLUGINS': str(ROOT / 'automation/ansible/filter_plugins'),
                                'ANSIBLE_LOCAL_TEMP': str(tmp_path / 'ansible'),
                            },
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_writer_preserves_action_association_and_separate_content_evidence() -> None:
    evidence = [{'identity': ['A'], 'source': {'type': 'urltable'}, 'status': 'failed'}]
    provider = FakeProvider(activation_result={'status': 'processing', 'action_id': 'native-1',
                                               'content_update': evidence})
    result = Writer(provider).activate('aliases')
    assert result['status'] == 'processing'
    assert result['action_id'] == 'native-1'
    assert result['content_update'] == evidence
    evidence[0]['status'] = 'confirmed'
    assert result['content_update'][0]['status'] == 'failed'
    assert provider.activation_calls == ['aliases']
