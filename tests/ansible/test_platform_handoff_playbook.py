"""Static safety checks for the read-only platform handoff playbook."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "automation" / "ansible" / "playbooks" / "k3s" / "platform-handoff.yml"


def test_handoff_playbook_reads_authoritative_ca_and_never_mutates_cluster() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")
    document = yaml.safe_load(text)

    assert document[0]["hosts"] == "localhost"
    assert "/var/lib/rancher/k3s/server/tls/server-ca.crt" in text
    assert "ansible.builtin.slurp:" in text
    assert "exactly one X.509 CA certificate" in text
    assert "-verify_return_error" in text
    assert "platform_handoff_tls.verify_option" in text
    assert "sha256:" in text
    for forbidden in ("kubernetes.core.", "helm", "flux", "kubectl apply", "state: present"):
        assert forbidden not in text.lower()


def test_handoff_playbook_requires_explicit_inputs_before_guest_access() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")

    assert text.index("Require explicit handoff inputs") < text.index("Read the authoritative K3s server CA")
    assert "platform_handoff_scope" in text
    assert "platform_handoff_output" in text


def test_handoff_uses_only_the_authoritative_ca_path_for_its_fingerprint() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")

    assert "platform_handoff_ca_fingerprint_command" in text
    assert "--endpoint-fingerprint" not in text
    assert text.index("Read the authoritative K3s server CA") < text.index("Derive the authoritative server CA")
