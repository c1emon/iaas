"""Static contract coverage for pinned K3s executable acquisition."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "automation" / "ansible" / "roles" / "k3s_acquisition" / "tasks" / "main.yml"


def test_acquisition_is_pinned_to_the_composed_architecture_and_checksum() -> None:
    source = ROLE.read_text(encoding="utf-8")

    assert "k3s_acquisition_model_node.architecture" in source
    assert "k3s_acquisition_cluster.artifacts" in source
    assert "ansible.builtin.get_url:" in source
    assert "checksum: \"sha256:" in source
    assert "no_log: true" in source
    assert "get.k3s.io" not in source
    assert "shell:" not in source
    assert "command:" not in source


def test_acquisition_uses_only_an_action_scoped_proxy_environment() -> None:
    source = ROLE.read_text(encoding="utf-8")

    assert "k3s_acquisition_runtime_proxy" in source
    assert "/etc/apt" not in source
    assert "git config" not in source
    assert "environment:" in source
