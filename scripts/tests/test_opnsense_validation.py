from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
import yaml

from scripts.common.errors import ValidationError
from scripts.opnsense_validation import RESOURCE_PATHS, validate_all, validate_document


def _document(resource: str) -> dict[str, Any]:
    return yaml.safe_load(RESOURCE_PATHS[resource].read_text(encoding="utf-8"))


def test_committed_supported_desired_state_passes_without_rewrite() -> None:
    validate_all()


@pytest.mark.parametrize(
    ("resource", "mutate", "match"),
    [
        ("aliases", lambda document: document["opnsense_aliases"][0].update({"unexpected": True}), "unknown keys"),
        ("aliases", lambda document: document["opnsense_aliases"][0].update({"enabled": "true"}), "enabled: must be a boolean"),
        ("vips", lambda document: document["opnsense_vips"][0].update({"address": "10.1.0.253"}), "address: must be an IP address with prefix"),
        ("vips", lambda document: document["opnsense_vips"].append(deepcopy(document["opnsense_vips"][0])), "duplicate managed identity"),
        ("gateways", lambda document: document["opnsense_gateways"][0].update({"default_gw": True}), "default_gw: must be false"),
        ("gateways", lambda document: document["opnsense_gateways"][0].update({"priority": 256}), "priority: must be within 1..255"),
        ("gateways", lambda document: document["opnsense_gateways"][0].update({"latency_low": 501}), "latency_low must not exceed"),
        ("filter-rules", lambda document: document["opnsense_filter_rules"][0].update({"description": "manual"}), "description: is generated"),
        ("filter-rules", lambda document: document["opnsense_filter_rules"][0].update({"destination_port": "70000"}), "destination_port: must be within 1..65535"),
        ("filter-rules", lambda document: document["opnsense_filter_rules"][3].update({"destination_net": ["opt8"]}), "deny rule must not include"),
    ],
)
def test_invalid_resource_values_fail_with_field_paths(
    resource: str, mutate: Callable[[dict[str, Any]], None], match: str
) -> None:
    document = _document(resource)
    mutate(document)
    with pytest.raises(ValidationError, match=match):
        validate_document(resource, document)


def test_invalid_document_shape_fails_closed() -> None:
    with pytest.raises(ValidationError, match="must contain only opnsense_aliases"):
        validate_document("aliases", {"opnsense_aliases": [], "other": []})
    with pytest.raises(ValidationError, match="opnsense_aliases: must be a list"):
        validate_document("aliases", {"opnsense_aliases": {}})


def test_cli_reports_expected_error_without_traceback_or_payload(tmp_path: Path) -> None:
    path = tmp_path / "aliases.yml"
    path.write_text("opnsense_aliases:\n  - name: secret-value\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.opnsense_validation", "--resource", "aliases", "--file", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "opnsense validation failed: opnsense_aliases[0]" in result.stderr
    assert "Traceback" not in result.stderr
    assert "secret-value" not in result.stderr
