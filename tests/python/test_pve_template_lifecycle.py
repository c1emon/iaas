"""Contract tests for the independent PVE template lifecycle."""

from __future__ import annotations

import copy
import json
import os
import socket
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_execution.execution import Execution
from iaas_automation.runtime_execution.outputs import TaskOutputs
from iaas_automation.pve_template import runtime
from iaas_automation.pve_template.contracts import (
    build_preview,
    canonical_digest,
    validate_cleanup_preview,
    validate_preview,
    validate_recipe,
    validate_request,
)


def recipe() -> dict:
    return {
        "schema_version": 1,
        "action": "build",
        "recipe": "debian-13",
        "target": {"node": "node-a", "host": "pve-a.example.invalid",
                   "api_endpoint": "https://pve-a.example.invalid:8006",
                   "insecure": False, "ssh_user": "pve-ops", "ssh_port": 22},
        "vmid": 9002,
        "version": "debian-13-20260922",
        "image_url": "https://images.example.invalid/debian-13.qcow2",
        "image_url_prefix": "https://images.example.invalid/",
        "image_sha512": "a" * 128,
        "import_storage": "local",
        "disk_storage": "local-lvm",
        "build_bridge": "vmbr0",
        "build_domain": "example.invalid",
        "apt_mirror": "https://deb.debian.org/debian",
        "apt_security_mirror": "https://security.debian.org/debian-security",
        "timezone": "Etc/UTC",
        "locale": "en_US.UTF-8",
        "ciuser": "ci",
        "nameserver": "192.0.2.53",
    }


def test_preview_is_fixed_and_round_trips() -> None:
    preview = build_preview(recipe(), runtime={"image_digest": "sha256:" + "b" * 64})
    assert preview["schema_version"] == 1
    assert preview["helper"]["protocol_version"] == 2
    assert validate_preview(preview) == preview
    assert preview["preview_digest"] == canonical_digest({k: v for k, v in preview.items() if k != "preview_digest"})


@pytest.mark.parametrize("field", ["vmid", "image_url", "image_sha512", "build_bridge"])
def test_recipe_rejects_missing_or_invalid_fixed_inputs(field: str) -> None:
    value = recipe()
    if field == "vmid":
        value[field] = 100
    elif field == "image_url":
        value[field] = "https://other.example.invalid/image.qcow2"
    elif field == "image_sha512":
        value[field] = "not-a-checksum"
    else:
        value[field] = ""
    with pytest.raises(ValidationError):
        validate_recipe(value)


def test_preview_digest_and_unknown_fields_are_fail_closed() -> None:
    preview = build_preview(recipe(), runtime={"image_digest": "sha256:" + "b" * 64})
    changed = copy.deepcopy(preview)
    changed["fixed_input"]["vmid"] = 9003
    with pytest.raises(ValidationError, match="digest"):
        validate_preview(changed)
    with pytest.raises(ValidationError, match="unsupported"):
        validate_request({"protocol_version": 2, "operation": "capabilities", "shell": "rm -rf /"})


def test_submit_admission_is_bound_to_preview_and_execution() -> None:
    preview = build_preview(recipe(), runtime={"image_digest": "sha256:" + "b" * 64})
    request = {
        "protocol_version": 2,
        "operation": "submit",
        "execution_id": "build-42",
        "preview": preview,
        "admission": {"schema_version": 1, "approved": True,
                      "preview_digest": preview["preview_digest"], "execution_id": "build-42",
                      "target": recipe()["target"],
                      "consumption": {"reserved": True, "reservation_id": "consume-42"},
                      "pending": {"record_id": "pending-42"},
                      "serialization": {"held": True, "context_id": "lock-42"}},
    }
    assert validate_request(request)["execution_id"] == "build-42"
    request["admission"]["execution_id"] = "other"
    with pytest.raises(ValidationError, match="execution"):
        validate_request(request)


def test_cleanup_preview_and_admission_share_helper_digest() -> None:
    target = recipe()["target"]
    obj = {"node": "node-a", "vmid": 9002, "smbios_uuid": "uuid-1",
           "disks": {"scsi0": "local-lvm:vm-9002-disk-0"}}
    preview = {
        "schema_version": 1, "kind": "pve-template-cleanup-preview", "action": "cleanup",
        "original_execution": "build-42", "vmid": 9002, "volumes": ["local-lvm:vm-9002-disk-0"],
        "owner": "helper", "mode": "failed_build", "target": target, "object": obj,
        "runtime": {"image_digest": "sha256:" + "b" * 64},
        "helper": {"protocol_version": 2},
    }
    body = {key: preview[key] for key in ("original_execution", "vmid", "volumes", "owner", "mode", "target", "object", "runtime", "helper")}
    preview["preview_digest"] = canonical_digest(body)
    assert validate_cleanup_preview(preview)["preview_digest"] == preview["preview_digest"]
    request = {"protocol_version": 2, "operation": "cleanup", "execution_id": "cleanup-42",
               "recovery_of": "build-42", "cleanup": {**preview, "management_status": "stopped"},
                   "admission": {"schema_version": 1, "approved": True, "execution_id": "cleanup-42",
                                 "plan_digest": preview["preview_digest"],
                                 "target": target,
                             "consumption": {"reserved": True, "reservation_id": "consume-42"},
                             "pending": {"record_id": "pending-42"},
                             "serialization": {"held": True, "context_id": "lock-42"}}}
    assert validate_request(request)["admission"]["execution_id"] == "cleanup-42"


def test_runtime_subprocess_records_and_live_verify(tmp_path, monkeypatch) -> None:
    helper = tmp_path / "helper.py"
    helper.write_text(
        "import hashlib, json, os, sys\n"
        "request = json.load(sys.stdin)\n"
        "op = request['operation']\n"
        "if op == 'capabilities': print(json.dumps({'protocol_version': 2}))\n"
        "elif op == 'check': print(json.dumps({'status': 'ready'}))\n"
        "elif op == 'submit':\n"
        "  record = json.load(open(os.environ['FAKE_RECORD']))\n"
        "  response = {'status': 'succeeded', 'execution': {'state': 'succeeded', 'execution_id': request['execution_id'], 'template_record': record}}\n"
        "  if not os.environ.get('MISSING_RECEIPT'): response['receipt'] = {'schema_version': 1, 'kind': 'pve-template-receipt', 'status': 'succeeded', 'execution_id': request['execution_id'], 'preview_digest': request['preview']['preview_digest'], 'target': record['target'], 'object': record['object'], 'template_record': record}\n"
        "  print(json.dumps(response))\n"
        "elif op == 'observe':\n"
        "  record = json.load(open(os.environ['FAKE_RECORD']))\n"
        "  print(json.dumps({'status': 'observed', 'template': record['object'] | {'configuration': record['configuration']}}))\n"
        "elif op == 'cleanup_preview':\n"
        "  record = json.load(open(os.environ['FAKE_RECORD']))\n"
        "  cleanup = request['cleanup']\n"
        "  body = {'original_execution': cleanup['original_execution'], 'vmid': cleanup['vmid'], 'volumes': cleanup['volumes'], 'owner': 'helper', 'mode': cleanup.get('mode', 'failed_build'), 'target': record['target'], 'object': record['object'], 'runtime': cleanup['runtime'], 'helper': cleanup['helper']}\n"
        "  digest = 'sha256:' + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()\n"
        "  print(json.dumps({'status': 'ready', 'preview': {'schema_version': 1, 'kind': 'pve-template-cleanup-preview', 'action': 'cleanup', **body, 'preview_digest': digest}}))\n"
        "elif op == 'cleanup':\n"
        "  assert request.get('admission', {}).get('plan_digest') == request['cleanup']['preview_digest']\n"
        "  print(json.dumps({'status': 'succeeded', 'effects': 'known', 'receipt': {'schema_version': 1, 'kind': 'pve-template-cleanup-receipt', 'status': 'succeeded', 'execution_id': request['execution_id'], 'preview_digest': request['cleanup']['preview_digest'], 'recovery_of': request['recovery_of']}}))\n"
        "else: print(json.dumps({'status': 'unknown'}))\n",
        encoding="utf-8")
    record_path = tmp_path / "record.json"
    record = {"schema_version": 1, "record_id": "template-live-1", "target": recipe()["target"],
              "object": {"node": "node-a", "vmid": 9002, "smbios_uuid": "uuid-1",
                         "disks": {"scsi0": "local-lvm:vm-9002-disk-0"}},
              "configuration": {"template": 1, "scsi0": "local-lvm:vm-9002-disk-0,size=8G"}}
    record_path.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(runtime, "_helper_command", lambda *_: [sys.executable, str(helper)])
    env = {"FAKE_RECORD": str(record_path)}
    digest = "sha256:" + "b" * 64
    selected = SimpleNamespace(documents={"recipe": recipe()}, files={}, options={})

    def execute(tmp_name, *, files=None, options=None):
        outputs = TaskOutputs.create(tmp_path / tmp_name, tmp_path / "implementation", [])
        return Execution(outputs, {**env}), outputs

    plan_execution, plan_outputs = execute("plan")
    runtime.run(selected, "plan", "node-a", plan_execution, digest, "")
    preview_path = plan_outputs.path("plan") / "template-preview.json"
    preview = json.loads(preview_path.read_text())
    admission = {"schema_version": 1, "approved": True, "execution_id": "build-live-1",
                 "preview_digest": preview["preview_digest"], "target": recipe()["target"],
                 "consumption": {"reserved": True, "reservation_id": "consume-live-1"},
                 "pending": {"record_id": "pending-live-1"},
                 "serialization": {"held": True, "context_id": "lock-live-1"}}
    apply_selected = SimpleNamespace(documents={"recipe": recipe()},
                                     files={"template_preview": preview_path},
                                     options={"preview_digest": preview["preview_digest"],
                                              "admission": admission})
    apply_execution, apply_outputs = execute("apply")
    runtime.run(apply_selected, "apply", "node-a", apply_execution, digest, "build-live-1")
    exported = json.loads((apply_outputs.path("generated") / "template-records.json").read_text())
    receipt_path = apply_outputs.path("diagnostics") / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert exported["records"][0]["record_id"] == "template-live-1"
    assert receipt["kind"] == "pve-template-receipt" and "execution" not in receipt

    from iaas_automation.runtime_execution.execution import OperationFailed
    missing_execution, missing_outputs = execute("missing-receipt")
    missing_execution.environ["MISSING_RECEIPT"] = "1"
    with pytest.raises(OperationFailed, match="confirmed success"):
        runtime.run(apply_selected, "apply", "node-a", missing_execution, digest, "build-live-1")
    assert not (missing_outputs.path("diagnostics") / "receipt.json").exists()
    assert (missing_outputs.path("diagnostics") / "remote-observation.json").exists()

    verify_selected = SimpleNamespace(documents={"recipe": recipe()}, files={"receipt": receipt_path},
                                      options={})
    verify_execution, _ = execute("verify")
    runtime.run(verify_selected, "verify", "node-a", verify_execution, digest, "")
    record["object"]["smbios_uuid"] = "uuid-recreated"
    record["configuration"]["scsi0"] = "local-lvm:vm-9002-disk-1,size=8G"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    failed_execution, _ = execute("verify-recreated")
    with pytest.raises(ValidationError, match="verification"):
        runtime.run(verify_selected, "verify", "node-a", failed_execution, digest, "")

    cleanup_plan_selected = SimpleNamespace(documents={"recipe": recipe()}, files={},
                                            options={"action": "cleanup",
                                                     "cleanup": {"vmid": 9002, "owner": "helper",
                                                                 "original_execution": "build-live-1",
                                                                 "management_status": "stopped",
                                                                 "mode": "failed_build",
                                                                 "volumes": ["local-lvm:vm-9002-disk-0"]}})
    cleanup_plan_execution, cleanup_plan_outputs = execute("cleanup-plan")
    runtime.run(cleanup_plan_selected, "plan", "node-a", cleanup_plan_execution, digest, "cleanup-preview-1")
    cleanup_preview_path = cleanup_plan_outputs.path("plan") / "template-preview.json"
    cleanup_preview = json.loads(cleanup_preview_path.read_text())
    cleanup_admission = {"schema_version": 1, "approved": True, "execution_id": "cleanup-live-1",
                         "plan_digest": cleanup_preview["preview_digest"],
                         "target": cleanup_preview["target"],
                         "consumption": {"reserved": True, "reservation_id": "consume-cleanup-1"},
                         "pending": {"record_id": "pending-cleanup-1"},
                         "serialization": {"held": True, "context_id": "lock-cleanup-1"}}
    cleanup_selected = SimpleNamespace(documents={"recipe": recipe()},
                                       files={"template_preview": cleanup_preview_path},
                                       options={"action": "cleanup",
                                                "preview_digest": cleanup_preview["preview_digest"],
                                                "admission": cleanup_admission})
    cleanup_execution, cleanup_outputs = execute("cleanup-apply")
    runtime.run(cleanup_selected, "apply", "node-a", cleanup_execution, digest, "cleanup-live-1")
    assert json.loads((cleanup_outputs.path("diagnostics") / "receipt.json").read_text())["status"] == "succeeded"


def test_runtime_actual_helper_cleanup_subprocess(tmp_path, monkeypatch) -> None:
    helper = Path(__file__).resolve().parents[2] / "automation/pve-node/bin/iaas-pve-template"
    monkeypatch.setattr(runtime, "_helper_command", lambda *_: [sys.executable, str(helper)])
    state = tmp_path / "state"
    original = state / "executions/build-clean-1"
    original.mkdir(parents=True)
    local_recipe = recipe()
    target = {**local_recipe["target"], "node": socket.gethostname().split(".", 1)[0]}
    local_recipe["target"] = target
    object_value = {"node": target["node"], "vmid": 9002,
                    "smbios_uuid": "11111111-1111-4111-8111-111111111111",
                    "disks": {"scsi0": "local-lvm:vm-9002-disk-0"}}
    (original / "record.json").write_text(json.dumps({"schema_version": 1, "kind": "pve-template-execution",
        "execution_id": "build-clean-1", "state": "failed", "owner": "helper",
        "unit": "iaas-pve-template-build-clean-1.service", "target": target, "object": object_value}), encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    qm = fake_bin / "qm"
    qm.write_text("#!/bin/sh\n"
                  "case \"$1\" in config) printf 'smbios1: uuid=11111111-1111-4111-8111-111111111111\\nscsi0: local-lvm:vm-9002-disk-0,size=8G\\ntemplate: 1\\n'; exit 0;;"
                  "destroy) touch \"$DESTROY_MARKER\"; exit 0;; esac\n", encoding="utf-8")
    qm.chmod(0o755)
    systemctl = fake_bin / "systemctl"
    systemctl.write_text("#!/bin/sh\nprintf 'LoadState=loaded\\nActiveState=inactive\\nSubState=dead\\n'\n", encoding="utf-8")
    systemctl.chmod(0o755)
    selected = SimpleNamespace(documents={"recipe": local_recipe}, files={}, options={
                                                                                     "action": "cleanup", "cleanup": {
                                                                                         "vmid": 9002, "owner": "helper",
                                                                                         "original_execution": "build-clean-1",
                                                                                         "management_status": "stopped",
                                                                                         "state_owner": "helper", "state_ref_absent": True,
                                                                                         "mode": "failed_build",
                                                                                         "volumes": ["local-lvm:vm-9002-disk-0"]}})
    digest = "sha256:" + "b" * 64
    env = {"IAAS_PVE_TEMPLATE_ROOT": str(state), "IAAS_PVE_QM": str(qm),
           "IAAS_PVE_TEMPLATE_LOCK": str(tmp_path / "node.lock"),
           "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}", "DESTROY_MARKER": str(tmp_path / "destroyed")}

    def execute(name):
        outputs = TaskOutputs.create(tmp_path / name, tmp_path / "implementation", [])
        return Execution(outputs, env), outputs

    plan_execution, plan_outputs = execute("actual-cleanup-plan")
    runtime.run(selected, "plan", target["node"], plan_execution, digest, "cleanup-preview-actual")
    preview_path = plan_outputs.path("plan") / "template-preview.json"
    preview = json.loads(preview_path.read_text())
    admission = {"schema_version": 1, "approved": True, "execution_id": "cleanup-actual-1",
                 "plan_digest": preview["preview_digest"],
                 "target": target,
                 "consumption": {"reserved": True, "reservation_id": "consume-actual-1"},
                 "pending": {"record_id": "pending-actual-1"},
                 "serialization": {"held": True, "context_id": "lock-actual-1"}}
    apply_selected = SimpleNamespace(documents={"recipe": local_recipe}, files={"template_preview": preview_path},
                                     options={ "action": "cleanup",
                                              "preview_digest": preview["preview_digest"], "admission": admission})
    apply_execution, outputs = execute("actual-cleanup-apply")
    runtime.run(apply_selected, "apply", target["node"], apply_execution, digest, "cleanup-actual-1")
    assert (tmp_path / "destroyed").is_file()
    assert json.loads((outputs.path("diagnostics") / "receipt.json").read_text())["status"] == "succeeded"


@pytest.mark.parametrize("operation", ["check", "read", "plan", "apply", "verify"])
def test_runtime_rejects_caller_helper_command(operation):
    selected = SimpleNamespace(documents={"recipe": recipe()}, files={},
                               options={"helper_command": ["untrusted-program"]})
    with pytest.raises(ValidationError, match="unknown.*option"):
        runtime.run(selected, operation, "node-a", None, "sha256:" + "b" * 64)


def test_helper_environment_override_cannot_bypass_ssh_credentials(monkeypatch):
    monkeypatch.setenv("IAAS_PVE_TEMPLATE_HELPER", "untrusted-program")
    selected = SimpleNamespace(documents={"recipe": recipe()}, files={}, options={})
    with pytest.raises(ValidationError, match="explicit SSH"):
        runtime._helper_command(selected, "read")
    selected.files = {"ssh_key": "/private/key", "known_hosts": "/private/known-hosts"}
    command = runtime._helper_command(selected, "read")
    assert command[0] == "ssh"
    assert command[-3:] == ["sudo", "-n", "/usr/local/sbin/iaas-pve-template"]
    assert "IdentityAgent=none" in command
    assert "StrictHostKeyChecking=yes" in command
    assert "untrusted-program" not in command


@pytest.mark.parametrize("shape", ["receipt", "bundle", "nested_bundle", "object"])
def test_historical_read_accepts_worker_receipt_and_record_bundles(tmp_path, monkeypatch, shape):
    obj = {"node": "node-a", "vmid": 9002, "smbios_uuid": "uuid-1",
           "disks": {"scsi0": "local-lvm:vm-9002-disk-0"}}
    record = {"schema_version": 1, "record_id": "template-build-1", "target": recipe()["target"],
              "object": obj, "configuration": {"template": 1}}
    documents = {"receipt": {"kind": "pve-template-receipt", "template_record": record, "object": obj},
                 "bundle": {"records": [record]},
                 "nested_bundle": {"template_record": {"records": [record]}}, "object": {"object": obj}}
    historical = tmp_path / "receipt.json"
    historical.write_text(json.dumps(documents[shape]))
    selected = SimpleNamespace(documents={"recipe": recipe()}, files={"execution_result": historical}, options={})
    requests = []
    def invoke(_selected, _execution, request, phase):
        requests.append(request)
        return {"status": "observed", "template": {**obj, "configuration": {"template": 1}}}
    monkeypatch.setattr(runtime, "_invoke_helper", invoke)
    outputs = TaskOutputs.create(tmp_path / "out", tmp_path / "implementation", [])
    runtime.run(selected, "read", "node-a", Execution(outputs, {}), "sha256:" + "b" * 64)
    assert requests[0]["template"] == obj
    observation = json.loads((outputs.path("diagnostics") / "observation.json").read_text())
    assert observation["records"]["records"][0]["object"] == obj
    assert observation["build_history"] == "unknown"


@pytest.mark.parametrize("historical", [
    {"template_record": {}}, {"template_record": None, "object": {"node": "node-a", "vmid": 9002}},
    {"records": []},
    {"template_record": {"object": {"node": "node-a", "vmid": 9002}},
     "object": {"node": "node-a", "vmid": 9999}},
])
def test_historical_read_rejects_missing_or_conflicting_record_identity(historical, monkeypatch):
    selected = SimpleNamespace(documents={"recipe": recipe()}, files={}, options={"template": historical})
    monkeypatch.setattr(runtime, "_invoke_helper", lambda *_: pytest.fail("must reject before network"))
    with pytest.raises(ValidationError):
        runtime.run(selected, "read", "node-a", None, "sha256:" + "b" * 64)
