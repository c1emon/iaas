"""Static and synthetic offline coverage for the K3s prerequisite role."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
ROLE = ANSIBLE_DIR / "roles" / "k3s_prerequisites"
DEFAULTS = ROLE / "defaults" / "main.yml"
TASKS = ROLE / "tasks" / "main.yml"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    return subprocess.run(
        ["uv", "run", "ansible-playbook", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _synthetic_playbook(
    path: Path, *, distribution: str = "Debian", packages: list[str] | None = None
) -> None:
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Synthetic K3s prerequisite role test",
                    "hosts": "all",
                    "gather_facts": False,
                    "vars": {
                        "ansible_facts": {
                            "os_family": "Debian",
                            "distribution": distribution,
                            "pkg_mgr": "apt",
                        },
                        **({"k3s_prerequisites_packages": packages} if packages is not None else {}),
                    },
                    "roles": ["k3s_prerequisites"],
                }
            ],
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_role_has_explicit_debian_k3s_package_contract() -> None:
    defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    assert defaults["k3s_prerequisites_packages"] == [
        "ca-certificates",
        "conntrack",
        "iptables",
        "socat",
    ]


def test_role_is_separate_and_does_not_manage_generic_host_policy() -> None:
    assert ROLE.name == "k3s_prerequisites"
    source = "\n".join(path.read_text(encoding="utf-8") for path in ROLE.rglob("*.yml"))
    assert "vm_baseline" not in source
    assert "update_cache: false" in source
    for forbidden in ("sources.list", "apt_proxy", "http_proxy", "https_proxy", "git config", "shell:"):
        assert forbidden not in source
    assert "ansible.builtin.apt:" in source
    assert "state: present" in source


def test_role_syntax_check_passes(tmp_path: Path) -> None:
    playbook = tmp_path / "synthetic.yml"
    _synthetic_playbook(playbook, packages=[])
    result = _run(["--syntax-check", "-i", "localhost,", str(playbook)])
    assert result.returncode == 0, result.stdout + result.stderr


def test_synthetic_debian_check_mode_is_convergent_without_host_mutation(tmp_path: Path) -> None:
    playbook = tmp_path / "synthetic.yml"
    _synthetic_playbook(playbook, packages=[])
    result = _run(["--check", "-i", "localhost,", "-e", "ansible_connection=local", str(playbook)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Install declared Debian K3s host prerequisites" in result.stdout


def test_non_debian_synthetic_host_fails_closed_before_package_task(tmp_path: Path) -> None:
    playbook = tmp_path / "synthetic.yml"
    _synthetic_playbook(playbook, distribution="Ubuntu")
    result = _run(["--check", "-i", "localhost,", "-e", "ansible_connection=local", str(playbook)])
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "supports Debian hosts managed by APT only" in output
    assert "Install declared Debian K3s host prerequisites" not in output
