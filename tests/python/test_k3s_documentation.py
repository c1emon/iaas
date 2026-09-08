"""Contract checks for the authoritative K3s operations chapter."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "operations" / "05-k3s.md"


def documentation() -> str:
    return DOC.read_text(encoding="utf-8")


def test_documentation_exists_and_describes_the_software_only_boundary() -> None:
    text = documentation()

    assert "当前状态与准入" in text
    assert "调用方环境的 K3s VM/inventory/intent" in text
    assert "synthetic" in text.lower()
    assert "生产资格" in text


def test_documentation_covers_source_handoff_and_composed_facts() -> None:
    text = documentation()

    for required in (
        "pve-cluster.yml",
        "vms.yml",
        "generated OpenTofu",
        "generated Ansible inventory",
        "cloud-init",
        "vm_baseline",
        "pve_architecture",
        "ansible_host",
        "node_network_role",
    ):
        assert required in text


def test_documentation_covers_artifact_registry_proxy_and_separate_host_policy() -> None:
    text = documentation()

    for required in (
        "SHA-256 checksum",
        "registries.yaml",
        "fallback",
        "NO_PROXY",
        "APT/Shell/Git",
        "runtime JSON",
    ):
        assert required in text


def test_documentation_covers_secret_snapshot_upgrade_and_cni_boundaries() -> None:
    text = documentation()

    for required in (
        "op://vault/item/field",
        "snapshot source",
        "upgrade plan",
        "k3s-upgrade",
        "CNI-not-initialized",
        "Cilium",
    ):
        assert required in text


def test_documentation_exposes_safety_classes_but_no_destructive_k3s_commands() -> None:
    text = documentation()
    lower = text.lower()

    for command in (
        "make k3s-check",
        "make k3s-render",
        "make k3s-ansible-syntax",
        "make k3s-preflight",
        "make k3s-verify",
        "make k3s-deploy",
        "make k3s-snapshot",
        "make k3s-upgrade",
        "make check",
    ):
        assert command in lower

    # Prose may name the excluded operation, but no executable command line may
    # accidentally become an operator recipe for a destructive K3s action.
    destructive_command = re.compile(
        r"(?:^|\s)(?:make\s+)?k3s(?:[-_ ]+(?:restore|uninstall|destroy|remove|delete))\b",
        re.IGNORECASE,
    )
    assert destructive_command.search(text) is None
    assert "没有自动" in text
    assert "restore" in lower


def test_documentation_does_not_claim_live_astra_nodes_or_cluster_qualification() -> None:
    text = documentation()
    lower = text.lower()

    forbidden_claims = (
        "astra k3s nodes are deployed",
        "astra cluster is running",
        "live-qualified",
        "production qualification passed",
        "highly available cluster",
    )
    assert all(claim not in lower for claim in forbidden_claims)
    assert "调用方环境的 k3s vm/inventory/intent" in lower
    assert "Astra 已" not in text
