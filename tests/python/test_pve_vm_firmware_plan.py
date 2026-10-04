"""Real provider create plans; configuration observation uses a synthetic API."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from iaas.runtime_execution.pve_results import expectations, verify_configuration


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def firmware_plan(tmp_path_factory):
    tofu = shutil.which("tofu")
    if tofu is None:
        pytest.skip("OpenTofu is required for real provider plan verification")
    root = tmp_path_factory.mktemp("vm-firmware-plan")
    shutil.copytree(ROOT / "automation/opentofu/modules/pve-cloudinit-vm", root / "vm")
    shutil.copy(ROOT / "tests/fixtures/runtime-root/.terraform.lock.hcl", root)
    modules = {}
    for bios in ("seabios", "ovmf"):
        for protected in (False, True):
            modules[f"{bios}_{str(protected).lower()}"] = {
                "source": "./vm", "cluster_name": "synthetic",
                "disk_datastore_id": "local", "cloud_init_datastore_id": "local",
                "started": False, "on_boot": False, "prevent_destroy": protected,
                "tags": ["synthetic"],
                "user_data_file_id": "local:snippets/user.yml",
                "network_data_file_id": "local:snippets/network.yml",
                "template": {"bios": bios, "machine": "q35", "scsi_controller": "virtio-scsi-single",
                             "node": "n1", "vmid": 900, "cpu_type": "host", "primary_disk": "scsi0"},
                "vm": {"name": f"{bios}-{protected}", "node": "n1", "vmid": 100 + len(modules),
                       "pool": None, "resources": {"cores": 2, "memory_mib": 1024, "root_disk_gib": 8},
                       "nics": [], "passthrough": []},
            }
    (root / "main.tf.json").write_text(json.dumps({
        "terraform": {"required_providers": {"proxmox": {"source": "bpg/proxmox", "version": "~> 0.111.0"}}},
        "provider": {"proxmox": {"endpoint": "https://pve.invalid:8006",
                                  "api_token": "synthetic@pve!test=synthetic", "insecure": False}},
        "module": modules,
    }))

    def run(*args):
        result = subprocess.run([tofu, f"-chdir={root}", *args], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    run("init", "-backend=false", "-input=false", "-lockfile=readonly", "-no-color")
    run("validate", "-no-color")
    run("plan", "-refresh=false", "-input=false", "-out=plan.tfplan", "-no-color")
    return json.loads(run("show", "-json", "plan.tfplan"))["resource_changes"]


@pytest.mark.integration
@pytest.mark.parametrize("bios", ["seabios", "ovmf"])
@pytest.mark.parametrize("protected", [False, True])
def test_saved_create_plan_and_configuration_share_efi_scope(firmware_plan, bios, protected):
    branch = "protected" if protected else "unprotected"
    address = f"module.{bios}_{str(protected).lower()}.proxmox_virtual_environment_vm.{branch}[0]"
    item = next(row for row in firmware_plan if row["address"] == address)
    assert item["change"]["actions"] == ["create"]
    values = deepcopy(item["change"]["after"])
    assert len(values["efi_disk"]) == (1 if bios == "ovmf" else 0)
    if bios == "ovmf":
        assert values["efi_disk"][0] == {
            "datastore_id": "local", "file_format": "raw", "type": "4m", "pre_enrolled_keys": False,
        }
    values["smbios"] = [{"uuid": "synthetic-uuid"}]
    snapshot = {"resources": [{"module": address.split(".proxmox_")[0], "type": item["type"],
                               "name": branch, "instances": [{"index_key": 0, "attributes": values}]}]}
    expected = expectations([item], snapshot)
    assert expected[0]["values"]["efi_disk"] == values["efi_disk"]

    class API:
        def vm_config(self, node, vmid):
            config = {"cores": 2, "cpu": "host", "memory": "1024", "bios": bios, "machine": "q35",
                      "scsihw": "virtio-scsi-single", "scsi0": f"local:vm-{vmid}-disk-0,size=8G",
                      "smbios1": "uuid=synthetic-uuid",
                      "cicustom": "user=local:snippets/user.yml,network=local:snippets/network.yml"}
            if bios == "ovmf":
                config["efidisk0"] = f"local:vm-{vmid}-disk-1,efitype=4m,size=4M"
            return config

        def vm_status(self, node, vmid):
            return {"status": "stopped"}

    report = verify_configuration(expected, API())
    assert report["status"] == "passed", report
