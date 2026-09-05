"""Static contract tests for the separate K3s server and agent service roles."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "automation" / "ansible"


def test_server_role_uses_a_config_file_not_secret_cli_arguments() -> None:
    tasks = (ANSIBLE / "roles" / "k3s_server" / "tasks" / "main.yml").read_text(encoding="utf-8")
    unit = (ANSIBLE / "roles" / "k3s_server" / "templates" / "k3s.service.j2").read_text(encoding="utf-8")

    assert "embedded-etcd" in tasks
    assert "ansible.builtin.systemd:" in tasks
    assert "--config /etc/rancher/k3s/config.yaml" in unit
    assert "token" not in unit


def test_agent_role_uses_a_config_file_not_secret_cli_arguments() -> None:
    tasks = (ANSIBLE / "roles" / "k3s_agent" / "tasks" / "main.yml").read_text(encoding="utf-8")
    unit = (ANSIBLE / "roles" / "k3s_agent" / "templates" / "k3s-agent.service.j2").read_text(encoding="utf-8")

    assert "k3s_agent_node.role" in tasks
    assert "ansible.builtin.systemd:" in tasks
    assert "--config /etc/rancher/k3s/config.yaml" in unit
    assert "token" not in unit


def test_runtime_config_keeps_join_token_root_only_and_redacted() -> None:
    tasks = (ANSIBLE / "roles" / "k3s_runtime_config" / "tasks" / "main.yml").read_text(encoding="utf-8")
    defaults = (ANSIBLE / "roles" / "k3s_runtime_config" / "defaults" / "main.yml").read_text(encoding="utf-8")
    template = (ANSIBLE / "roles" / "k3s_runtime_config" / "templates" / "config.yaml.j2").read_text(encoding="utf-8")

    assert "k3s_runtime_join_token" in defaults
    assert "token:" in template
    assert "mode: '0600'" in tasks
    assert "no_log: true" in tasks


def test_converged_service_units_do_not_force_a_restart() -> None:
    server = (ANSIBLE / "roles" / "k3s_server" / "tasks" / "main.yml").read_text(encoding="utf-8")
    agent = (ANSIBLE / "roles" / "k3s_agent" / "tasks" / "main.yml").read_text(encoding="utf-8")

    for source in (server, agent):
        assert "state: \"{{ 'restarted' if" in source
        assert "else 'started' }}\"" in source
        assert "daemon_reload: \"{{" in source
