"""Contract checks for the K3s operator-boundary documentation."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "k3s-automation.md"


def documentation() -> str:
    return DOC.read_text(encoding="utf-8")


def test_documentation_exists_and_describes_the_software_only_boundary() -> None:
    text = documentation()

    assert "software-only K3s automation foundation" in text
    assert "does not deploy K3s to Astra" in text
    assert "synthetic fixtures" in text.lower()
    assert "not" in text.lower()
    assert "production-ready" in text


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
        "K3s document declares K3s-owned intent only",
        "ansible_host",
        "node-network role",
    ):
        assert required in text


def test_documentation_covers_artifact_registry_proxy_and_separate_host_policy() -> None:
    text = documentation()

    for required in (
        "SHA-256 checksum",
        "same-path",
        "action-scoped proxy",
        "registries.yaml",
        "registry fallback/TLS",
        "service-proxy retirement",
        "fallback denial",
        "NO_PROXY",
        "APT sources",
        "global shell or Git proxy settings",
        "separate APT/shell/Git boundary",
        "does not run `apt update`",
    ):
        assert required in text


def test_documentation_covers_secret_snapshot_upgrade_and_cni_boundaries() -> None:
    text = documentation()

    for required in (
        "op://vault/item/field",
        "CLI arguments",
        "stable intent",
        "snapshot source",
        "snapshot.yml",
        "offline upgrade planner",
        "k3s-upgrade",
        "whole-cluster scope",
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
    assert "no K3s command surface for automatic" in text
    assert re.search(r"automatic\s+restore", lower)


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
    assert "no astra composition" in lower
    assert re.search(r"does not require PVE\s+apply", text)
