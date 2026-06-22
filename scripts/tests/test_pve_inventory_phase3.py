"""Focused Phase 3 tests for PVE template build parameterization."""

from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.pve_inventory.io import load_yaml
from scripts.pve_inventory.model import build_model
from scripts.pve_inventory.render import render_outputs
from scripts.pve_inventory.cloud_init import render_snippets
from scripts.pve_inventory.errors import ValidationError
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

    snippets = render_snippets(ROOT / "infra/tofu/pve/generated.auto.tfvars.json", "images")

    snippet_names = {snippet.name for snippet in snippets}
    assert snippet_names == {"dev-web-01", "prod-app-01", "media-lab-01"}
    media_snippet = next(snippet for snippet in snippets if snippet.name == "media-lab-01")
    assert media_snippet.file_name == "opentofu-vm-501-user-data.yml"
    assert media_snippet.file_id == "images:snippets/opentofu-vm-501-user-data.yml"
    assert "hostname: media-lab-01" in media_snippet.content
    assert "name: ops" in media_snippet.content


def test_inventory_passthrough_schema_omits_device() -> None:
    vms = load_yaml(VMS_PATH)
    passthrough = vms["vms"][2]["passthrough"][0]
    assert "device" not in passthrough
    assert "device_override" not in passthrough


def test_validation_generates_hostpci0_without_override() -> None:
    normalized = validate_vms(load_yaml(VMS_PATH), cluster_state())
    media_vm = next(vm for vm in normalized if vm["name"] == "media-lab-01")
    assert media_vm["passthrough"][0]["device"] == "hostpci0"


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
