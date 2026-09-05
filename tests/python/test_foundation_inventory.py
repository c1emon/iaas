"""Focused tests for the foundation recovery inventory workflow."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.common.io import load_yaml
from iaas_automation.foundation_inventory.cli import main as foundation_main
from iaas_automation.foundation_inventory.health import ProbeOutcome, run_health_checks
from iaas_automation.foundation_inventory.model import build_model
from iaas_automation.foundation_inventory.render import build_markdown
from iaas_automation.foundation_inventory.validation import validate_foundation_inventory
from iaas_automation.pve_inventory.checks.results import render_report


ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "environments" / "astra" / "inventory" / "foundation.yml"
GENERATED_DOCS_PATH = ROOT / "environments" / "astra" / "generated" / "docs" / "foundation-recovery.md"


def _validated_model(doc: dict[str, object] | None = None) -> dict[str, object]:
    foundation_doc = load_yaml(INVENTORY_PATH) if doc is None else doc
    return build_model(validate_foundation_inventory(foundation_doc))


def test_valid_foundation_inventory_renders_expected_document() -> None:
    model = _validated_model()
    markdown = build_markdown(model)

    assert markdown == GENERATED_DOCS_PATH.read_text(encoding="utf-8")
    assert "1. opnsense" in markdown
    assert "6. external-databases" in markdown
    assert "| n100 | bare-metal | 10.1.0.15 | 10.50.0.15 | yes |" in markdown
    assert "| authentik | n100 | compose | important | no | - | no | internal-dns | https https://10.50.0.15 [200, 302, 401] | authentik-config; runbook: docs/operations/06-acceptance-and-recovery.md" in markdown
    assert "accepted single point of failure" in markdown
    assert "Only VM-based K3s nodes may access the storage VLAN" in markdown


def test_markdown_renderer_escapes_table_sensitive_content_and_remains_non_sensitive() -> None:
    doc = copy.deepcopy(load_yaml(INVENTORY_PATH))
    doc["foundation_hosts"][0]["notes"] = "alpha | beta\nline"
    doc["foundation_services"][0]["notes"] = "pipe | line\nsecond"

    markdown = build_markdown(_validated_model(doc))

    assert "alpha \\| beta<br>line" in markdown
    assert "pipe \\| line<br>second" in markdown
    assert "-----BEGIN" not in markdown
    assert "AKIA" not in markdown
    assert "password" not in markdown.lower()


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("foundation_hosts", 0, "name"), "n100", "duplicate host name n100"),
        (("foundation_services", 1, "host"), "missing-host", "unknown host ref missing-host"),
        (("foundation_services", 4, "dependencies"), ["missing-service"], "unknown dependency ref missing-service"),
        (("foundation_services", 2, "restore_order"), None, "restore_order: must be a positive integer"),
        (("foundation_services", 4, "restore_order"), 3, "duplicate restore_order 3"),
        (("foundation_services", 0, "backup_restore"), None, "critical or required-before-K3s services must declare backup/restore metadata"),
    ],
)
def test_validation_rejects_duplicates_unknown_refs_restore_order_and_missing_metadata(path: tuple[object, ...], value: object, message: str) -> None:
    doc = copy.deepcopy(load_yaml(INVENTORY_PATH))
    target = doc
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    if value is None:
        target.pop(path[-1], None)  # type: ignore[index]
    else:
        target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ValidationError, match=message):
        _validated_model(doc)


def test_validation_rejects_inconsistent_storage_facts_and_secret_like_values() -> None:
    doc = copy.deepcopy(load_yaml(INVENTORY_PATH))
    doc["storage_networks"][0]["subnet"] = "10.34.0.0/24"
    with pytest.raises(ValidationError, match="truenas_endpoint: must be inside subnet"):
        _validated_model(doc)

    secret_doc = copy.deepcopy(load_yaml(INVENTORY_PATH))
    secret_doc["foundation_services"][0]["break_glass"]["secret_ref"] = "plaintext-secret"
    with pytest.raises(ValidationError, match="sensitive keys must use an external secret reference"):
        validate_foundation_inventory(secret_doc)


def test_health_classification_uses_fake_probes_and_render_report() -> None:
    model = _validated_model()
    # Probe functions are injected so the test exercises result mapping only.
    results = run_health_checks(
        model,
        probe_dispatch={
            "http": lambda check: ProbeOutcome("passed", f"fake {check['target']}") ,
            "https": lambda check: ProbeOutcome("passed", f"fake {check['target']}") ,
            "api": lambda check: ProbeOutcome("failed", "fake api failure"),
            "dns": lambda check: ProbeOutcome("unreachable", "fake dns timeout"),
            "tcp": lambda check: ProbeOutcome("skipped", "fake skip"),
        },
    )

    assert [result.severity for result in results] == ["PASS", "FAIL", "FAIL", "SKIP", "PASS", "SKIP", "PASS"]
    assert any(result.message.startswith("passed: opnsense") for result in results)
    assert any(result.message.startswith("failed: truenas") for result in results)
    assert any(result.message.startswith("unreachable: internal-dns") for result in results)
    assert any(result.message.startswith("skipped: sing-box") for result in results)
    report = render_report(results)
    assert "summary:" in report


def test_offline_check_mode_does_not_run_health(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    inventory_copy = tmp_path / "foundation.yml"
    inventory_copy.write_text(INVENTORY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    docs_copy = tmp_path / "foundation-recovery.md"
    docs_copy.write_text(GENERATED_DOCS_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    def _boom(*_args: object, **_kwargs: object) -> list[object]:
        raise AssertionError("health should not run in offline check mode")

    # Offline check mode should never touch the live health path.
    monkeypatch.setattr("iaas_automation.foundation_inventory.cli.run_health_checks", _boom)
    assert foundation_main(["--inventory", str(inventory_copy), "--docs", str(docs_copy), "--check"]) == 0


def test_foundation_cli_validation_failure_exits_1_without_traceback(tmp_path: Path) -> None:
    inventory_copy = tmp_path / "foundation.yml"
    doc = copy.deepcopy(load_yaml(INVENTORY_PATH))
    doc["foundation_hosts"][0]["name"] = "broken host"
    inventory_copy.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "iaas_automation.foundation_inventory.cli", "--inventory", str(inventory_copy)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ | {"PYTHONPATH": str(ROOT / "automation" / "src")},
    )

    assert result.returncode == 1
    assert result.stderr.startswith("FAIL validation: ")
    assert "Traceback (most recent call last):" not in result.stderr
