"""Installation state table using disposable files and read-only observations."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import os

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = load("installation_probe", "automation/ansible/roles/k3s_preflight/files/probe_installation.py")
FILTER = load("installation_filter", "automation/ansible/filter_plugins/k3s_observations.py")
VERSION = "v1.35.1+k3s1"


@pytest.mark.parametrize("role", ["server", "agent"])
def test_probe_task_renders_real_model_and_unit_templates(tmp_path, role):
    ansible = ROOT / "automation/ansible"
    model = yaml.safe_load((ROOT / "tests/fixtures/k3s/expected-review.yml").read_text())
    node = next(dict(item) for item in model["nodes"] if item["role"] == role)
    node["vm_ref"] = "localhost"
    task = next(item for item in yaml.safe_load((ansible / "roles/k3s_preflight/tasks/main.yml").read_text())
                if item["name"].startswith("Observe installation ownership"))
    code = (ansible / "roles/k3s_preflight/files/probe_installation.py").read_text()
    assert code.count("probe(json.load(sys.stdin))") == 1
    code = code.replace("probe(json.load(sys.stdin))", "probe(json.load(sys.stdin), Path(" + repr(str(tmp_path / "root")) + "))")
    task["ansible.builtin.command"]["argv"][2] = code
    play = tmp_path / "probe.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": {"k3s_model": model, "k3s_preflight_node": node, "k3s_preflight_reachable": True,
                 "role_path": str(ansible / "roles/k3s_preflight")},
        "tasks": [{"ansible.builtin.set_fact": {"k3s_model": model}}, task, {"ansible.builtin.assert": {"that": [
            "(k3s_preflight_installation_probe.stdout | from_json).state == 'fresh'"]}}],
    }]))
    result = subprocess.run(["uv", "run", "ansible-playbook", "-i", "localhost,", str(play)], cwd=ROOT,
                            env=os.environ | {"ANSIBLE_CONFIG": str(ansible / "ansible.cfg")}, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("state", ["fresh", "artifact-only", "managed", "foreign-unit", "foreign-config", "dropin"])
def test_read_only_state_probe(tmp_path, state):
    expected = {"role": "server", "config": 'node-name: "node-a"\n', "unit": "[Service]\nExecStart=/usr/local/bin/k3s server\n"}
    if state != "fresh":
        binary = tmp_path / "usr/local/bin/k3s"
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nprintf "k3s version ' + VERSION + ' (synthetic)\\n"\n')
        binary.chmod(0o755)
        expected["sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    if state not in {"fresh", "artifact-only"}:
        config = tmp_path / "etc/rancher/k3s/config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text(expected["config"] + 'token: "never-print-this"\n')
        unit = tmp_path / "etc/systemd/system/k3s.service"
        unit.parent.mkdir(parents=True)
        unit.write_text(expected["unit"])
        (tmp_path / "var/lib/rancher/k3s").mkdir(parents=True)
        if state == "foreign-unit":
            unit.write_text("[Service]\nExecStart=/other/binary server\n")
        if state == "foreign-config":
            config.write_text('node-name: "foreign-node"\n')
    def run(argv, **kwargs):
        if argv[0] != "systemctl":
            return subprocess.run(argv, **kwargs)
        return subprocess.CompletedProcess(argv, 0, "FragmentPath=/etc/systemd/system/k3s.service\nActiveState=active\nDropInPaths="
                                           + ("/foreign.conf" if state == "dropin" else "") + "\n", "")
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    facts = PROBE.probe(expected, tmp_path, run)
    after = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert before == after
    assert facts["state"] == (state if state in {"fresh", "artifact-only", "managed"} else "foreign")
    assert "never-print-this" not in json.dumps(facts)


@pytest.mark.parametrize("state,observed,allowed", [
    ("fresh", "", {"install", "converge"}),
    ("artifact-only", VERSION, {"converge"}),
    ("managed", VERSION, {"converge", "upgrade"}),
    ("managed", "v1.34.0+k3s1", {"upgrade"}),
    ("managed", "v1.33.0+k3s1", set()),
    ("foreign", VERSION, set()),
    ("unknown", "", set()),
])
def test_operation_state_table(state, observed, allowed):
    facts = {"state": state, "version": observed, "sha256": "a" * 64, "datastore": True}
    for mode in ["install", "converge", "upgrade"]:
        assert FILTER.k3s_installation_allowed(facts, mode, VERSION, "a" * 64) == (mode in allowed)
    facts["sha256"] = "b" * 64
    if state == "artifact-only":
        assert not FILTER.k3s_installation_allowed(facts, "converge", VERSION, "a" * 64)


@pytest.mark.parametrize("case", ["correct", "old-version", "wrong-node", "not-ready", "duplicate"])
def test_exact_node_observation(case):
    node = {"metadata": {"name": "node-a", "labels": {"node-role.kubernetes.io/control-plane": "true"}},
            "status": {"nodeInfo": {"kubeletVersion": VERSION}, "conditions": [{"type": "Ready", "status": "True"}]}}
    if case == "old-version":
        node["status"]["nodeInfo"]["kubeletVersion"] = "v1.34.0+k3s1"
    if case == "wrong-node":
        node["metadata"]["name"] = "node-a-extra"
    if case == "not-ready":
        node["status"]["conditions"][0]["status"] = "False"
    payload = {"items": [node, node] if case == "duplicate" else [node]}
    assert FILTER.k3s_node_healthy(payload, {"vm_ref": "node-a", "role": "server"}, VERSION) == (case == "correct")
