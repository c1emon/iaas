"""Exercise bootstrap input validation and rendering without modifying a host."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "automation/ansible/playbooks/pve/bootstrap-pve-ssh-user.yml"


@pytest.mark.parametrize("inputs,success", [
    ({}, False),
    ({"pve_bootstrap_user": "site-ops"}, False),
    ({"pve_bootstrap_user": "root", "pve_bootstrap_authorized_key": "ssh-ed25519 AAAA fixture"}, False),
    ({"pve_bootstrap_user": "site-ops\nALL", "pve_bootstrap_authorized_key": "ssh-ed25519 AAAA fixture"}, False),
    ({"pve_bootstrap_user": "site-ops", "pve_bootstrap_authorized_key": "   "}, False),
    ({"pve_bootstrap_user": "site-ops", "pve_bootstrap_authorized_key": "ssh-ed25519 AAAA fixture"}, True),
])
def test_bootstrap_requires_inventory_identity_and_renders_same_user(tmp_path, inputs, success):
    source = yaml.safe_load(PLAYBOOK.read_text())[0]
    assert "pve_bootstrap_user" not in source["vars"]
    assert "pve_bootstrap_authorized_key" not in source["vars"]
    user_task = next(task["ansible.builtin.user"] for task in source["tasks"] if "ansible.builtin.user" in task)
    sudo_task = next(task["ansible.builtin.template"] for task in source["tasks"] if "ansible.builtin.template" in task)
    assert sudo_task["validate"] == "/usr/sbin/visudo -cf %s"
    ssh_dir = next(task["ansible.builtin.file"] for task in source["tasks"] if "ansible.builtin.file" in task)
    assert ssh_dir["path"] == "{{ pve_bootstrap_user_result.home }}/.ssh"
    key_task = next(task["ansible.builtin.copy"] for task in source["tasks"]
                    if task.get("name") == "Install the caller-provided authorized public key")
    assert key_task["dest"] == "{{ pve_bootstrap_user_result.home }}/.ssh/authorized_keys"
    # Execute the real first validation task and actual template lookup. All
    # mutating tasks are excluded; values arrive through inventory, not -e.
    variables = dict(source["vars"])
    variables["pve_bootstrap_snippet_wrapper_sudoers_src"] = str(
        ROOT / "automation/pve-node/sudoers.d/iaas-pve-snippet-upload.j2")
    variables["rendered_user"] = user_task["name"]
    variables["rendered_sudoers"] = "{{ lookup('ansible.builtin.template', pve_bootstrap_snippet_wrapper_sudoers_src) }}"
    play = {"hosts": "all", "gather_facts": False, "vars": variables, "tasks": [
        source["tasks"][0],
        {"name": "Check shared identity binding", "ansible.builtin.assert": {"that": [
            "rendered_user == 'site-ops'",
            "'site-ops ALL=(root) NOPASSWD: /usr/local/sbin/iaas-pve-snippet-upload' in rendered_sudoers",
            "'pve-ops ALL=' not in rendered_sudoers",
        ]}},
    ]}
    harness = tmp_path / "validate.yml"
    harness.write_text(yaml.safe_dump([play]))
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": {"localhost": {
        "ansible_connection": "local", **inputs}}}}))
    result = subprocess.run([sys.executable, "-m", "ansible.cli.playbook", "-i", str(inventory), str(harness)],
        capture_output=True, text=True, cwd=tmp_path,
        env=os.environ | {"ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-tmp")}, check=False)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    if not success:
        assert "Provide pve_bootstrap_user" in result.stdout


@pytest.mark.parametrize("existing,broader,success", [
    ("legacy", False, True), ("current", False, True), ("absent", False, True),
    ("legacy", True, True), ("unmanaged", False, False), ("symlink", False, False),
])
def test_bootstrap_override_managed_cleanup_and_identity_switch(tmp_path, existing, broader, success):
    source = yaml.safe_load(PLAYBOOK.read_text())[0]
    override = tmp_path / "override"
    legacy = "# Managed by automation/ansible/playbooks/pve/bootstrap-pve-ops.yml\nold-user ALL=(root) NOPASSWD: /bin/true\n"
    if existing == "symlink":
        target = tmp_path / "site-file"
        target.write_text(legacy)
        override.symlink_to(target)
    elif existing != "absent":
        content = legacy if existing == "legacy" else legacy.replace("bootstrap-pve-ops", "bootstrap-pve-ssh-user")
        if existing == "unmanaged":
            content = "# Site-owned\nold-user ALL=(root) NOPASSWD: /bin/true\n"
        override.write_text(content)
    original = override.read_text() if override.exists() else None
    tasks = [task for task in source["tasks"] if task["name"] in {
        "Inspect existing bootstrap override", "Require a regular bootstrap override file",
        "Read existing bootstrap override ownership marker", "Require a managed bootstrap override marker",
        "Remove managed override when restoring default permissions",
        "Install optional broader sudo allowlist when requested"}]
    # Redirect only the fixed destination into the disposable local fixture.
    # Native visudo and root ownership are covered by playbook syntax/lint;
    # this test exercises actual Ansible guard/removal/copy semantics.
    tasks = yaml.safe_load(yaml.safe_dump(tasks).replace("/etc/sudoers.d/iaas-pve-bootstrap-override", str(override)))
    for task in tasks:
        if "ansible.builtin.copy" in task:
            for key in ("owner", "group", "validate"):
                task["ansible.builtin.copy"].pop(key)
    variables = dict(source["vars"])
    variables["pve_bootstrap_user"] = "new-user"
    if broader:
        variables["pve_bootstrap_sudo_commands"] = ["/bin/true"]
    play = tmp_path / "override.yml"
    play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local",
        "gather_facts": False, "vars": variables, "tasks": tasks}]))
    for _ in range(2):
        result = subprocess.run([sys.executable, "-m", "ansible.cli.playbook", "-i", "localhost,", str(play)],
            capture_output=True, text=True, cwd=tmp_path,
            env=os.environ | {"ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-tmp")}, check=False)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        if not success:
            assert override.read_text() == original
        elif broader:
            assert "new-user ALL=(root) NOPASSWD: /bin/true" in override.read_text()
            assert "old-user" not in override.read_text()
        else:
            assert not override.exists()
