"""Focused Phase 3 tests for PVE template build parameterization."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest
import yaml

import scripts.pve_inventory.cloud_init as cloud_init
from scripts.common.io import load_yaml
from scripts.pve_inventory.inventory.model import build_model
from scripts.pve_inventory.inventory.render import render_outputs
from scripts.common.errors import ValidationError
from scripts.pve_inventory.validation import validate_cluster, validate_vms


ROOT = Path(__file__).resolve().parents[2]
CLUSTER_PATH = ROOT / "inventory" / "pve-cluster.yml"
VMS_PATH = ROOT / "inventory" / "vms.yml"


def cluster_state() -> dict[str, Any]:
    return validate_cluster(load_yaml(CLUSTER_PATH))


def vms_model() -> dict[str, Any]:
    cluster = cluster_state()
    return build_model(cluster, validate_vms(load_yaml(VMS_PATH), cluster))


def template_env_text() -> str:
    model = build_model(cluster_state(), [])
    return render_outputs(model)["template_build_env"]


def test_generated_docs_render_passthrough_details() -> None:
    docs = render_outputs(vms_model())["docs"]
    assert "hostpci0:iGpu0 (pcie=true, rombar=true, xvga=false)" in docs
    assert "| media-lab-01 | 501 | ephemeral_lab | cohe | dev | 10.10.0.21/24 |" in docs


def test_passthrough_vms_get_cloud_init_user_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    snippets = cloud_init.render_snippets(ROOT / "infra/tofu/pve/generated.auto.tfvars.json", "images")

    snippet_names = {snippet.name for snippet in snippets}
    assert snippet_names == {"dev-web-01", "prod-app-01", "media-lab-01"}
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


def test_cloud_init_render_writes_manifest_and_exact_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    tfvars_path = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
    snippets = cloud_init.render_snippets(tfvars_path, "images")
    cloud_init.write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["storage_id"] == "images"
    assert manifest["source_tfvars_path"] == str(tfvars_path)
    assert manifest["source_tfvars_sha256"] == hashlib.sha256(tfvars_path.read_bytes()).hexdigest()

    snippet_names = {entry["file_name"] for entry in manifest["snippets"]}
    assert snippet_names == {snippet.file_name for snippet in snippets}

    media_entry = next(entry for entry in manifest["snippets"] if entry["name"] == "media-lab-01")
    media_bytes = (tmp_path / media_entry["file_name"]).read_bytes()
    assert media_entry["file_id"] == "images:snippets/opentofu-vm-501-user-data.yml"
    assert media_entry["byte_count"] == len(media_bytes)
    assert media_entry["sha256"] == hashlib.sha256(media_bytes).hexdigest()


def test_cloud_init_upload_and_verify_use_existing_manifest_without_rerender(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    tfvars_path = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
    snippets = cloud_init.render_snippets(tfvars_path, "images")
    cloud_init.write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    monkeypatch.setattr(cloud_init, "render_snippets", lambda *args, **kwargs: pytest.fail("upload/verify must not rerender"))

    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[object]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cloud_init.subprocess, "run", fake_run)

    cloud_init.main(["upload", "--output-dir", str(tmp_path), "--storage-id", "images", "--pve-host", "pve-01", "--ssh-user", "ops"])
    cloud_init.main(["verify", "--output-dir", str(tmp_path), "--storage-id", "images", "--pve-host", "pve-01", "--ssh-user", "ops"])

    assert any("--verify" in argv and "--sha256" in argv for argv in calls)


def test_cloud_init_load_rendered_artifacts_rejects_checksum_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PVE_VM_CLEMON_PASSWORD", "clemon-password")
    monkeypatch.setenv("PVE_VM_CLEMON_PUBLIC_KEY", "ssh-ed25519 AAAAclemon clemon@example")
    monkeypatch.setenv("PVE_VM_OPS_PASSWORD", "ops-password")
    monkeypatch.setenv("PVE_VM_OPS_PUBLIC_KEY", "ssh-ed25519 AAAAops ops@example")

    tfvars_path = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
    snippets = cloud_init.render_snippets(tfvars_path, "images")
    cloud_init.write_rendered_artifacts(snippets, tfvars_path, "images", tmp_path)

    snippet_path = tmp_path / snippets[0].file_name
    snippet_path.write_text(snippet_path.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")

    with pytest.raises(ValidationError, match=snippets[0].name):
        cloud_init.load_rendered_artifacts(tmp_path, "images")


def test_cloud_init_upload_timeout_is_operator_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    snippet = cloud_init.CloudInitSnippet(
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

    monkeypatch.setattr(cloud_init.subprocess, "run", timeout_run)

    with pytest.raises(ValidationError, match="timed out after 30s") as excinfo:
        cloud_init.upload_snippets([snippet], args)

    assert snippet.file_name in str(excinfo.value)
    assert snippet.name in str(excinfo.value)


def test_cloud_init_verify_nonzero_exit_is_operator_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    snippet = cloud_init.CloudInitSnippet(
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

    monkeypatch.setattr(cloud_init.subprocess, "run", failed_run)

    with pytest.raises(ValidationError, match="ssh command failed") as excinfo:
        cloud_init.verify_snippets([snippet], args)

    assert snippet.file_name in str(excinfo.value)
    assert snippet.name in str(excinfo.value)


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
    doc["vms"][0]["static_ip"] = "not-a-cidr"

    with pytest.raises(ValidationError, match=r"vms\.vms\[0\]\.static_ip: must be a valid CIDR-style IP interface"):
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
        ("not-a-cidr", r"vms\.vms\[0\]\.static_ip: must be a valid CIDR-style IP interface"),
        ("10.10.0.20/25", r"vms\.vms\[0\]\.static_ip: must use prefix /24"),
        ("2001:db8::20/24", r"vms\.vms\[0\]\.static_ip: address family must match dev \(10.10.0.0/24\)"),
        ("10.20.0.20/24", r"vms\.vms\[0\]\.static_ip: must be inside dev \(10.10.0.0/24\)"),
        ("10.10.0.0/24", r"vms\.vms\[0\]\.static_ip: must not be the network address 10.10.0.0"),
        ("10.10.0.255/24", r"vms\.vms\[0\]\.static_ip: must not be the broadcast address 10.10.0.255"),
    ],
)
def test_validation_rejects_static_ip_shape_prefix_and_network_bounds(static_ip: str, message: str) -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["static_ip"] = static_ip

    with pytest.raises(ValidationError, match=message):
        validate_vms(doc, cluster_state())


def test_validation_rejects_duplicate_static_ip() -> None:
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][1]["network"] = "dev"
    doc["vms"][1]["gateway"] = "10.10.0.254"
    doc["vms"][1]["dns"] = ["10.10.0.254"]
    doc["vms"][1]["static_ip"] = doc["vms"][0]["static_ip"]

    with pytest.raises(ValidationError, match=r"vms\.vms\[1\]\.static_ip: duplicate IP 10.10.0.20"):
        validate_vms(doc, cluster_state())


def test_current_vm_inventory_remains_valid() -> None:
    normalized = validate_vms(load_yaml(VMS_PATH), cluster_state())
    assert [vm["name"] for vm in normalized] == ["dev-web-01", "prod-app-01", "media-lab-01"]


def test_pve_cli_validation_failure_exits_1_without_traceback(tmp_path: Path) -> None:
    vms_copy = tmp_path / "vms.yml"
    doc = copy.deepcopy(load_yaml(VMS_PATH))
    doc["vms"][0]["static_ip"] = "not-a-cidr"
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
