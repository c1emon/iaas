"""Real acquisition/checksum/version/copy tasks with local inert transport and service."""

import copy
import hashlib
import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "automation/ansible"


@pytest.mark.parametrize("failure", ["download", "checksum", "version", "stop", "none"])
def test_stage_before_stop_and_activation(tmp_path, failure):
    binary = tmp_path / "k3s"
    binary.write_text("old-active-binary")
    service = tmp_path / "service"
    service.write_text("active")
    artifact = tmp_path / "artifact"
    version = "v1.35.1+k3s1"
    payload = '#!/bin/sh\nprintf "%s\\n" "k3s version ' + ("v1.34.0+k3s1" if failure == "version" else version) + ' (synthetic)"\n'
    artifact.write_text(payload)
    checksum = "0" * 64 if failure == "checksum" else hashlib.sha256(payload.encode()).hexdigest()
    acquisition = yaml.safe_load((ANSIBLE / "roles/k3s_acquisition/tasks/main.yml").read_text())
    download = next(task["ansible.builtin.get_url"] for task in acquisition if "ansible.builtin.get_url" in task)
    download["url"] = (tmp_path / "missing" if failure == "download" else artifact).as_uri()
    download.pop("owner")
    download.pop("group")
    acquisition_path = tmp_path / "acquisition.yml"
    acquisition_path.write_text(yaml.safe_dump(acquisition))
    source = yaml.safe_load((ANSIBLE / "roles/k3s_upgrade/tasks/main.yml").read_text())
    names = [task["name"] for task in source]
    start = names.index("Stage the exact target before stopping any service")
    end = names.index("Start the selected K3s service after replacing its executable")
    tasks = copy.deepcopy(source[start:end])
    stage = tasks[0]["block"][0]
    stage.pop("ansible.builtin.include_role")
    stage["ansible.builtin.include_tasks"] = str(acquisition_path)
    stop = next(task for task in tasks if task["name"].startswith("Stop the selected"))["block"][0]
    stop.pop("ansible.builtin.systemd")
    stop["ansible.builtin.command"] = {"argv": ["/usr/bin/false"] if failure == "stop" else
                                      ["/bin/sh", "-c", 'printf stopped > "$1"', "service", str(service)]}
    activate = tasks[-1]["block"][0]["ansible.builtin.copy"]
    activate.pop("owner")
    activate.pop("group")
    play = tmp_path / "stage.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": {"k3s_upgrade_skip": False, "k3s_upgrade_synthetic": False,
                 "k3s_upgrade_node": {"vm_ref": "localhost", "role": "server", "architecture": "amd64"},
                 "k3s_upgrade_model": {"cluster": {"version": version, "artifacts": {
                     "amd64": {"url": "https://artifacts.invalid/binary", "sha256": checksum}}}},
                 "k3s_upgrade_binary_path": str(binary), "k3s_upgrade_service_name": "k3s",
                 "k3s_upgrade_runtime_proxy": "", "k3s_upgrade_runtime_secret_file": ""},
        "tasks": tasks,
    }]))
    result = subprocess.run(["uv", "run", "ansible-playbook", "-i", "localhost,", str(play)], cwd=ROOT,
                            env=os.environ | {"ANSIBLE_CONFIG": str(ANSIBLE / "ansible.cfg")},
                            capture_output=True, text=True)
    assert (result.returncode == 0) == (failure == "none"), result.stdout + result.stderr
    assert binary.read_text() == (payload if failure == "none" else "old-active-binary")
    assert service.read_text() == ("stopped" if failure == "none" else "active")
