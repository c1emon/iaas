"""The checked-in synthetic PVE lifecycle root stays contract-valid."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from iaas_automation.pve_template.contracts import (validate_preview, validate_recipe,
                                                     validate_cleanup_preview,
                                                     validate_request, validate_template_record)
from iaas_automation.runtime_execution.__main__ import main
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
    assert set(compile_documents(selected)) == {"pve.tfvars.json", "pve-inventory.yml", "pve.md", "template-build.env"}
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
    template = load_operation(ROOT / "environment-template.yml", "pve-template", "plan", None, SourceReader())
    assert validate_recipe(template.documents["recipe"])["target"]["node"] == "synthetic-node"
    template_read = load_operation(ROOT / "environment-template.yml", "pve-template", "read", None, SourceReader())
    assert {"ssh_key", "known_hosts"} <= set(template_read.files)
    template_verify = load_operation(ROOT / "environment-template.yml", "pve-template", "verify", None, SourceReader())
    assert {"ssh_key", "known_hosts"} <= set(template_verify.files)
    preview = validate_preview(json.loads((ROOT / "template/template-preview.json").read_text()))
    receipt = json.loads((ROOT / "template/template-receipt.json").read_text())
    records = json.loads((ROOT / "template-records.json").read_text())
    assert validate_template_record(records["records"][0])["object"]["smbios_uuid"]
    assert receipt["kind"] == "pve-template-receipt"
    assert receipt["preview_digest"] == preview["preview_digest"].removeprefix("sha256:")


def test_template_read_apply_cleanup_entries_and_cli_discovery() -> None:
    read = load_operation(ROOT / "environment-template-read.yml", "pve-template", "read", None, SourceReader())
    assert {"execution_result", "ssh_key", "known_hosts"} <= set(read.files)
    apply = load_operation(ROOT / "environment-template-apply.yml", "pve-template", "apply", None, SourceReader())
    assert {"template_preview", "execution_admission", "ssh_key", "known_hosts"} <= set(apply.files)
    apply_preview = validate_preview(json.loads((ROOT / "template/template-preview.json").read_text()))
    assert apply.options["preview_digest"] == apply_preview["preview_digest"]
    cleanup_plan = load_operation(ROOT / "environment-template-cleanup.yml", "pve-template", "plan", None, SourceReader())
    assert cleanup_plan.options["action"] == "cleanup"
    cleanup_apply = load_operation(ROOT / "environment-template-cleanup-apply.yml", "pve-template", "apply", None, SourceReader())
    assert {"template_preview", "execution_admission", "ssh_key", "known_hosts"} <= set(cleanup_apply.files)
    cleanup_preview = json.loads((ROOT / "template-cleanup-preview.json").read_text())
    cleanup_admission = json.loads((ROOT / "template-cleanup-admission.json").read_text())
    assert validate_cleanup_preview(cleanup_preview)["preview_digest"] == cleanup_admission["plan_digest"]
    request = validate_request({"protocol_version": 2, "operation": "cleanup",
                                "execution_id": cleanup_admission["execution_id"],
                                "recovery_of": cleanup_preview["original_execution"],
                                "cleanup": {**cleanup_preview, "management_status": "stopped"},
                                "admission": cleanup_admission})
    assert request["cleanup"]["object"]["vmid"] == cleanup_preview["vmid"]
    assert main(["--environment", str(ROOT / "environment-template-cleanup.yml"),
                 "--component", "pve-template", "--operation", "plan", "--scope", "synthetic-node",
                 "--discover"]) == 0
    assert main(["--environment", str(ROOT / "environment-template-apply.yml"),
                 "--component", "pve-template", "--operation", "apply", "--scope", "synthetic-node",
                 "--execution-id", "template-synthetic-apply-001", "--discover"]) == 0
