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
INVENTORY_PATH = ROOT / "tests" / "fixtures" / "environment" / "inventory" / "foundation.yml"
GENERATED_DOCS_PATH = ROOT / "tests" / "fixtures" / "environment" / "generated" / "docs" / "foundation-recovery.md"


def _validated_model(doc: dict[str, object] | None = None) -> dict[str, object]:
    foundation_doc = load_yaml(INVENTORY_PATH) if doc is None else doc
    return build_model(validate_foundation_inventory(foundation_doc))


def test_valid_foundation_inventory_renders_expected_document() -> None:
    model = _validated_model()
    markdown = build_markdown(model)

    assert markdown == GENERATED_DOCS_PATH.read_text(encoding="utf-8")
    assert "1. opnsense" in markdown
    assert "6. external-databases" in markdown
    assert "| foundation-a | bare-metal | 192.0.2.15 | 203.0.113.15 | yes |" in markdown
    assert "| authentik | foundation-a | compose | important | no | - | no | internal-dns | https https://203.0.113.15 [200, 302, 401] | authentik-config; runbook: docs/operations/06-acceptance-and-recovery.md" in markdown
    assert "accepted single point of failure" in markdown
    assert "Declared storage access for this example's VM nodes" in markdown


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
        (("foundation_hosts", 0, "name"), "foundation-a", "duplicate host name foundation-a"),
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
    with pytest.raises(ValidationError, match="endpoint: must be inside subnet"):
        _validated_model(doc)

    secret_doc = copy.deepcopy(load_yaml(INVENTORY_PATH))
    secret_doc["foundation_services"][0]["break_glass"]["secret_ref"] = "plaintext-secret"
    with pytest.raises(ValidationError, match="sensitive keys must use an external secret reference"):
        validate_foundation_inventory(secret_doc)


def test_neutral_storage_is_optional_and_legacy_layout_stays_explicit() -> None:
    doc = load_yaml(INVENTORY_PATH)
    legacy = copy.deepcopy(doc)
    legacy["schema_version"] = 1
    legacy["k3s_storage_access"] = {"phase_1": legacy.pop("storage_access")}
    for network in legacy["storage_networks"]:
        network["truenas_endpoint"] = network.pop("endpoint")
    assert "Phase 1 node classes: vm" in build_markdown(_validated_model(legacy))
    doc.pop("storage_access")
    doc.pop("storage_networks")
    rendered = build_markdown(_validated_model(doc))
    assert "Storage-network facts" not in rendered
    assert "storage access" not in rendered


def test_probe_inputs_require_resolver_and_scope_ca_to_https() -> None:
    doc = load_yaml(INVENTORY_PATH)
    next(service for service in doc["foundation_services"] if service["health_check"]["type"] == "dns")["health_check"].pop("resolver")
    with pytest.raises(ValidationError, match="resolver"):
        _validated_model(doc)
    doc = load_yaml(INVENTORY_PATH)
    check = doc["foundation_services"][0]["health_check"]
    check.update(type="tcp", target="example.test:443", ca_file="private-ca.pem")
    with pytest.raises(ValidationError, match="only valid for HTTPS"):
        _validated_model(doc)


def test_ca_path_is_resolved_from_selected_inventory(monkeypatch, tmp_path):
    doc = load_yaml(INVENTORY_PATH)
    doc["foundation_services"][0]["health_check"].update(type="https", target="https://example.test", ca_file="trust/ca.pem")
    path = tmp_path / "foundation.yml"
    path.write_text(yaml.safe_dump(doc))
    def observe(model):
        assert model["foundation_services"][0]["health_check"]["ca_file"] == str(tmp_path / "trust/ca.pem")
        return []
    monkeypatch.setattr("iaas_automation.foundation_inventory.cli.run_health_checks", observe)
    assert foundation_main(["--inventory", str(path), "--health"]) == 0


@pytest.mark.parametrize("case", ["self", "cycle", "order", "closure", "ambiguous"])
def test_dependency_admission_rejects_invalid_graphs(case) -> None:
    doc = load_yaml(INVENTORY_PATH)
    services = doc["foundation_services"]
    if case == "self":
        services[0]["dependencies"] = [services[0]["name"]]
    elif case == "cycle":
        for service in services:
            service["required_before_k3s"] = False
            service.pop("restore_order", None)
        services[0]["dependencies"] = [services[1]["name"]]
        services[1]["dependencies"] = [services[0]["name"]]
    elif case == "order":
        services[0]["restore_order"], services[1]["restore_order"] = 2, 1
    elif case == "closure":
        services[0]["dependencies"] = [services[-1]["name"]]
    else:
        doc["foundation_hosts"][-1]["name"] = services[-1]["name"]
        services[-2]["host"] = services[-1]["name"]
    with pytest.raises(ValidationError):
        _validated_model(doc)


def test_recovery_order_comes_from_facts_not_yaml_order() -> None:
    doc = load_yaml(INVENTORY_PATH)
    before = _validated_model(doc)
    doc["foundation_services"].reverse()
    after = _validated_model(doc)
    assert before["recovery_order"] == after["recovery_order"]


@pytest.mark.parametrize("field,value", [("vlan_id", 4095), ("unexpected", True)])
def test_neutral_storage_rejects_invalid_fields(field, value) -> None:
    doc = load_yaml(INVENTORY_PATH)
    doc["storage_networks"][0][field] = value
    with pytest.raises(ValidationError):
        _validated_model(doc)


def test_neutral_storage_supports_optional_vlan_and_selected_node_classes() -> None:
    doc = load_yaml(INVENTORY_PATH)
    doc["storage_networks"][0].pop("vlan_id")
    doc["storage_access"]["node_classes"] = ["vm", "bare-metal"]
    assert _validated_model(doc)["storage_access"]["node_classes"] == ["vm", "bare-metal"]


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
