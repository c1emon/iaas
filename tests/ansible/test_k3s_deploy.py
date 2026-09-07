"""Static contract coverage for ordered K3s deployment orchestration."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "automation" / "ansible" / "playbooks" / "k3s" / "deploy.yml"


def test_deployment_is_explicit_whole_cluster_and_ordered() -> None:
    source = PLAYBOOK.read_text(encoding="utf-8")

    assert "k3s_deploy_selected_scope | sort" in source
    assert "k3s_bootstrap_server" in source
    assert "k3s_additional_servers" in source
    assert "k3s_agents" in source
    assert source.index("Bootstrap the explicit") < source.index("Join additional") < source.index("Join agents")
    assert source.count("serial: 1") == 3
    assert source.count("any_errors_fatal: true") == 3


def test_only_ephemeral_active_secure_token_is_used_after_bootstrap() -> None:
    source = PLAYBOOK.read_text(encoding="utf-8")

    additional = source[source.index("Join additional"):source.index("Join agents")]
    agents = source[source.index("Join agents"):]
    assert "Read the active bootstrap secure token" in source
    assert "Compare active secure-token credential and optional CA hash" in source
    assert "k3s_deploy_active_token_read.content" in additional
    assert "k3s_deploy_active_token_read.content" in agents
    assert re.search(r"tokens_by_vm_ref\[inventory_hostname\]", additional) is None
    assert re.search(r"tokens_by_vm_ref\[inventory_hostname\]", agents) is None
    assert "active_secure_token" not in source
    assert source.count("no_log: true") >= 12


def test_deployment_reruns_preflight_before_mutation_and_never_puts_secret_in_inventory() -> None:
    source = PLAYBOOK.read_text(encoding="utf-8")

    assert source.index("Re-run read-only preflight") < source.index("Bootstrap the explicit")
    assert "import_playbook: preflight.yml" in source
    assert "k3s_deploy_runtime_secret_file" in source
    assert "k3s_deploy_active_secure_token" not in source
    assert "add_host:" in source
    inventory_section = source[source.index("Materialize ordered deployment groups"):source.index("Bootstrap the explicit")]
    assert "token" not in inventory_section.lower()
