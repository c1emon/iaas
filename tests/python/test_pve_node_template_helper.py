"""Synthetic node-helper checks; no PVE or systemd installation is required."""

from __future__ import annotations

import json
import hashlib
import copy
import os
from pathlib import Path
import socket
import subprocess

from iaas_automation.pve_template.contracts import build_preview


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "automation/pve-node/bin/iaas-pve-template"


def _recipe() -> dict:
    return {
        "schema_version": 1, "action": "build", "recipe": "debian-13",
        "target": {"node": socket.gethostname().split(".", 1)[0], "host": "pve-a.example.invalid",
                    "api_endpoint": "https://pve-a.example.invalid:8006",
                    "insecure": False, "ssh_user": "pve-ops", "ssh_port": 22},
        "vmid": 9003, "version": "v1",
        "image_url": "https://images.example.invalid/debian.qcow2",
        "image_url_prefix": "https://images.example.invalid/", "image_sha512": "a" * 128,
        "import_storage": "local", "disk_storage": "local-lvm", "build_bridge": "vmbr0",
        "build_domain": "example.invalid", "apt_mirror": "https://deb.debian.org/debian",
        "apt_security_mirror": "https://security.debian.org/debian-security", "timezone": "Etc/UTC",
        "locale": "en_US.UTF-8", "ciuser": "ci", "nameserver": "192.0.2.53",
    }


def _run(tmp_path: Path, value: dict, *, systemd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ | {"IAAS_PVE_TEMPLATE_ROOT": str(tmp_path / "state")}
    if systemd:
        env["IAAS_PVE_TEMPLATE_SYSTEMD_RUN"] = str(systemd)
    return subprocess.run(["python3", str(HELPER)], input=json.dumps(value), text=True,
                          capture_output=True, env=env, check=False)


def _admission(preview: dict, execution_id: str) -> dict:
    return {"schema_version": 1, "approved": True,
            "execution_id": execution_id, "plan_digest": preview["preview_digest"],
            "target": preview["fixed_input"]["target"],
            "consumption": {"reserved": True, "reservation_id": f"consume-{execution_id}"},
            "pending": {"record_id": f"pending-{execution_id}"},
            "serialization": {"held": True, "context_id": f"lock-{execution_id}"}}


def _preview(recipe: dict | None = None) -> dict:
    return build_preview(recipe or _recipe(), runtime={"image_digest": "sha256:" + "b" * 64})


def test_helper_rejects_shell_fields_and_advertises_no_restart(tmp_path: Path) -> None:
    result = _run(tmp_path, {"protocol_version": 2, "operation": "capabilities", "command": "rm -rf /"})
    assert result.returncode != 0
    result = _run(tmp_path, {"protocol_version": 2, "operation": "capabilities"})
    response = json.loads(result.stdout)
    assert response["protocol_version"] == 2
    assert response["automatic_restart"] is False
    missing_template = _run(tmp_path, {"protocol_version": 2, "operation": "observe"})
    assert missing_template.returncode != 0
    assert "template" in missing_template.stdout


def test_check_rejects_recipe_for_another_local_node(tmp_path: Path) -> None:
    wrong = _recipe()
    wrong["target"] = {**wrong["target"], "node": "node-that-is-not-local"}
    result = _run(tmp_path, {"protocol_version": 2, "operation": "check", "preview": _preview(wrong)})
    assert result.returncode != 0
    assert "does not match this PVE node" in result.stdout


def test_submit_persists_before_worker_and_deduplicates(tmp_path: Path) -> None:
    marker = tmp_path / "systemd.args"
    fake = tmp_path / "systemd-run"
    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {marker}\n", encoding="utf-8")
    fake.chmod(0o755)
    preview = _preview()
    request = {"protocol_version": 2, "operation": "submit", "execution_id": "build-1",
               "preview": preview,
               "admission": _admission(preview, "build-1")}
    first = _run(tmp_path, request, systemd=fake)
    assert first.returncode == 0, first.stdout + first.stderr
    record = tmp_path / "state/executions/build-1/record.json"
    assert record.is_file()
    assert "--property=Restart=no" in marker.read_text(encoding="utf-8")
    second = _run(tmp_path, request, systemd=fake)
    assert json.loads(second.stdout)["status"] == "existing"
    changed = json.loads(json.dumps(request))
    changed["preview"] = _preview({**_recipe(), "version": "v2"})
    changed["admission"]["plan_digest"] = changed["preview"]["preview_digest"]
    conflict = _run(tmp_path, changed, systemd=fake)
    assert conflict.returncode != 0
    assert "different fixed inputs" in conflict.stdout


def test_worker_runs_every_build_phase_and_attaches_imported_volume(tmp_path: Path) -> None:
    worker = ROOT / "automation/pve-node/bin/iaas-pve-template-worker"
    execution = tmp_path / "execution"
    (execution / "cache").mkdir(parents=True)
    preview = _preview()
    image = b"synthetic genericcloud image"
    preview["fixed_input"]["image_sha512"] = hashlib.sha512(image).hexdigest()
    # Recompute the fixed preview digest after changing the pinned checksum.
    from iaas_automation.pve_template.contracts import canonical_digest
    preview.pop("preview_digest")
    preview["preview_digest"] = canonical_digest(preview)
    (execution / "cache/debian.qcow2").write_bytes(image)
    request = {"protocol_version": 2, "operation": "submit", "execution_id": "build-2",
               "preview": preview, "admission": _admission(preview, "build-2")}
    (execution / "request.json").write_text(json.dumps(request), encoding="utf-8")
    (execution / "record.json").write_text(json.dumps({"execution_id": "build-2", "target": preview["fixed_input"]["target"],
        "preview_digest": preview["preview_digest"], "state": "admitted", "effects": "none", "phases": []}), encoding="utf-8")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    qm = fake_bin / "qm"
    qm.write_text("#!/bin/sh\n"
                  "printf '%s\\n' \"$*\" >> \"$QM_LOG\"\n"
                  "case \"$1\" in config) printf 'unused0: local-lvm:vm-9003-disk-0\\n'; printf 'smbios1: uuid=11111111-1111-4111-8111-111111111111\\n'; printf 'scsi0: local-lvm:vm-9003-disk-0,size=8G\\n'; printf 'scsihw: virtio-scsi-single\\n'; printf 'ide2: local-lvm:cloudinit,media=cdrom\\n'; printf 'template: 1\\n'; exit 0;; create) [ \"$QM_FAIL\" = create ] && exit 9; exit 0;; importdisk|set|template) exit 0;; *) exit 2;; esac\n",
                  encoding="utf-8")
    qm.chmod(0o755)
    pvesh = fake_bin / "pvesh"
    pvesh.write_text("#!/bin/sh\ncase \"$2\" in /cluster/resources) printf '[]\\n';; */storage) printf '[{\\\"storage\\\":\\\"local\\\",\\\"avail\\\":\\\"999999999999\\\"},{\\\"storage\\\":\\\"local-lvm\\\",\\\"avail\\\":\\\"999999999999\\\"}]\\n';; esac\n",
                     encoding="utf-8")
    pvesh.chmod(0o755)
    ip = fake_bin / "ip"
    ip.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ip.chmod(0o755)
    for name in ("virt-customize", "virt-sysprep"):
        script = fake_bin / name
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.chmod(0o755)
    env = os.environ | {"IAAS_PVE_QM": str(qm), "IAAS_PVE_VIRT_CUSTOMIZE": str(fake_bin / "virt-customize"),
                        "IAAS_PVE_VIRT_SYSPREP": str(fake_bin / "virt-sysprep"),
                        "IAAS_PVE_PVESH": str(pvesh), "IAAS_PVE_IP": str(ip),
                        "IAAS_PVE_MIN_FREE_BYTES": "1",
                        "IAAS_PVE_TEMPLATE_LOCK": str(tmp_path / "node.lock"), "QM_LOG": str(tmp_path / "qm.log")}
    result = subprocess.run(["python3", str(worker), "--execution-dir", str(execution)], env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads((execution / "record.json").read_text(encoding="utf-8"))
    phases = [item["phase"] for item in record["phases"]]
    assert {"customize", "sysprep", "create", "import", "import-observation", "configure", "template"} <= set(phases)
    assert record["object"]["smbios_uuid"] == "11111111-1111-4111-8111-111111111111"
    assert record["object"]["disks"] == {"scsi0": "local-lvm:vm-9003-disk-0"}
    assert record["object"]["configuration"]["scsihw"] == "virtio-scsi-single"
    assert record["object"]["configuration"]["ide2"].endswith("media=cdrom")
    assert "--scsi0 local-lvm:vm-9003-disk-0" in (tmp_path / "qm.log").read_text(encoding="utf-8")
    qm_log = (tmp_path / "qm.log").read_text(encoding="utf-8")
    assert "--efidisk0 local-lvm:0,efitype=4m,format=raw" in qm_log
    assert any(item["phase"] == "prerequisites" and item["status"] == "complete"
               for item in record["phases"])
    assert record["storage_effects"] == {"cache": "known", "work": "cleaned"}
    assert record["vm_effects"] == "known"
    assert record["effects"] == "known"

    def run_variant(execution_id: str, variant_preview: dict, *, fail_create: bool = False) -> dict:
        variant = tmp_path / execution_id
        (variant / "cache").mkdir(parents=True)
        (variant / "cache/debian.qcow2").write_bytes(image)
        variant_request = {"protocol_version": 2, "operation": "submit", "execution_id": execution_id,
                           "preview": variant_preview, "admission": _admission(variant_preview, execution_id)}
        (variant / "request.json").write_text(json.dumps(variant_request), encoding="utf-8")
        (variant / "record.json").write_text(json.dumps({"execution_id": execution_id,
            "target": variant_preview["fixed_input"]["target"],
            "preview_digest": variant_preview["preview_digest"], "state": "admitted",
            "effects": "none", "phases": []}), encoding="utf-8")
        variant_env = env | {"QM_FAIL": "create" if fail_create else ""}
        subprocess.run(["python3", str(worker), "--execution-dir", str(variant)], env=variant_env,
                       capture_output=True, text=True, check=False)
        return json.loads((variant / "record.json").read_text(encoding="utf-8"))

    create_failure = run_variant("build-create-failure", copy.deepcopy(preview), fail_create=True)
    assert create_failure["storage_effects"] == {"cache": "known", "work": "known"}
    assert create_failure["vm_effects"] == "unknown"
    assert create_failure["effects"] == "unknown"
    checksum_preview = copy.deepcopy(preview)
    checksum_preview["fixed_input"]["image_sha512"] = "0" * 128
    checksum_preview.pop("preview_digest")
    checksum_preview["preview_digest"] = canonical_digest(checksum_preview)
    checksum_failure = run_variant("build-checksum-failure", checksum_preview)
    assert checksum_failure["storage_effects"] == {"cache": "known", "work": "none"}
    assert checksum_failure["vm_effects"] == "none"
    assert checksum_failure["effects"] == "known"
    template_records = json.loads((execution / "template-record.json").read_text(encoding="utf-8"))
    assert template_records["records"][0]["target"]["api_endpoint"].startswith("https://")

    state = tmp_path / "controller-state"
    precache = tmp_path / "precache.qcow2"
    precache.write_bytes(image)
    controller_preview = _preview({**_recipe(), "vmid": 9004,
                                   "image_sha512": hashlib.sha512(image).hexdigest()})
    controller_request = {"protocol_version": 2, "operation": "submit", "execution_id": "build-3",
                          "preview": controller_preview,
                          "admission": _admission(controller_preview, "build-3")}
    service = tmp_path / "systemd-run"
    service.write_text("#!/bin/sh\n"
                       "while [ $# -gt 0 ]; do [ \"$1\" = --execution-dir ] && { dir=$2; shift 2; continue; }; shift; done\n"
                       "mkdir -p \"$dir/cache\"\ncp \"$PRECACHE\" \"$dir/cache/debian.qcow2\"\n"
                       f"exec python3 {worker} --execution-dir \"$dir\"\n", encoding="utf-8")
    service.chmod(0o755)
    helper_env = env | {"IAAS_PVE_TEMPLATE_ROOT": str(state), "IAAS_PVE_TEMPLATE_SYSTEMD_RUN": str(service),
                        "PRECACHE": str(precache)}
    submitted = subprocess.run(["python3", str(HELPER)], input=json.dumps(controller_request), text=True,
                               capture_output=True, env=helper_env, check=False)
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    observed = json.loads(submitted.stdout)
    assert observed["execution"]["state"] == "succeeded"


def test_query_missing_unit_is_unknown(tmp_path: Path) -> None:
    state = tmp_path / "state/executions/q-1"
    state.mkdir(parents=True)
    (state / "record.json").write_text(json.dumps({
        "schema_version": 1, "kind": "pve-template-execution", "execution_id": "q-1",
        "state": "admitted", "effects": "none", "unit": "iaas-pve-template-q-1.service",
    }), encoding="utf-8")
    result = _run(tmp_path, {"protocol_version": 2, "operation": "query", "execution_id": "q-1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["execution"]["state"] == "unknown"


def test_submit_failure_does_not_overwrite_worker_terminal_record(tmp_path: Path) -> None:
    fake = tmp_path / "systemd-run"
    fake.write_text("#!/bin/sh\n"
                    "while [ $# -gt 0 ]; do [ \"$1\" = --execution-dir ] && { dir=$2; shift 2; continue; }; shift; done\n"
                    "cat > \"$dir/record.json\" <<'EOF'\n"
                    '{"execution_id":"build-race","state":"succeeded","effects":"known"}'
                    "\nEOF\nexit 1\n", encoding="utf-8")
    fake.chmod(0o755)
    preview = _preview()
    request = {"protocol_version": 2, "operation": "submit", "execution_id": "build-race",
               "preview": preview, "admission": _admission(preview, "build-race")}
    result = _run(tmp_path, request, systemd=fake)
    assert result.returncode != 0
    record = json.loads((tmp_path / "state/executions/build-race/record.json").read_text(encoding="utf-8"))
    assert record["state"] == "succeeded"


def test_cleanup_rejects_running_original_execution(tmp_path: Path) -> None:
    state = tmp_path / "state/executions/build-running"
    state.mkdir(parents=True)
    (state / "record.json").write_text(json.dumps({
        "schema_version": 1, "kind": "pve-template-execution", "execution_id": "build-running",
        "state": "running", "effects": "unknown", "owner": "helper",
        "target": {"node": socket.gethostname().split(".", 1)[0],
                   "api_endpoint": "https://pve-a.example.invalid:8006"},
        "unit": "iaas-pve-template-build-running.service", "object": {"vmid": 9003},
    }), encoding="utf-8")
    request = {"protocol_version": 2, "operation": "cleanup_preview", "execution_id": "cleanup-running",
               "cleanup": {"original_execution": "build-running", "vmid": 9003, "owner": "helper",
                           "management_status": "stopped", "state_ref_absent": True, "volumes": []}}
    result = _run(tmp_path, request)
    assert result.returncode != 0
    assert "still active" in result.stdout
