"""The checked-in synthetic PVE lifecycle root stays contract-valid."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_config import SourceReader
from iaas_automation.runtime_config.compile import compile_documents
from iaas_automation.runtime_execution.pve_contracts import validate_result
from iaas_automation.runtime_execution.pve_provider import validate_root
from iaas_automation.runtime_execution.root import materialize_root
from iaas_automation.runtime_execution.selection import load_operation


ROOT = Path(__file__).resolve().parents[2] / "docs/examples/pve-lifecycle"


def test_synthetic_pve_vm_root_and_lifecycle_files() -> None:
    entry = ROOT / "environment.yml"
    selected = load_operation(entry, "pve", "plan", None, SourceReader())
    assert "execution_result" not in selected.files
    assert set(compile_documents(selected)) == {"pve.tfvars.json", "pve-inventory.yml", "pve.md"}
    binding = validate_root(ROOT / "root", {**selected.options["pve"], "root_id": "synthetic-root"})
    assert binding["provider"] == "proxmox"
    assert binding["ssh_nodes"] == [{"name": "synthetic-node", "host": "synthetic-node.example.invalid", "port": 2222}]
    with TemporaryDirectory() as directory:
        materialized = materialize_root(selected.options["root"], selected.files, Path(directory) / "workspace")
        assert materialized == Path(directory) / "workspace"
        assert validate_root(materialized, {**selected.options["pve"], "root_id": "synthetic-root"}) == binding
    assert set(load_operation(entry, "pve", "read", None, SourceReader()).files) == {"backend", "execution_result"}
    assert set(load_operation(entry, "pve", "verify", None, SourceReader()).files) == {"execution_result"}
    result = json.loads((ROOT / "execution-result.json").read_text())
    assert validate_result(result)["snapshot"]["lineage"] == "synthetic-lineage"


def test_synthetic_delete_root_and_independent_template_contracts() -> None:
    delete = load_operation(ROOT / "environment-delete.yml", "pve", "plan", None, SourceReader())
    assert delete.options["destroy"] is True
    with pytest.raises(ValidationError, match="unsupported pve-template input"):
        load_operation(ROOT / "environment-template.yml", "pve-template", "plan", None, SourceReader())


def test_template_read_apply_cleanup_entries_and_cli_discovery() -> None:
    with pytest.raises(ValidationError, match="unsupported pve-template input"):
        load_operation(ROOT / "environment-template-read.yml", "pve-template", "read", None, SourceReader())
    with pytest.raises(ValidationError, match="unsupported pve-template input"):
        load_operation(ROOT / "environment-template-apply.yml", "pve-template", "apply", None, SourceReader())
