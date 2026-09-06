"""Synthetic contract tests for the external GitOps handoff boundary."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.common.io import load_yaml
from iaas_automation.k3s_automation.config import build_composed_model
from iaas_automation.platform_handoff.cli import main
from iaas_automation.platform_handoff.config import attach_ca_fingerprint, build_handoff, render_bundle


ROOT = Path(__file__).resolve().parents[2]
K3S_FIXTURES = ROOT / "tests" / "fixtures" / "k3s"
FIXTURES = ROOT / "tests" / "fixtures" / "platform_handoff"
SCOPE = "synthetic-server-01,synthetic-server-02,synthetic-server-03,synthetic-agent-01"
FINGERPRINT = "sha256:" + "d" * 64


def documents() -> tuple[dict[str, Any], dict[str, Any]]:
    model = build_composed_model(
        copy.deepcopy(load_yaml(K3S_FIXTURES / "intent.yml")),
        copy.deepcopy(load_yaml(K3S_FIXTURES / "generated-pve.yml")),
    )
    return copy.deepcopy(load_yaml(FIXTURES / "intent.yml")), model


def test_handoff_is_deterministic_and_contains_only_contract_fields() -> None:
    intent, model = documents()

    rendered = render_bundle(attach_ca_fingerprint(build_handoff(intent, model, SCOPE), FINGERPRINT))

    assert rendered == (FIXTURES / "expected-bundle.yml").read_text(encoding="utf-8")
    assert "synthetic-server-01" not in rendered
    assert "op://synthetic/platform/bootstrap-grant" in rendered
    assert "not-qualified" in rendered


@pytest.mark.parametrize("address", ["api.synthetic.invalid", "203.0.113.10", "2001:db8::10"])
def test_api_endpoint_is_normalized_with_required_port(address: str) -> None:
    intent, model = documents()
    model["cluster"]["api_endpoint"]["address"] = address

    endpoint = build_handoff(intent, model, SCOPE)["cluster"]["api_endpoint"]

    expected_host = f"[{address}]" if ":" in address else address
    assert endpoint == f"https://{expected_host}:6443"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda intent: intent["platform"]["repository"].update(url="http://git.synthetic.invalid/repo.git"),
        lambda intent: intent["platform"]["repository"].update(url="https://token@git.synthetic.invalid/repo.git"),
        lambda intent: intent["platform"]["repository"].update(url="https://git.synthetic.invalid/repo.git?token=value"),
        lambda intent: intent["platform"]["repository"].update(path="../unsafe"),
        lambda intent: intent["platform"].update(bootstrap_credential_ref="plaintext-secret"),
        lambda intent: intent["platform"].update(node_address="198.51.100.11"),
    ],
)
def test_handoff_rejects_untrusted_or_copied_input(mutate: Any) -> None:
    intent, model = documents()
    mutate(intent)

    with pytest.raises(ValidationError):
        build_handoff(intent, model, SCOPE)


def test_handoff_rejects_partial_scope_before_rendering() -> None:
    intent, model = documents()

    with pytest.raises(ValidationError, match="whole cluster"):
        build_handoff(intent, model, "synthetic-server-01")


def test_render_requires_authoritative_ca_identity_and_protects_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "operator" / "handoff.yml"

    result = main([
        "--intent", str(K3S_FIXTURES / "intent.yml"), "--inventory", str(K3S_FIXTURES / "generated-pve.yml"),
        "--handoff-intent", str(FIXTURES / "intent.yml"), "--scope", SCOPE,
        "--render", str(output), "--ca-fingerprint", FINGERPRINT,
    ])

    assert result == 0
    assert oct(output.stat().st_mode & 0o777) == "0o600"
    stdout = capsys.readouterr().out
    assert "Platform handoff bundle rendered:" in stdout
    assert "bootstrap-grant" not in stdout


def test_render_rejects_repository_owned_output_path() -> None:
    with pytest.raises(ValidationError, match="repository-owned"):
        main([
            "--intent", str(K3S_FIXTURES / "intent.yml"), "--inventory", str(K3S_FIXTURES / "generated-pve.yml"),
            "--handoff-intent", str(FIXTURES / "intent.yml"), "--scope", SCOPE,
            "--render", str(ROOT / ".cache" / "handoff.yml"), "--ca-fingerprint", FINGERPRINT,
        ])


def test_render_does_not_require_or_resolve_a_secret_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: pytest.fail("unexpected external command"))
    output = tmp_path / "handoff.yml"

    main([
        "--intent", str(K3S_FIXTURES / "intent.yml"), "--inventory", str(K3S_FIXTURES / "generated-pve.yml"),
        "--handoff-intent", str(FIXTURES / "intent.yml"), "--scope", SCOPE,
        "--render", str(output), "--ca-fingerprint", FINGERPRINT,
    ])

    assert "bootstrap-grant" in output.read_text(encoding="utf-8")
