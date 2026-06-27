"""Focused tests for the service metadata inventory workflow."""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.pve_inventory.errors import ValidationError
from scripts.services_inventory.cli import main as services_main
from scripts.services_inventory.io import load_yaml
from scripts.services_inventory.model import build_model
from scripts.services_inventory.render import build_markdown
from scripts.services_inventory.validation import load_vm_names, validate_services


ROOT = Path(__file__).resolve().parents[2]
SERVICES_PATH = ROOT / "inventory" / "services.yml"
VMS_PATH = ROOT / "inventory" / "vms.yml"
GENERATED_DOCS_PATH = ROOT / "docs" / "generated" / "services.md"
MAKEFILE_PATH = ROOT / "Makefile"


def _validated_model(doc: dict[str, object] | None = None) -> dict[str, object]:
    services_doc = load_yaml(SERVICES_PATH) if doc is None else doc
    vm_names = load_vm_names(load_yaml(VMS_PATH))
    services, warnings = validate_services(services_doc, vm_names)
    return build_model(services, warnings)


def test_valid_service_metadata_with_multiple_endpoints_renders_expected_rows_and_warnings() -> None:
    model = _validated_model()
    markdown = build_markdown(model)

    assert markdown == GENERATED_DOCS_PATH.read_text(encoding="utf-8")
    assert "| dev-dashboard | dev-web-01 | web | dashboard.dev.example.invalid | http | 8080 | lan | app | dns: manual; reverse proxy: future; opnsense: review-before-public |" in markdown
    assert "| prod-api | prod-app-01 | grpc | grpc.example.invalid | grpc | 8443 | vpn | sso | reverse proxy: future |" in markdown
    assert "## Warnings" in markdown
    assert "| prod-api | api | public-exposure | public exposure requires operator review |" in markdown


def test_optional_endpoint_name_is_rendered_as_a_placeholder() -> None:
    doc = copy.deepcopy(load_yaml(SERVICES_PATH))
    doc["services"][0]["endpoints"][0].pop("name", None)

    model = _validated_model(doc)
    markdown = build_markdown(model)

    assert "| dev-dashboard | dev-web-01 | - | dashboard.dev.example.invalid | http | 8080 | lan | app |" in markdown


@pytest.mark.parametrize(
    ("field_path", "value", "message"),
    [
        (("services", 0, "owner_vm"), "missing-vm", "owner_vm missing-vm is not declared in inventory/vms.yml"),
        (("services", 0, "endpoints", 0, "port"), 70000, "port: must be within 1-65535"),
        (("services", 0, "endpoints", 0, "protocol"), "HTTP", "protocol: must be lower-case"),
        (("services", 0, "endpoints", 0, "protocol"), "smtpx", "unsupported value smtpx"),
        (("services", 0, "endpoints", 0, "exposure"), "dmz", "unsupported value dmz"),
        (("services", 0, "endpoints", 0, "auth"), "oauth", "unsupported value oauth"),
    ],
)
def test_validation_rejects_invalid_owner_vm_port_protocol_exposure_and_auth(field_path: tuple[object, ...], value: object, message: str) -> None:
    doc = copy.deepcopy(load_yaml(SERVICES_PATH))
    target = doc
    for part in field_path[:-1]:
        target = target[part]  # type: ignore[index]
    target[field_path[-1]] = value  # type: ignore[index]

    with pytest.raises(ValidationError, match=message):
        _validated_model(doc)


def test_validation_rejects_duplicate_service_names_and_empty_endpoint_lists() -> None:
    duplicate_doc = copy.deepcopy(load_yaml(SERVICES_PATH))
    duplicate_doc["services"][1]["name"] = duplicate_doc["services"][0]["name"]
    with pytest.raises(ValidationError, match="duplicate service name dev-dashboard"):
        _validated_model(duplicate_doc)

    empty_doc = copy.deepcopy(load_yaml(SERVICES_PATH))
    empty_doc["services"][0]["endpoints"] = []
    with pytest.raises(ValidationError, match="endpoints must not be empty"):
        _validated_model(empty_doc)


def test_validation_rejects_duplicate_endpoint_names_within_a_service() -> None:
    doc = copy.deepcopy(load_yaml(SERVICES_PATH))
    doc["services"][0]["endpoints"].append(copy.deepcopy(doc["services"][0]["endpoints"][0]))

    with pytest.raises(ValidationError, match="duplicate endpoint name web"):
        _validated_model(doc)


def test_warning_generation_is_deterministic_and_ordered() -> None:
    doc = copy.deepcopy(load_yaml(SERVICES_PATH))
    doc["services"] = [
        {
            "name": "warning-service",
            "owner_vm": "prod-app-01",
            "endpoints": [
                {
                    "name": "public",
                    "port": 443,
                    "protocol": "https",
                    "exposure": "public",
                    "auth": "none",
                },
                {
                    "name": "vpn",
                    "port": 8443,
                    "protocol": "https",
                    "exposure": "vpn",
                    "auth": "unknown",
                },
            ],
        }
    ]

    model = _validated_model(doc)
    assert model["warnings"] == [
        {"service": "warning-service", "endpoint": "public", "code": "missing-fqdn", "message": "non-internal endpoint lacks fqdn"},
        {"service": "warning-service", "endpoint": "public", "code": "public-exposure", "message": "public exposure requires operator review"},
        {"service": "warning-service", "endpoint": "public", "code": "public-unauthenticated", "message": "public exposure with auth none"},
        {"service": "warning-service", "endpoint": "vpn", "code": "missing-fqdn", "message": "non-internal endpoint lacks fqdn"},
        {"service": "warning-service", "endpoint": "vpn", "code": "auth-unknown", "message": "auth unknown needs review"},
    ]


def test_service_docs_stale_check_is_offline_and_participates_in_root_targets(tmp_path: Path) -> None:
    services_copy = tmp_path / "services.yml"
    services_copy.write_text(SERVICES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    vms_copy = tmp_path / "vms.yml"
    vms_copy.write_text(VMS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    docs_copy = tmp_path / "services.md"
    docs_copy.write_text("stale\n", encoding="utf-8")

    with pytest.raises(ValidationError, match=f"stale: {docs_copy}"):
        services_main(["--services", str(services_copy), "--vms", str(vms_copy), "--docs", str(docs_copy), "--check"])

    makefile_text = MAKEFILE_PATH.read_text(encoding="utf-8")
    assert "services-generate:" in makefile_text
    assert "services-check:" in makefile_text
    assert "$(MAKE) services-generate" in makefile_text
    assert "$(MAKE) services-check" in makefile_text


def test_services_cli_validation_failure_exits_1_without_traceback(tmp_path: Path) -> None:
    services_copy = tmp_path / "services.yml"
    doc = copy.deepcopy(load_yaml(SERVICES_PATH))
    doc["services"][0]["owner_vm"] = "missing-vm"
    services_copy.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "scripts.services_inventory.cli", "--services", str(services_copy)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("FAIL validation: ")
    assert "Traceback (most recent call last):" not in result.stderr
