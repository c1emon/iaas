from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.pve_template import contracts, runtime

from test_image_publish_contracts import request as publish_request


TARGET = {"api_endpoint": "https://pve.example.invalid:8006", "node": "cohe", "tls_verify": True}
EXECUTION_ID = "publish-1"
PREVIEW_DIGEST = "sha256:" + "a" * 64
RUNTIME_DIGEST = "runtime@sha256:" + "b" * 64
UPLOAD = "staging:import/publish-1.qcow2"
DISK = "images:vm-9001-disk-0"


class Outputs:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "diagnostics").mkdir(parents=True)

    def path(self, category: str) -> Path:
        return self.root / category


class CleanupAPI:
    def __init__(self, *, config: dict[str, object], volumes: set[str], active: bool = False,
                 failed_task: bool = False, upload: str = UPLOAD) -> None:
        self.config = config
        self.volumes = set(volumes)
        self.active = active
        self.failed_task = failed_task
        self.upload = upload
        self.deletes: list[tuple[str, str]] = []

    def request(self, method: str, path: str, *, fields: dict | None = None, **kwargs: object) -> object:
        if method == "GET" and "/tasks/" in path and path.endswith("/status"):
            if self.active:
                return {"status": "running"}
            return {"status": "stopped", "exitstatus": "ERROR" if self.failed_task and "00000004" in path else "OK"}
        if method == "GET" and path.endswith("/config"):
            return dict(self.config)
        if method == "GET" and path.endswith("/content"):
            storage = path.split("/storage/", 1)[1].rsplit("/content", 1)[0]
            return [{"volid": value} for value in sorted(self.volumes) if value.startswith(storage + ":")]
        if method == "DELETE" and "/qemu/" in path:
            self.deletes.append((method, path))
            self.volumes.discard(DISK)
            return "UPID:cohe:00000000:00000000:00000006:vmdelete:100:root@pam:"
        if method == "DELETE" and "/content/" in path:
            self.deletes.append((method, path))
            self.volumes.discard(unquote(path.rsplit("/", 1)[1]))
            return "UPID:cohe:00000000:00000000:00000005:voldelete:100:root@pam:"
        raise AssertionError((method, path, fields))


def _execution(tmp_path: Path) -> Any:
    return SimpleNamespace(outputs=Outputs(tmp_path / "outputs"), environ={"PVE_API_TOKEN": "user!token"})


def _journal(original: Path, *, template_status: str = "succeeded", result: bool = True,
             execution_id: str = EXECUTION_ID, preview_digest: str = PREVIEW_DIGEST) -> None:
    diagnostics = original / "diagnostics"
    diagnostics.mkdir(parents=True)
    template_event = {"phase": "template", "status": template_status,
                      "upid": "UPID:cohe:00000000:00000000:00000004:template:100:root@pam:",
                      "disk_slot": "scsi0", "imported_volume": DISK}
    if template_status == "succeeded":
        template_event["final_volume"] = DISK
    intent = {
        "kind": "pve-template-publish-intent", "schema_version": 1,
        "execution_id": execution_id, "preview_digest": preview_digest, "target": TARGET,
        "runtime_digest": RUNTIME_DIGEST, "artifact_digest": "sha256:" + "c" * 64,
        "vmid": 9001, "upload_volid": UPLOAD, "boot_disk": "scsi0",
        "events": [
            {"phase": "upload", "status": "succeeded",
             "upid": "UPID:cohe:00000000:00000000:00000001:upload:100:root@pam:"},
            {"phase": "create", "status": "succeeded",
             "upid": "UPID:cohe:00000000:00000000:00000002:create:100:root@pam:",
             "smbios_uuid": "template-uuid"},
            template_event,
            {"phase": "local-cleanup", "status": "succeeded"},
        ],
        "status": "succeeded" if template_status == "succeeded" else "unknown",
    }
    (diagnostics / "publish-intent.json").write_text(json.dumps(intent) + "\n")
    if result:
        template_record = {
            "kind": "pve-template-record", "schema_version": 2, "record_id": "v1-9001",
            "target": TARGET, "node": "cohe", "vmid": 9001, "smbios_uuid": "template-uuid",
            "volumes": {"scsi0": DISK}, "configuration": {"scsi0": DISK},
            "origin": "publication", "execution_id": execution_id,
            "artifact_digest": "sha256:" + "c" * 64,
            "verification": {"template_config": "passed"},
        }
        receipt = {"kind": "pve-template-result", "schema_version": 2,
                   "execution_id": execution_id, "preview_digest": preview_digest,
                   "action": "publish", "status": "succeeded", "template_record": template_record}
        (diagnostics / "result.json").write_text(json.dumps(receipt) + "\n")


def _selected(original: Path) -> SimpleNamespace:
    return SimpleNamespace(files={"original_execution_dir": str(original)}, options={})


def _fixed(*, objects: list[dict], volumes: list[object], execution_id: str = EXECUTION_ID,
           preview_digest: str = PREVIEW_DIGEST) -> dict:
    return {"target": TARGET, "original_execution_id": execution_id,
            "original_execution_dir": "retained/publish-1", "original_preview_digest": preview_digest,
            "objects": objects, "volumes": volumes,
            "ownership_admission": {"owner": "publisher", "reference": "journal/publish-1", "activity": "stopped"}}


def _preview(fixed: dict, action: str = "cleanup") -> dict:
    return {"action": action, "fixed_input": fixed, "preview_digest": PREVIEW_DIGEST,
            "runtime": {"image_digest": RUNTIME_DIGEST}}


def _object() -> dict:
    return {"vmid": 9001, "smbios_uuid": "template-uuid", "volumes": {"scsi0": DISK}}


def test_staging_only_cleanup_uses_journal_upload_without_deleting_vm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original"
    _journal(original)
    journal_path = original / "diagnostics" / "publish-intent.json"
    journal = json.loads(journal_path.read_text())
    journal["events"].append({"phase": "remote-cleanup", "status": "submitted",
                               "upid": "UPID:cohe:00000000:00000000:00000005:voldelete:100:root@pam:",
                               "volid": UPLOAD})
    journal["events"].append({"phase": "remote-cleanup", "status": "unknown", "volid": UPLOAD})
    journal["status"] = "unknown"
    journal_path.write_text(json.dumps(journal) + "\n")
    api = CleanupAPI(config={"template": 1, "smbios1": "uuid=template-uuid", "scsi0": DISK}, volumes={UPLOAD})
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)

    result = runtime._delete_action(_selected(original), execution, _fixed(objects=[], volumes=[UPLOAD]),
                                    _preview(_fixed(objects=[], volumes=[UPLOAD])), "cleanup-1")

    assert result["status"] == "succeeded"
    assert not any("/qemu/" in path for _, path in api.deletes)
    assert any("/content/" in path for _, path in api.deletes)


def test_cleanup_rejects_wrong_original_binding_before_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original"
    _journal(original)
    api = CleanupAPI(config={}, volumes={UPLOAD})
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    fixed = _fixed(objects=[], volumes=[UPLOAD], execution_id="wrong-execution")

    with pytest.raises(ValidationError, match="original execution"):
        runtime._delete_action(_selected(original), execution, fixed, _preview(fixed), "cleanup-1")
    assert api.deletes == []


@pytest.mark.parametrize("config,match", [
    ({"template": 0, "smbios1": "uuid=reused", "scsi0": DISK}, "UUID"),
    ({"template": 0, "smbios1": "uuid=template-uuid", "scsi0": DISK, "scsi1": "images:extra"}, "exactly"),
    ({"template": 0, "smbios1": "uuid=template-uuid", "scsi0": DISK,
      "efidisk0": "images:unexpected-efi"}, "exactly"),
])
def test_cleanup_rejects_reused_vmid_or_extra_volume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                     config: dict[str, object], match: str) -> None:
    original = tmp_path / "original"
    _journal(original, template_status="failed", result=False)
    api = CleanupAPI(config=config, volumes={DISK})
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    fixed = _fixed(objects=[_object()], volumes=[DISK])

    with pytest.raises(ValidationError, match=match):
        runtime._delete_action(_selected(original), execution, fixed, _preview(fixed), "cleanup-1")
    assert api.deletes == []


def test_cleanup_does_not_delete_volume_already_removed_by_vm_purge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original"
    _journal(original, template_status="failed", result=False)
    api = CleanupAPI(config={"template": 0, "smbios1": "uuid=template-uuid", "scsi0": DISK},
                     volumes={DISK}, failed_task=True)
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    fixed = _fixed(objects=[_object()], volumes=[DISK])

    result = runtime._delete_action(_selected(original), execution, fixed, _preview(fixed), "cleanup-1")

    assert result["status"] == "succeeded"
    assert len([path for _, path in api.deletes if "/qemu/" in path]) == 1
    assert not any("/content/" in path for _, path in api.deletes)


def test_cleanup_allows_create_only_vm_with_no_disk_after_import_failure(tmp_path: Path,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original"
    _journal(original, result=False)
    journal_path = original / "diagnostics" / "publish-intent.json"
    journal = json.loads(journal_path.read_text())
    journal["events"] = journal["events"][:2]
    journal["status"] = "unknown"
    journal_path.write_text(json.dumps(journal) + "\n")
    api = CleanupAPI(config={"template": 0, "smbios1": "uuid=template-uuid"}, volumes={UPLOAD})
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    fixed = _fixed(objects=[{"vmid": 9001, "smbios_uuid": "template-uuid", "volumes": {}}],
                   volumes=[UPLOAD])

    result = runtime._delete_action(_selected(original), execution, fixed, _preview(fixed), "cleanup-1")

    assert result["status"] == "succeeded"
    assert any("/qemu/" in path for _, path in api.deletes)


def test_cleanup_rejects_active_original_upid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original"
    _journal(original)
    journal_path = original / "diagnostics" / "publish-intent.json"
    journal = json.loads(journal_path.read_text())
    journal["events"][-1]["status"] = "submitted"
    journal["status"] = "unknown"
    journal_path.write_text(json.dumps(journal) + "\n")
    api = CleanupAPI(config={}, volumes={UPLOAD}, active=True)
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    fixed = _fixed(objects=[], volumes=[UPLOAD])

    with pytest.raises(ValidationError, match="active or unknown"):
        runtime._delete_action(_selected(original), execution, fixed, _preview(fixed), "cleanup-1")
    assert api.deletes == []


def test_cleanup_rejects_template_task_submitted_but_observed_ok(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original"
    _journal(original, template_status="submitted", result=False)
    api = CleanupAPI(config={"template": 1, "smbios1": "uuid=template-uuid", "scsi0": DISK},
                     volumes={DISK})
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    fixed = _fixed(objects=[_object()], volumes=[DISK])

    with pytest.raises(ValidationError, match="retired"):
        runtime._delete_action(_selected(original), execution, fixed, _preview(fixed), "cleanup-1")
    assert api.deletes == []


def test_cleanup_can_remove_incomplete_template_after_failed_conversion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original"
    _journal(original, template_status="failed", result=False)
    api = CleanupAPI(config={"template": 1, "smbios1": "uuid=template-uuid", "scsi0": DISK},
                     volumes={DISK}, failed_task=True)
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    fixed = _fixed(objects=[_object()], volumes=[DISK])

    result = runtime._delete_action(_selected(original), execution, fixed, _preview(fixed), "cleanup-1")

    assert result["status"] == "succeeded"
    assert any("/qemu/" in path for _, path in api.deletes)


def test_cleanup_consumes_real_publish_failure_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request = contracts.validate_publish_request(publish_request())
    preview = contracts.build_publish_preview(
        request, runtime={"image_digest": RUNTIME_DIGEST}, observed={"vmid_free": True})
    execution = _execution(tmp_path)
    execution.environ["PVE_ARTIFACT_URL"] = request["source"]["object_ref"]

    class PublishAPI:
        def __init__(self) -> None:
            self.configured = False
            self.created_uuid = ""
            self.create_fields: dict[str, object] | None = None

        def request(self, method: str, path: str, *, fields: dict | None = None, **kwargs: object) -> object:
            if method == "GET" and path.endswith("/access/permissions"):
                return {"/vms/9001": {"VM.Audit": 1}}
            if method == "GET" and path.endswith("/cluster/resources"):
                return []
            if method == "GET" and path.endswith("/storage"):
                return [{"storage": "images", "enabled": 1, "active": 1,
                         "avail": 2**40, "content": "import,images"}]
            if method == "GET" and path.endswith("/content"):
                return []
            if method == "POST" and path.endswith("/qemu"):
                assert fields is not None
                self.create_fields = dict(fields)
                self.created_uuid = str(fields["smbios1"]).split("uuid=", 1)[1]
                return "UPID:cohe:00000000:00000000:00000002:create:100:root@pam:"
            if method == "POST" and path.endswith("/config"):
                self.configured = True
                return "UPID:cohe:00000000:00000000:00000003:config:100:root@pam:"
            if method == "GET" and path.endswith("/config"):
                if self.configured:
                    return {"smbios1": "uuid=" + self.created_uuid,
                            "scsi0": DISK, "ide2": "images:cloudinit"}
                return {"smbios1": "uuid=" + self.created_uuid,
                        "efidisk0": "images:vm-9001-efi"} if self.created_uuid else {}
            if method == "POST" and path.endswith("/template"):
                return "UPID:cohe:00000000:00000000:00000004:template:100:root@pam:"
            raise AssertionError((method, path, fields))

        def upload_file(self, *args: object, **kwargs: object) -> str:
            return "UPID:cohe:00000000:00000000:00000001:upload:100:root@pam:"

    publish_api = PublishAPI()
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: publish_api)
    monkeypatch.setattr(runtime, "_download", lambda locator, destination, digest, size: destination.write_bytes(b"x" * size))
    monkeypatch.setattr(runtime, "_verify_qcow2", lambda path, artifact: None)

    def fail_template(client: object, value: object, phase: str, node: str = "localhost", timeout: int = 300) -> dict:
        if phase == "template":
            raise ValidationError("template task failed after submission")
        return {"phase": phase, "status": "succeeded", "upid": str(value)}

    monkeypatch.setattr(runtime, "_upid", fail_template)
    with pytest.raises(ValidationError, match="template task failed"):
        runtime._publish(SimpleNamespace(), execution, request, preview, EXECUTION_ID)

    journal = json.loads((execution.outputs.path("diagnostics") / "publish-intent.json").read_text())
    upload_volid = journal["upload_volid"]
    created_uuid = next(event["smbios_uuid"] for event in journal["events"]
                        if event.get("phase") == "create" and event.get("status") == "succeeded")
    assert publish_api.create_fields is not None
    assert publish_api.create_fields["smbios1"] == "uuid=" + created_uuid
    attachments = {"scsi0": DISK, "ide2": "images:cloudinit"}
    cleanup_api = CleanupAPI(config={"template": 0, "smbios1": "uuid=" + created_uuid, **attachments},
                             volumes={upload_volid, *attachments.values()}, failed_task=True, upload=upload_volid)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: cleanup_api)
    fixed = {"target": TARGET, "original_execution_id": EXECUTION_ID,
             "original_execution_dir": "retained/publish-1",
             "original_preview_digest": preview["preview_digest"],
             "objects": [{"vmid": 9001, "smbios_uuid": created_uuid, "volumes": attachments}],
             "volumes": [upload_volid, *attachments.values()],
             "ownership_admission": {"owner": "publisher", "reference": "journal/publish-1", "activity": "stopped"}}
    cleanup_preview = {"action": "cleanup", "fixed_input": fixed, "preview_digest": PREVIEW_DIGEST,
                       "runtime": {"image_digest": RUNTIME_DIGEST}}
    result = runtime._delete_action(SimpleNamespace(files={"original_execution_dir": str(execution.outputs.root)}, options={}),
                                    execution, fixed, cleanup_preview, "cleanup-1")

    assert result["status"] == "succeeded"
    assert any("/content/" in path for _, path in cleanup_api.deletes)


def test_cleanup_recovers_real_publish_remote_observation_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_pve_template_publisher import API

    request = contracts.validate_publish_request(publish_request())
    preview = contracts.build_publish_preview(
        request, runtime={"image_digest": RUNTIME_DIGEST}, observed={"vmid_free": True})
    execution = _execution(tmp_path)
    execution.environ["PVE_ARTIFACT_URL"] = request["source"]["object_ref"]
    api = API()
    original_content = runtime._storage_content
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    monkeypatch.setattr(runtime, "_download", lambda locator, destination, digest, size: destination.write_bytes(b"x" * size))
    monkeypatch.setattr(runtime, "_verify_qcow2", lambda path, artifact: None)

    def fail_after_template(client: Any, node: str, storage: str) -> Any:
        if api.config.get("template") == 1:
            raise runtime.OperationFailed("staging observation unavailable")
        return original_content(client, node, storage)

    monkeypatch.setattr(runtime, "_storage_content", fail_after_template)
    published = runtime._publish(SimpleNamespace(), execution, request, preview, EXECUTION_ID)

    assert published["status"] == "unknown"
    journal_path = execution.outputs.path("diagnostics") / "publish-intent.json"
    journal = json.loads(journal_path.read_text())
    remote_events = [event for event in journal["events"] if event.get("phase") == "remote-cleanup"]
    assert remote_events[-1]["status"] == "unknown"
    assert "upid" not in remote_events[-1]

    upload_volid = journal["upload_volid"]
    cleanup_api = CleanupAPI(config={"template": 1, "smbios1": api.config["smbios1"],
                                     "scsi0": "images:base-9001-disk-0"}, volumes={upload_volid})
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: cleanup_api)
    monkeypatch.setattr(runtime, "_storage_content", original_content)
    fixed = _fixed(objects=[], volumes=[upload_volid], preview_digest=preview["preview_digest"])

    result = runtime._delete_action(
        _selected(execution.outputs.root), execution, fixed, _preview(fixed), "cleanup-1")

    assert result["status"] == "succeeded"
    assert any("/content/" in path for _, path in cleanup_api.deletes)


def test_retire_rejects_extra_current_volume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = {"kind": "pve-template-record", "schema_version": 2, "record_id": "v1-9001",
              "target": TARGET, "node": "cohe", "vmid": 9001, "smbios_uuid": "template-uuid",
              "volumes": {"scsi0": DISK}, "configuration": {"scsi0": DISK}, "origin": "publication",
              "execution_id": EXECUTION_ID, "artifact_digest": "sha256:" + "c" * 64,
              "verification": {"template_config": "passed"}}
    fixed = {"target": TARGET, "template_record": record,
             "ownership_admission": {"owner": "publisher", "reference": "record", "activity": "stopped"},
             "retirement_admission": {"authorized": True, "dependencies_resolved": True, "reference": "review"}}
    api = CleanupAPI(config={"template": 1, "smbios1": "uuid=template-uuid", "scsi0": DISK,
                             "scsi1": "images:extra"}, volumes=set())
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)

    with pytest.raises(ValidationError, match="exactly"):
        runtime._delete_action(SimpleNamespace(files={}, options={}), execution, fixed,
                               _preview(fixed, action="retire"), "retire-1")
    assert api.deletes == []


def test_retire_rejects_current_config_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = {"kind": "pve-template-record", "schema_version": 2, "record_id": "v1-9001",
              "target": TARGET, "node": "cohe", "vmid": 9001, "smbios_uuid": "template-uuid",
              "volumes": {"scsi0": DISK}, "configuration": {"scsi0": DISK}, "origin": "publication",
              "execution_id": EXECUTION_ID, "artifact_digest": "sha256:" + "c" * 64,
              "verification": {"template_config": "passed"}}
    fixed = {"target": TARGET, "template_record": record,
             "ownership_admission": {"owner": "publisher", "reference": "record", "activity": "stopped"},
             "retirement_admission": {"authorized": True, "dependencies_resolved": True, "reference": "review"}}
    api = CleanupAPI(config={"template": 1, "lock": "backup", "smbios1": "uuid=template-uuid", "scsi0": DISK},
                     volumes=set())
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)

    with pytest.raises(ValidationError, match="locked"):
        runtime._delete_action(SimpleNamespace(files={}, options={}), execution, fixed,
                               _preview(fixed, action="retire"), "retire-1")
    assert api.deletes == []
