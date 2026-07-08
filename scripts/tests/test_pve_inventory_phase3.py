"""Focused Phase 3 tests for PVE template build parameterization."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shlex
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.pve_inventory.cloud_init import main as cloud_init_main
from scripts.pve_inventory.cloud_init_helpers.artifacts import load_rendered_artifacts, write_rendered_artifacts
from scripts.pve_inventory.cloud_init_helpers.model import CloudInitSnippet
from scripts.pve_inventory.cloud_init_helpers.render import render_snippets
from scripts.pve_inventory.cloud_init_helpers import ssh as cloud_init_ssh
from scripts.common.io import load_yaml
from scripts.pve_inventory.checks.preflight.model import derive_expected_resources
from scripts.pve_inventory.inventory.model import build_model
from scripts.pve_inventory.inventory.render import render_outputs
from scripts.pve_inventory.inventory.validation.cluster import validate_cluster
from scripts.pve_inventory.inventory.validation.vm import validate_vms
from scripts.common.errors import ValidationError


ROOT = Path(__file__).resolve().parents[2]
CLUSTER_PATH = ROOT / "inventory" / "pve-cluster.yml"
VMS_PATH = ROOT / "inventory" / "vms.yml"


def cluster_state() -> dict[str, Any]:
    return validate_cluster(load_yaml(CLUSTER_PATH))


def vms_model() -> dict[str, Any]:
    cluster = cluster_state()
    return build_model(cluster, validate_vms(load_yaml(VMS_PATH), cluster))


def explicit_multi_nic_doc() -> dict[str, Any]:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    vm = doc["vms"][2]
    vm["nics"] = [
        {
            "name": "mgmt0",
            "role": "management",
            "network": "dev",
            "macaddr": "52:54:00:10:00:01",
            "static_ip": "10.10.0.21/24",
            "ansible_connection": True,
        },
        {
            "name": "cluster0",
            "role": "cluster",
            "network": "prod",
            "mac_address": "52:54:00:10:00:02",
            "static_ip": "10.50.0.22/24",
            "gateway": "10.50.0.254",
            "default_route": True,
            "dns": ["10.50.0.254"],
        },
    ]
    for field in ("network", "static_ip", "gateway", "dns"):
        vm.pop(field, None)
    return doc


def template_env_text() -> str:
    model = build_model(cluster_state(), [])
    return render_outputs(model)["template_build_env"]


def test_generated_docs_render_passthrough_details() -> None:
    docs = render_outputs(vms_model())["docs"]
    assert "hostpci0:iGpu0 (pcie=true, rombar=true, xvga=false)" in docs
    assert "| media-lab-01 | 501 | ephemeral_lab | cohe | mgmt0 (management) | dev / br_dev | 52:54:00:00:01:f5 | 10.10.0.21/24 | 10.10.0.254 | yes | yes | 10.10.0.254 |" in docs


def test_generated_ansible_inventory_has_no_removed_nic_aliases() -> None:
    inventory = render_outputs(vms_model())["ansible"]

    assert "ansible_host:" in inventory
    assert "pve_nics:" in inventory
    for alias in ("pve_network", "pve_bridge", "pve_gateway", "pve_dns", "pve_management_nic"):
        assert alias not in inventory


def test_passthrough_vms_get_cloud_init_user_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    snippets = render_snippets(ROOT / "infra/tofu/pve/generated.auto.tfvars.json", "images")

    snippet_names = {snippet.name for snippet in snippets}
    assert snippet_names == {"dev-web-01", "prod-app-01", "media-lab-01"}
    assert {snippet.kind for snippet in snippets} == {"user-data", "network-config"}
    media_snippet = next(snippet for snippet in snippets if snippet.name == "media-lab-01")
    assert media_snippet.file_name == "opentofu-vm-501-user-data.yml"
    assert media_snippet.file_id == "images:snippets/opentofu-vm-501-user-data.yml"
    assert "hostname: media-lab-01" in media_snippet.content
    assert "disable_root: true" in media_snippet.content
    assert "ssh_pwauth: false" in media_snippet.content
    assert "name: clemon" in media_snippet.content
    assert "sudo:\n  - ALL=(ALL) ALL" in media_snippet.content
    assert "name: ops" in media_snippet.content
    assert "sudo:\n  - ALL=(ALL) NOPASSWD:ALL" in media_snippet.content


def test_explicit_multi_nic_vms_render_network_config_and_user_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    cluster = cluster_state()
    model = build_model(cluster, validate_vms(explicit_multi_nic_doc(), cluster))
    tfvars_path = tmp_path / "generated.auto.tfvars.json"
    tfvars_path.write_text(render_outputs(model)["tfvars"], encoding="utf-8")
    snippets = render_snippets(tfvars_path, "images")
    write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    assert any(snippet.kind == "network-config" for snippet in snippets)
    media_user_data = next(snippet for snippet in snippets if snippet.name == "media-lab-01" and snippet.kind == "user-data")
    media_network = next(snippet for snippet in snippets if snippet.name == "media-lab-01" and snippet.kind == "network-config")
    assert media_user_data.file_name == "opentofu-vm-501-user-data.yml"
    assert media_network.file_name == "opentofu-vm-501-network-config.yml"
    network_doc = yaml.safe_load(media_network.content)
    assert network_doc["network"]["version"] == 2
    assert set(network_doc["network"]["ethernets"]) == {"mgmt0", "cluster0"}
    assert network_doc["network"]["ethernets"]["mgmt0"]["match"]["macaddress"] == "52:54:00:10:00:01"
    assert network_doc["network"]["ethernets"]["mgmt0"]["set-name"] == "mgmt0"
    assert network_doc["network"]["ethernets"]["mgmt0"]["addresses"] == ["10.10.0.21/24"]
    assert "routes" not in network_doc["network"]["ethernets"]["mgmt0"]
    assert "nameservers" not in network_doc["network"]["ethernets"]["mgmt0"]
    assert network_doc["network"]["ethernets"]["cluster0"]["match"]["macaddress"] == "52:54:00:10:00:02"
    assert network_doc["network"]["ethernets"]["cluster0"]["addresses"] == ["10.50.0.22/24"]
    assert network_doc["network"]["ethernets"]["cluster0"]["routes"] == [{"to": "default", "via": "10.50.0.254"}]
    assert network_doc["network"]["ethernets"]["cluster0"]["nameservers"]["addresses"] == ["10.50.0.254"]

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert {entry["kind"] for entry in manifest["snippets"]} == {"user-data", "network-config"}
    network_entry = next(entry for entry in manifest["snippets"] if entry["name"] == "media-lab-01" and entry["kind"] == "network-config")
    assert network_entry["file_id"] == "images:snippets/opentofu-vm-501-network-config.yml"
    assert network_entry["byte_count"] == len((tmp_path / network_entry["file_name"]).read_bytes())


def test_validation_normalizes_explicit_nics_and_connection_metadata() -> None:
    cluster = cluster_state()
    normalized = validate_vms(explicit_multi_nic_doc(), cluster)
    media_vm = next(vm for vm in normalized if vm["name"] == "media-lab-01")

    assert [nic["name"] for nic in media_vm["nics"]] == ["mgmt0", "cluster0"]
    assert media_vm["nics"][0]["ansible_connection"] is True
    assert media_vm["nics"][0]["default_route"] is False
    assert media_vm["nics"][1]["default_route"] is True
    assert media_vm["nics"][1]["gateway"] == "10.50.0.254"
    assert media_vm["nics"][1]["dns"] == ["10.50.0.254"]


def test_validation_rejects_explicit_nics_mixed_with_legacy_fields() -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["network"] = "dev"

    with pytest.raises(ValidationError, match="legacy NIC fields are not supported: network"):
        validate_vms(doc, cluster_state())


def test_validation_allows_explicit_nics_without_default_route() -> None:
    cluster = cluster_state()
    cluster["networks"]["nogw"] = {
        "bridge": "br_nogw",
        "cidr": "10.60.0.0/24",
        "gateway": None,
        "dns": None,
        "attach_vms": True,
    }
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][0].pop("gateway", None)
    doc["vms"][2]["nics"][0].pop("default_route", None)
    doc["vms"][2]["nics"][1]["network"] = "nogw"
    doc["vms"][2]["nics"][1]["static_ip"] = "10.60.0.22/24"
    doc["vms"][2]["nics"][1].pop("gateway", None)
    doc["vms"][2]["nics"][1].pop("default_route", None)

    normalized = validate_vms(doc, cluster)
    media_vm = next(vm for vm in normalized if vm["name"] == "media-lab-01")
    assert all(not nic["default_route"] for nic in media_vm["nics"])


def test_validation_allows_explicit_zero_nic_vm_and_skips_inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    cluster = cluster_state()
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    vm = doc["vms"][2]
    vm["nics"] = []
    for field in ("network", "static_ip", "gateway", "dns"):
        vm.pop(field, None)

    model = build_model(cluster, validate_vms(doc, cluster))
    outputs = render_outputs(model)
    inventory = yaml.safe_load(outputs["ansible"])
    assert "media-lab-01" not in inventory["all"]["children"].get("pve_vms", {}).get("hosts", {})

    tfvars_path = tmp_path / "generated.auto.tfvars.json"
    tfvars_path.write_text(outputs["tfvars"], encoding="utf-8")
    snippets = render_snippets(tfvars_path, "images")
    assert any(snippet.name == "media-lab-01" and snippet.kind == "user-data" for snippet in snippets)
    assert not any(snippet.name == "media-lab-01" and snippet.kind == "network-config" for snippet in snippets)


def test_validation_skips_inventory_when_no_nic_is_marked_for_ansible_connection() -> None:
    cluster = cluster_state()
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][0].pop("ansible_connection", None)
    doc["vms"][2]["nics"][1].pop("ansible_connection", None)

    model = build_model(cluster, validate_vms(doc, cluster))
    inventory = yaml.safe_load(render_outputs(model)["ansible"])
    assert "media-lab-01" not in inventory["all"]["children"].get("pve_vms", {}).get("hosts", {})


def test_validation_allows_explicit_nics_without_management_role() -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][0]["role"] = "cluster"
    doc["vms"][2]["nics"][1]["role"] = "storage"

    normalized = validate_vms(doc, cluster_state())
    media_vm = next(vm for vm in normalized if vm["name"] == "media-lab-01")
    assert [nic["role"] for nic in media_vm["nics"]] == ["cluster", "storage"]
    assert media_vm["nics"][0]["ansible_connection"] is True


def test_validation_rejects_duplicate_default_routes() -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][0]["gateway"] = "10.10.0.254"
    doc["vms"][2]["nics"][0]["default_route"] = True

    with pytest.raises(ValidationError, match="at most one default route"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_duplicate_ansible_connection_nics() -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][1]["ansible_connection"] = True

    with pytest.raises(ValidationError, match="at most one ansible_connection NIC"):
        validate_vms(doc, cluster_state())


def test_preflight_expected_tags_include_all_nic_networks() -> None:
    cluster = cluster_state()
    model = build_model(cluster, validate_vms(explicit_multi_nic_doc(), cluster))
    resources = derive_expected_resources(model)
    media_expectation = next(item for item in resources.vmid_expectations if item["name"] == "media-lab-01")

    assert media_expectation["tags"] == ["managed-by-opentofu", "ephemeral_lab", "dev", "prod", "lab", "media", "igpu"]


def test_validation_rejects_duplicate_nic_names() -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][1]["name"] = "mgmt0"

    with pytest.raises(ValidationError, match="duplicate NIC name"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_explicit_nic_mac_and_gateway_errors() -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][1]["mac_address"] = "not-a-mac"

    with pytest.raises(ValidationError, match="must be a MAC address"):
        validate_vms(doc, cluster_state())

    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][1]["gateway"] = "10.50.0.254"
    doc["vms"][2]["nics"].append(
        {
            "name": "storage0",
            "role": "storage",
            "network": "prod",
            "macaddr": "52:54:00:10:00:03",
            "static_ip": "10.50.0.23/24",
            "gateway": "10.50.0.254",
        }
    )

    with pytest.raises(ValidationError, match="at most one default route"):
        validate_vms(doc, cluster_state())


@pytest.mark.parametrize(
    ("network", "message"),
    [
        ("missing", "must reference a declared network"),
        ("storage", "is not attachable for VMs"),
    ],
)
def test_validation_rejects_explicit_nic_network_errors(network: str, message: str) -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][0]["network"] = network

    with pytest.raises(ValidationError, match=message):
        validate_vms(doc, cluster_state())


def test_validation_rejects_explicit_nic_invalid_cidr() -> None:
    doc = explicit_multi_nic_doc()
    doc["vms"][2]["nics"][0]["static_ip"] = "not-a-cidr"

    with pytest.raises(ValidationError, match="must be a valid CIDR-style IP interface"):
        validate_vms(doc, cluster_state())


def test_cloud_init_render_writes_manifest_and_exact_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    tfvars_path = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
    snippets = render_snippets(tfvars_path, "images")
    write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["storage_id"] == "images"
    assert manifest["source_tfvars_path"] == str(tfvars_path)
    assert manifest["source_tfvars_sha256"] == hashlib.sha256(tfvars_path.read_bytes()).hexdigest()

    snippet_names = {entry["file_name"] for entry in manifest["snippets"]}
    assert snippet_names == {snippet.file_name for snippet in snippets}

    assert {entry["kind"] for entry in manifest["snippets"]} == {"user-data", "network-config"}
    media_entry = next(entry for entry in manifest["snippets"] if entry["name"] == "media-lab-01")
    media_bytes = (tmp_path / media_entry["file_name"]).read_bytes()
    assert media_entry["kind"] == "user-data"
    assert media_entry["file_id"] == "images:snippets/opentofu-vm-501-user-data.yml"
    assert media_entry["byte_count"] == len(media_bytes)
    assert media_entry["sha256"] == hashlib.sha256(media_bytes).hexdigest()


def test_cloud_init_upload_and_verify_use_existing_manifest_without_rerender(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    tfvars_path = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
    snippets = render_snippets(tfvars_path, "images")
    write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[object]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cloud_init_ssh.subprocess, "run", fake_run)

    cloud_init_main(["upload", "--output-dir", str(tmp_path), "--storage-id", "images", "--pve-host", "pve-01", "--ssh-user", "ops"])
    cloud_init_main(["verify", "--output-dir", str(tmp_path), "--storage-id", "images", "--pve-host", "pve-01", "--ssh-user", "ops"])

    assert any("--verify" in argv[2] and "--sha256" in argv[2] for argv in calls)


def test_cloud_init_load_rendered_artifacts_rejects_checksum_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    tfvars_path = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
    snippets = render_snippets(tfvars_path, "images")
    write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    snippet_path = tmp_path / snippets[0].file_name
    snippet_path.write_text(snippet_path.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")

    with pytest.raises(ValidationError, match=snippets[0].name):
        load_rendered_artifacts(tmp_path, "images")


def test_cloud_init_upload_timeout_is_operator_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    snippet = CloudInitSnippet(
        vmid=501,
        name="media-lab-01",
        file_name="opentofu-vm-501-user-data.yml",
        file_id="images:snippets/opentofu-vm-501-user-data.yml",
        content="hostname: media-lab-01\n",
        byte_count=23,
        sha256="a" * 64,
    )
    args = Namespace(storage_id="images", pve_host="pve-01", ssh_user="ops", ssh_timeout=30.0)

    def timeout_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[object]:
        raise subprocess.TimeoutExpired(cmd=["ssh"], timeout=30.0)

    monkeypatch.setattr(cloud_init_ssh.subprocess, "run", timeout_run)

    with pytest.raises(ValidationError, match="timed out after 30s") as excinfo:
        cloud_init_ssh.upload_snippets([snippet], args)

    assert snippet.file_name in str(excinfo.value)
    assert snippet.name in str(excinfo.value)


def test_cloud_init_verify_nonzero_exit_is_operator_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    snippet = CloudInitSnippet(
        vmid=501,
        name="media-lab-01",
        file_name="opentofu-vm-501-user-data.yml",
        file_id="images:snippets/opentofu-vm-501-user-data.yml",
        content="hostname: media-lab-01\n",
        byte_count=23,
        sha256="a" * 64,
    )
    args = Namespace(storage_id="images", pve_host="pve-01", ssh_user="ops", ssh_timeout=30.0)

    def failed_run(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[object]:
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(cloud_init_ssh.subprocess, "run", failed_run)

    with pytest.raises(ValidationError, match="ssh command failed") as excinfo:
        cloud_init_ssh.verify_snippets([snippet], args)

    assert snippet.file_name in str(excinfo.value)
    assert snippet.name in str(excinfo.value)


@pytest.mark.parametrize("command", [["sudo", "--flag", "value with spaces", "a'b"]])
def test_cloud_init_ssh_quotes_remote_command_as_a_single_argv_item(command: list[str]) -> None:
    assert cloud_init_ssh._quote_remote_command(command) == " ".join(shlex.quote(part) for part in command)


def test_cloud_init_ssh_builds_single_quoted_remote_command(monkeypatch: pytest.MonkeyPatch) -> None:
    snippet = CloudInitSnippet(
        vmid=501,
        name="media-lab-01",
        file_name="opentofu-vm-501-user-data.yml",
        file_id="images:snippets/opentofu-vm-501-user-data.yml",
        content="hostname: media-lab-01\n",
        byte_count=23,
        sha256="a" * 64,
    )
    args = Namespace(storage_id="images", pve_host="pve-01", ssh_user="ops", ssh_timeout=30.0)
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[object]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cloud_init_ssh.subprocess, "run", fake_run)

    cloud_init_ssh.run_ssh_snippet_command(
        snippet,
        args,
        ["sudo", "-n", "/usr/local/sbin/astra-pve-snippet-upload", "--storage", "images", "--filename", snippet.file_name],
        input_text=snippet.content,
    )

    assert calls == [["ssh", "ops@pve-01", "sudo -n /usr/local/sbin/astra-pve-snippet-upload --storage images --filename opentofu-vm-501-user-data.yml"]]


@pytest.mark.parametrize("action", [cloud_init_ssh.upload_snippets, cloud_init_ssh.verify_snippets])
def test_cloud_init_ssh_rejects_unsafe_storage_id_before_ssh(monkeypatch: pytest.MonkeyPatch, action: Any) -> None:
    snippet = CloudInitSnippet(
        vmid=501,
        name="media-lab-01",
        file_name="opentofu-vm-501-user-data.yml",
        file_id="images:snippets/opentofu-vm-501-user-data.yml",
        content="hostname: media-lab-01\n",
        byte_count=23,
        sha256="a" * 64,
    )
    args = Namespace(storage_id="bad id", pve_host="pve-01", ssh_user="ops", ssh_timeout=30.0)
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[object]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cloud_init_ssh.subprocess, "run", fake_run)

    with pytest.raises(ValidationError, match="storage_id"):
        action([snippet], args)

    assert calls == []


@pytest.mark.parametrize("file_name", ["a/b.yml", "../evil.yml", "bad;name.yml"])
@pytest.mark.parametrize("action", [cloud_init_ssh.upload_snippets, cloud_init_ssh.verify_snippets])
def test_cloud_init_ssh_rejects_unsafe_file_names_before_ssh(monkeypatch: pytest.MonkeyPatch, action: Any, file_name: str) -> None:
    snippet = CloudInitSnippet(
        vmid=501,
        name="media-lab-01",
        file_name=file_name,
        file_id=f"images:snippets/{file_name}",
        content="hostname: media-lab-01\n",
        byte_count=23,
        sha256="a" * 64,
    )
    args = Namespace(storage_id="images", pve_host="pve-01", ssh_user="ops", ssh_timeout=30.0)
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[object]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cloud_init_ssh.subprocess, "run", fake_run)

    with pytest.raises(ValidationError, match="file_name"):
        action([snippet], args)

    assert calls == []


def test_cloud_init_verify_rejects_non_hex_sha256_before_ssh(monkeypatch: pytest.MonkeyPatch) -> None:
    snippet = CloudInitSnippet(
        vmid=501,
        name="media-lab-01",
        file_name="opentofu-vm-501-user-data.yml",
        file_id="images:snippets/opentofu-vm-501-user-data.yml",
        content="hostname: media-lab-01\n",
        byte_count=23,
        sha256="g" * 64,
    )
    args = Namespace(storage_id="images", pve_host="pve-01", ssh_user="ops", ssh_timeout=30.0)
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[object]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cloud_init_ssh.subprocess, "run", fake_run)

    with pytest.raises(ValidationError, match="sha256"):
        cloud_init_ssh.verify_snippets([snippet], args)

    assert calls == []


def test_cloud_init_load_rendered_artifacts_rejects_unsafe_manifest_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    tfvars_path = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
    snippets = render_snippets(tfvars_path, "images")
    write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["snippets"][0]["file_name"] = "../evil.yml"
    manifest["snippets"][0]["sha256"] = "g" * 64
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="file_name|sha256"):
        load_rendered_artifacts(tmp_path, "images")


def test_cloud_init_storage_roles_split_by_purpose() -> None:
    cluster = cluster_state()
    assert cluster["automation"]["cloud_init"]["drive_storage_role"] == "memory"
    assert cluster["automation"]["cloud_init"]["snippet_storage_role"] == "images"

    tfvars = json.loads(render_outputs(vms_model())["tfvars"])
    assert tfvars["cluster"]["automation"]["cloud_init"]["drive_storage_role"] == "memory"
    assert tfvars["cluster"]["automation"]["cloud_init"]["snippet_storage_role"] == "images"


def test_inventory_passthrough_schema_omits_device() -> None:
    vms = load_yaml(VMS_PATH)
    passthrough = vms["vms"][2]["passthrough"][0]
    assert "device" not in passthrough
    assert "device_override" not in passthrough


def test_validation_generates_hostpci0_without_override() -> None:
    normalized = validate_vms(load_yaml(VMS_PATH), cluster_state())
    media_vm = next(vm for vm in normalized if vm["name"] == "media-lab-01")
    assert media_vm["passthrough"][0]["device"] == "hostpci0"


def test_validation_treats_omitted_null_and_empty_passthrough_as_no_devices() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0].pop("passthrough", None)
    doc["vms"][1]["passthrough"] = None
    doc["vms"][2]["passthrough"] = []

    model = build_model(cluster_state(), validate_vms(doc, cluster_state()))
    tfvars = json.loads(render_outputs(model)["tfvars"])

    for vm in tfvars["vms"]:
        assert vm["passthrough"] in (None, [])
        assert not any((item.get("device") or "").startswith("hostpci") for item in vm.get("passthrough") or [])


def test_validation_honors_device_override_and_skips_reserved_devices() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["node"] = "node3"
    doc["vms"][0]["passthrough"] = [
        {"mapping": "iGpu0", "pcie": True, "rombar": True, "xvga": False},
        {"mapping": "iGpu1", "device_override": "hostpci1", "pcie": True, "rombar": True, "xvga": False},
    ]
    cluster = cluster_state()
    cluster["pci_mappings"]["iGpu1"] = {
        "type": "igpu",
        "ha_allowed": False,
        "defaults": {"pcie": True, "rombar": True, "xvga": False},
        "nodes": {"node3": {"path": "0000:00:02.1", "iommu_group": 99}},
    }
    normalized = validate_vms(doc, cluster)
    dev_vm = next(vm for vm in normalized if vm["name"] == "dev-web-01")
    assert [item["device"] for item in dev_vm["passthrough"]] == ["hostpci0", "hostpci1"]


def test_validation_rejects_passthrough_unknown_fields() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][2]["passthrough"][0]["device"] = "hostpci0"
    with pytest.raises(ValidationError, match="passthrough.*unknown keys device"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_other_passthrough_unknown_fields() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][2]["passthrough"][0]["unexpected"] = True
    with pytest.raises(ValidationError, match="passthrough.*unknown keys unexpected"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_duplicate_device_overrides() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][2]["passthrough"] = [
        {"mapping": "iGpu0", "device_override": "hostpci1", "pcie": True, "rombar": True, "xvga": False},
        {"mapping": "iGpu0", "device_override": "hostpci1", "pcie": True, "rombar": True, "xvga": False},
    ]
    with pytest.raises(ValidationError, match="duplicate device_override hostpci1"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_invalid_device_override() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][2]["passthrough"][0]["device_override"] = "hostpci16"
    with pytest.raises(ValidationError, match="device_override must match hostpci0-hostpci15"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_missing_passthrough_flags_with_clear_error() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    del doc["vms"][2]["passthrough"][0]["pcie"]
    with pytest.raises(ValidationError, match="pcie is required and must match mapping default True"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_passthrough_device_exhaustion() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["node"] = "node3"
    doc["vms"][0]["passthrough"] = [
        {"mapping": f"iGpu{i}", "device_override": f"hostpci{i}", "pcie": True, "rombar": True, "xvga": False}
        for i in range(16)
    ] + [{"mapping": "iGpu0", "pcie": True, "rombar": True, "xvga": False}]
    cluster = cluster_state()
    cluster["pci_mappings"]["iGpu1"] = {
        "type": "igpu",
        "ha_allowed": False,
        "defaults": {"pcie": True, "rombar": True, "xvga": False},
        "nodes": {"node3": {"path": "0000:00:02.1", "iommu_group": 99}},
    }
    for i in range(2, 16):
        cluster["pci_mappings"][f"iGpu{i}"] = {
            "type": "igpu",
            "ha_allowed": False,
            "defaults": {"pcie": True, "rombar": True, "xvga": False},
            "nodes": {"node3": {"path": "0000:00:02.1", "iommu_group": 99 + i}},
        }
    with pytest.raises(ValidationError, match="passthrough devices exhausted hostpci0-hostpci15"):
        validate_vms(doc, cluster)


def test_validation_rejects_duplicate_mapping_on_same_node_across_vms() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][1]["passthrough"] = [{"mapping": "iGpu0", "pcie": True, "rombar": True, "xvga": False}]
    with pytest.raises(ValidationError, match="mapping iGpu0 on node cohe is already used by VM prod-app-01"):
        validate_vms(doc, cluster_state())


def test_validation_allows_same_mapping_on_different_nodes() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][1]["node"] = "node3"
    doc["vms"][1]["passthrough"] = [{"mapping": "iGpu0", "pcie": True, "rombar": True, "xvga": False}]
    normalized = validate_vms(doc, cluster_state())
    prod_vm = next(vm for vm in normalized if vm["name"] == "prod-app-01")
    media_vm = next(vm for vm in normalized if vm["name"] == "media-lab-01")
    assert prod_vm["node"] == "node3"
    assert prod_vm["passthrough"][0]["device"] == "hostpci0"
    assert media_vm["passthrough"][0]["device"] == "hostpci0"


def test_validation_rejects_raw_pci_mapping_values() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][2]["passthrough"][0]["mapping"] = "0000:00:02.1"
    with pytest.raises(ValidationError, match="mapping must reference a declared PCI mapping"):
        validate_vms(doc, cluster_state())


def test_validation_rejects_malformed_static_ip_with_vm_field_context() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["nics"][0]["static_ip"] = "not-a-cidr"

    with pytest.raises(ValidationError, match=r"vms\.vms\[0\]\.nics\[0\]\.static_ip: must be a valid CIDR-style IP interface"):
        validate_vms(doc, cluster_state())


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("DEV-web-01", r"vms\.vms\[0\]\.name: must be a lower-case DNS-label-safe value"),
        ("dev web", r"vms\.vms\[0\]\.name: must be a lower-case DNS-label-safe value"),
        ("dev_web", r"vms\.vms\[0\]\.name: must be a lower-case DNS-label-safe value"),
        ("dev.web", r"vms\.vms\[0\]\.name: must be a lower-case DNS-label-safe value"),
        ("-dev", r"vms\.vms\[0\]\.name: must be a lower-case DNS-label-safe value"),
        ("dev-", r"vms\.vms\[0\]\.name: must be a lower-case DNS-label-safe value"),
        ("a" * 64, r"vms\.vms\[0\]\.name: must be a lower-case DNS-label-safe value"),
        ("", r"vms\.vms\[0\]\.name: must be a non-empty string"),
    ],
)
def test_validation_rejects_invalid_vm_names(value: str, message: str) -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["name"] = value

    with pytest.raises(ValidationError, match=message):
        validate_vms(doc, cluster_state())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ansible_groups", ["dev", "dev"], r"vms\.vms\[0\]\.ansible_groups: duplicate ansible_groups value dev"),
        ("ansible_groups", ["dev", 1], r"vms\.vms\[0\]\.ansible_groups\[1\]: must be a non-empty string"),
        ("ansible_groups", ["dev", ""], r"vms\.vms\[0\]\.ansible_groups\[1\]: must be a non-empty string"),
        ("ansible_groups", ["dev", "dev-web"], r"vms\.vms\[0\]\.ansible_groups\[1\]: must be a lower-case Ansible-safe identifier"),
        ("ansible_groups", ["dev", "dev web"], r"vms\.vms\[0\]\.ansible_groups\[1\]: must be a lower-case Ansible-safe identifier"),
        ("tags", ["dev", "dev"], r"vms\.vms\[0\]\.tags: duplicate tag dev"),
        ("tags", ["dev", 1], r"vms\.vms\[0\]\.tags\[1\]: must be a non-empty string"),
        ("tags", ["dev", ""], r"vms\.vms\[0\]\.tags\[1\]: must be a non-empty string"),
        ("tags", ["dev", "dev,ops"], r"vms\.vms\[0\]\.tags\[1\]: must be a lower-case PVE tag token"),
        ("tags", ["dev", "dev ops"], r"vms\.vms\[0\]\.tags\[1\]: must be a lower-case PVE tag token"),
    ],
)
def test_validation_rejects_invalid_and_duplicate_string_lists(field: str, value: list[object], message: str) -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0][field] = value

    with pytest.raises(ValidationError, match=message):
        validate_vms(doc, cluster_state())


@pytest.mark.parametrize(
    ("static_ip", "message"),
    [
        ("not-a-cidr", r"vms\.vms\[0\]\.nics\[0\]\.static_ip: must be a valid CIDR-style IP interface"),
        ("10.10.0.20/25", r"vms\.vms\[0\]\.nics\[0\]\.static_ip: must use prefix /24"),
        ("2001:db8::20/24", r"vms\.vms\[0\]\.nics\[0\]\.static_ip: address family must match dev \(10.10.0.0/24\)"),
        ("10.20.0.20/24", r"vms\.vms\[0\]\.nics\[0\]\.static_ip: must be inside dev \(10.10.0.0/24\)"),
        ("10.10.0.0/24", r"vms\.vms\[0\]\.nics\[0\]\.static_ip: must not be the network address 10.10.0.0"),
        ("10.10.0.255/24", r"vms\.vms\[0\]\.nics\[0\]\.static_ip: must not be the broadcast address 10.10.0.255"),
    ],
)
def test_validation_rejects_static_ip_shape_prefix_and_network_bounds(static_ip: str, message: str) -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["nics"][0]["static_ip"] = static_ip

    with pytest.raises(ValidationError, match=message):
        validate_vms(doc, cluster_state())


def test_validation_rejects_duplicate_static_ip() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][1]["nics"][0]["network"] = "dev"
    doc["vms"][1]["nics"][0]["static_ip"] = doc["vms"][0]["nics"][0]["static_ip"]

    with pytest.raises(ValidationError, match=r"vms\.vms\[1\]\.nics\[0\]\.static_ip: duplicate IP 10.10.0.20"):
        validate_vms(doc, cluster_state())


def test_current_vm_inventory_remains_valid() -> None:
    normalized = validate_vms(load_yaml(VMS_PATH), cluster_state())
    assert [vm["name"] for vm in normalized] == ["dev-web-01", "prod-app-01", "media-lab-01"]
    assert all(len(vm["nics"]) == 1 for vm in normalized)
    assert all(vm["nics"][0]["ansible_connection"] is True for vm in normalized)


def test_pve_cli_validation_failure_exits_1_without_traceback(tmp_path: Path) -> None:
    vms_copy = tmp_path / "vms.yml"
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["nics"][0]["static_ip"] = "not-a-cidr"
    vms_copy.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "scripts.pve_inventory.cli", "--vms", str(vms_copy)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("FAIL validation: ")
    assert "Traceback (most recent call last):" not in result.stderr


def test_template_build_env_uses_if_unset_guards() -> None:
    text = template_env_text()
    assert text.startswith("# Generated by scripts.pve_inventory.cli; source from build-template.sh.\n")
    assert "if [ -z \"${TEMPLATE_VMID+x}\" ]; then TEMPLATE_VMID='9001'; fi" in text
    assert "if [ -z \"${BUILD_BRIDGE+x}\" ]; then BUILD_BRIDGE='br_dev'; fi" in text
    assert text.count("if [ -z \"") == 15


def test_template_build_env_excludes_forbidden_repository_details() -> None:
    text = template_env_text()
    forbidden = (
        "PVE_HOST",
        "PVE_USER",
        "/usr/local/sbin/astra-pve-template-build",
        "/var/cache/astra/packer",
        "^[A-Za-z0-9][A-Za-z0-9._-]+$",
    )
    for item in forbidden:
        assert item not in text


def test_template_build_env_honors_caller_overrides(tmp_path: Path) -> None:
    env_file = tmp_path / "template-build.env"
    env_file.write_text(template_env_text(), encoding="utf-8")

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'IMAGE_URL="override-url"; TEMPLATE_VMID="9999"; . "{env_file}"; printf "%s|%s" "$IMAGE_URL" "$TEMPLATE_VMID"',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == "override-url|9999"


def test_template_build_script_shell_quotes_remote_args(tmp_path: Path) -> None:
    ssh_bin = tmp_path / "ssh"
    capture_path = tmp_path / "ssh-argv.txt"
    ssh_bin.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$@\" > \"${SSH_CAPTURE}\"\n",
        encoding="utf-8",
    )
    ssh_bin.chmod(0o755)

    script = ROOT / "infra" / "packer" / "proxmox" / "debian-13" / "build-template.sh"
    env = os.environ | {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "SSH_CAPTURE": str(capture_path),
        "PVE_HOST": "pve-01.example.invalid",
        "PVE_USER": "pve-ops",
        "TEMPLATE_VMID": "9001",
        "TEMPLATE_NAME": "debian-13-tmpl-20260621",
        "IMAGE_URL_PREFIX": "https://images.example.invalid/",
        "IMAGE_URL": "https://images.example.invalid/debian'$(touch /tmp/pwned);`id`.qcow2",
        "IMAGE_SHA512": "a" * 128,
        "IMPORT_STORAGE": "local",
        "DISK_STORAGE": "fast-nvme",
        "BUILD_DOMAIN": "build.example.invalid",
        "APT_MIRROR": "https://deb.debian.org/debian",
        "APT_SECURITY_MIRROR": "https://security.debian.org/debian-security",
        "TIMEZONE": "Etc/UTC",
        "LOCALE": "en_US.UTF-8",
        "CIUSER": "ci'user",
        "NAMESERVER": "192.0.2.53",
        "BUILD_BRIDGE": "br_dev",
        "FORCE_REPLACE": "true",
        "TEMPLATE_DEBUG": "true",
    }

    subprocess.run(["bash", str(script)], check=True, env=env, capture_output=True, text=True)

    host, remote_command = capture_path.read_text(encoding="utf-8").splitlines()
    assert host == "pve-ops@pve-01.example.invalid"
    assert remote_command.startswith("'sudo' '-n' '/usr/local/sbin/astra-pve-template-build'")
    assert "--image-url" in remote_command
    assert "'https://images.example.invalid/debian'\\''$(touch /tmp/pwned);`id`.qcow2'" in remote_command
    assert "--ciuser" in remote_command
    assert "'ci'\\''user'" in remote_command
    assert remote_command.endswith("'--force' '--debug'")


def test_template_build_script_rejects_shell_unsafe_template_name(tmp_path: Path) -> None:
    ssh_bin = tmp_path / "ssh"
    ssh_bin.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    ssh_bin.chmod(0o755)

    script = ROOT / "infra" / "packer" / "proxmox" / "debian-13" / "build-template.sh"
    env = os.environ | {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "PVE_HOST": "pve-01.example.invalid",
        "TEMPLATE_VMID": "9001",
        "TEMPLATE_NAME": "bad template name",
        "IMAGE_URL_PREFIX": "https://images.example.invalid/",
        "IMAGE_URL": "https://images.example.invalid/debian.qcow2",
        "IMAGE_SHA512": "a" * 128,
        "IMPORT_STORAGE": "local",
        "DISK_STORAGE": "fast-nvme",
        "BUILD_DOMAIN": "build.example.invalid",
        "APT_MIRROR": "https://deb.debian.org/debian",
        "APT_SECURITY_MIRROR": "https://security.debian.org/debian-security",
        "TIMEZONE": "Etc/UTC",
        "LOCALE": "en_US.UTF-8",
        "CIUSER": "ci",
        "NAMESERVER": "192.0.2.53",
        "BUILD_BRIDGE": "br_dev",
    }

    result = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)

    assert result.returncode == 1
    assert "template name must match the conservative template regex" in result.stderr


def test_validation_rejects_unknown_template_build_keys() -> None:
    doc = copy.deepcopy(load_yaml(CLUSTER_PATH))
    doc["cluster"]["automation"]["template_build"]["unexpected"] = "boom"
    with pytest.raises(ValidationError, match="unknown keys"):
        validate_cluster(doc)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("image_url", "https://example.invalid/not-debian.qcow2", "must start with image_url_prefix"),
        ("build_bridge", "storage", "must reference an attachable network bridge"),
        ("nameserver", "not-an-ip", "must be a valid IP address"),
    ],
)
def test_validation_rejects_phase3_template_build_inputs(field: str, value: str, message: str) -> None:
    doc = copy.deepcopy(load_yaml(CLUSTER_PATH))
    doc["cluster"]["automation"]["template_build"][field] = value
    with pytest.raises(ValidationError, match=message):
        validate_cluster(doc)
