"""Synthetic contract tests for the optional VM baseline egress policy."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from ansible.errors import AnsibleFilterError


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
ROLE = ANSIBLE_DIR / "roles" / "vm_baseline"
PLAYBOOK = ANSIBLE_DIR / "playbooks" / "pve" / "bootstrap-guests.yml"
FIXTURES = ROOT / "tests" / "fixtures" / "vm_baseline_egress"

_SPEC = importlib.util.spec_from_file_location("vm_baseline_egress", ANSIBLE_DIR / "filter_plugins" / "vm_baseline_egress.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
normalize = _MODULE.normalize

NICS = [
    {"ip_address": "192.0.2.20", "network_cidr": "192.0.2.0/24"},
    {"ip_address": "2001:db8::20", "network_cidr": "2001:db8::/64"},
]


def _fixture(name: str) -> dict[str, Any]:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _run_ansible(args: list[str]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    return subprocess.run(
        ["uv", "run", "ansible-playbook", *args],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_synthetic_present_and_absent_policy_fixtures_are_normalized_deterministically() -> None:
    present = _fixture("policy-present.yml")["vm_baseline_egress_policy"]
    first = normalize(present, NICS)
    second = normalize(present, list(reversed(NICS)))
    absent = normalize(_fixture("policy-absent.yml")["vm_baseline_egress_policy"], NICS)

    assert first == second
    assert first["apt_direct_hosts"] == ["packages.synthetic.invalid"]
    assert first["tool_bypass"] == [".svc.synthetic.invalid", "192.0.2.0/24", "192.0.2.20", "2001:db8::/64", "2001:db8::20"]
    assert first["sources"][0]["path"] == "/etc/apt/sources.list.d/vm-baseline-synthetic-repo.sources"
    assert first["keyrings"][0]["managed_path"] == "/etc/apt/keyrings/vm-baseline-synthetic-repo.gpg"
    assert absent["state"] == "absent"
    assert absent["sources"][0]["path"].startswith("/etc/apt/sources.list.d/vm-baseline-")


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda policy: policy.update(unexpected="value"), "unknown keys"),
        (lambda policy: policy.update(pve_nics=NICS), "unknown keys"),
        (lambda policy: policy.update(state="remove"), "state must be"),
        (lambda policy: policy["proxy"].update(endpoint="http://user:password@proxy.synthetic.invalid"), "must not contain credentials"),
        (lambda policy: policy["sources"][0].update(path="/etc/apt/sources.list.d/other.sources"), "unknown keys"),
        (lambda policy: policy["keyrings"][0].update(id="../../outside"), "identifier"),
    ],
)
def test_invalid_or_out_of_boundary_policy_is_rejected_before_host_mutation(mutator: Any, message: str) -> None:
    policy = _fixture("policy-present.yml")["vm_baseline_egress_policy"]
    mutator(policy)

    with pytest.raises(AnsibleFilterError, match=message):
        normalize(policy, NICS)


def test_omitted_fixture_is_empty_and_no_policy_path_keeps_existing_package_flow() -> None:
    assert _fixture("policy-omitted.yml") == {}
    tasks = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
    packages = (ROLE / "tasks" / "packages.yml").read_text(encoding="utf-8")

    assert "when: vm_baseline_egress_policy | length > 0" in tasks
    assert "ansible.builtin.apt:" in packages
    assert "vm_baseline_egress_apt_metadata_changed" in packages


def test_selected_missing_policy_fails_on_controller_before_the_synthetic_host_is_contacted(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        "all:\n  children:\n    pve_vms:\n      hosts:\n        synthetic-unreachable:\n          ansible_host: 192.0.2.250\n          ansible_connection: ssh\n",
        encoding="utf-8",
    )
    missing = tmp_path / "missing-policy.yml"

    result = _run_ansible(["-i", str(inventory), "-e", f"vm_baseline_egress_policy_file={missing}", str(PLAYBOOK)])

    assert result.returncode != 0
    assert "selected vm_baseline egress policy file is missing or unreadable" in result.stdout + result.stderr
    assert "UNREACHABLE" not in result.stdout + result.stderr


def test_role_orders_prechecks_before_guest_writes_and_preserves_guest_only_boundary() -> None:
    egress = (ROLE / "tasks" / "egress.yml").read_text(encoding="utf-8")
    present = (ROLE / "tasks" / "egress_present.yml").read_text(encoding="utf-8")
    absent = (ROLE / "tasks" / "egress_absent.yml").read_text(encoding="utf-8")
    role = "\n".join(path.read_text(encoding="utf-8") for path in ROLE.rglob("*.yml"))

    assert egress.index("Verify controller-side") < egress.index("Converge declared")
    assert egress.index("Require protected runtime") < egress.index("Converge declared")
    assert egress.index("exclusive policy mutation") < egress.index("Converge declared")
    assert present.index("APT keyrings") < present.index("custom CA") < present.index("deb822 APT sources") < present.index("APT proxy")
    assert "mode: \"0600\"" in present
    assert "no_log: true" in egress and "no_log: true" in present
    assert "vm_baseline_egress_model.sources" in absent
    assert "vm_baseline_egress_model.proxy_path" in absent
    for forbidden in ("nmcli", "ip route", "resolvectl", "iptables", "pvesh", "containerd", "k3s"):
        assert forbidden not in role


def test_bootstrap_syntax_and_disabled_tool_proxy_paths_are_valid() -> None:
    result = _run_ansible(["--syntax-check", "-i", str(ROOT / "tests/fixtures/environment/generated/ansible/pve.yml"), str(PLAYBOOK)])
    assert result.returncode == 0, result.stdout + result.stderr

    normalized = normalize(
        {
            "state": "present",
            "keyrings": [{"id": "repo", "kind": "role_managed", "artifact": "/synthetic/repo", "sha256": "c" * 64}],
            "sources": [{"id": "repo", "uri": "https://repo.synthetic.invalid", "suites": ["stable"], "components": ["main"], "keyring": "repo"}],
            "shell_proxy": {"enabled": False},
            "git_proxy": {"enabled": False},
        },
        NICS,
    )
    assert normalized["shell_proxy"] == {"enabled": False}
    assert normalized["git_proxy"] == {"enabled": False}
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "VM_BASELINE_EGRESS_POLICY" in makefile
    assert "ANSIBLE_LIMIT" in makefile
