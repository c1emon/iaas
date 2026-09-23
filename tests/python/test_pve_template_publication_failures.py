from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from iaas_automation.pve_template import contracts, runtime
from test_image_publish_contracts import request as publish_request
from test_pve_template_publisher import API, Outputs


def publish_setup(tmp_path, monkeypatch, api):
    request = contracts.validate_publish_request(publish_request())
    preview = contracts.build_publish_preview(request, runtime={"image_digest": "runtime@sha256:" + "a" * 64})
    outputs = Outputs(tmp_path / "outputs")
    execution = SimpleNamespace(outputs=outputs, environ={"PVE_ARTIFACT_URL": request["source"]["object_ref"]})
    monkeypatch.setattr(runtime, "_client", lambda *args: api)
    monkeypatch.setattr(runtime, "_download", lambda url, path, digest, size: path.write_bytes(b"disk"))
    monkeypatch.setattr(runtime, "_verify_qcow2", lambda *args: None)
    return request, preview, execution


@pytest.mark.parametrize("remote_unknown", [False, True])
def test_cleanup_failure_preserves_publication_and_unknown_precedence(tmp_path, monkeypatch, remote_unknown):
    api = API()
    request, preview, execution = publish_setup(tmp_path, monkeypatch, api)
    original_content = runtime._storage_content

    def content(client, node, storage):
        if remote_unknown and client.config.get("template") == 1:
            raise runtime.OperationFailed("staging observation unavailable")
        return original_content(client, node, storage)

    original_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path.suffix == ".qcow2":
            raise OSError("local staging cleanup failed")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(runtime, "_storage_content", content)
    monkeypatch.setattr(Path, "unlink", unlink)
    result = runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")
    assert result["publication"] == "succeeded"
    assert result["collection"]["status"] == "succeeded"
    assert result["status"] == ("unknown" if remote_unknown else "succeeded")
    assert result["cleanup"]["status"] == ("unknown" if remote_unknown else "failed")
    assert result["cleanup"]["inactive"] is not remote_unknown
    assert result["cleanup"]["todo"]["original_execution_id"] == "publish-1"


def test_upload_response_loss_retains_write_intent_and_unknown_effects(tmp_path, monkeypatch):
    class LostResponse(API):
        def upload_file(self, *args):
            raise runtime.OperationFailed("response lost after upload")

    request, preview, execution = publish_setup(tmp_path, monkeypatch, LostResponse())
    with pytest.raises(runtime.OperationFailed):
        runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")
    intent = json.loads((execution.outputs.path("diagnostics") / "publish-intent.json").read_text())
    assert intent["target"] == request["target"]
    upload_events = [event for event in intent["events"] if event["phase"] == "upload"]
    assert [event["status"] for event in upload_events] == ["intent", "failed"]
    assert upload_events[-1]["reason"] == "upload-request-failed"
    result = runtime._failure_result(intent, "publish-1", preview["preview_digest"], request["artifact_digest"])
    assert result["effects"]["pve"] == "unknown" and result["publication"] == "unknown"
    assert result["collection"]["status"] == "succeeded"


def test_upload_enospc_journals_safe_category_and_unknown_effects(tmp_path, monkeypatch):
    class NoSpace(API):
        def upload_file(self, *args, **kwargs):
            raise runtime.OperationFailed("PVE API upload request failed (os-error-28)")

    request, preview, execution = publish_setup(tmp_path, monkeypatch, NoSpace())
    with pytest.raises(runtime.OperationFailed):
        runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")
    intent = json.loads((execution.outputs.path("diagnostics") / "publish-intent.json").read_text())
    upload_failed = [event for event in intent["events"]
                     if event["phase"] == "upload" and event["status"] == "failed"]
    assert upload_failed[0]["reason"] == "upload-os-error-28"
    assert intent["status"] == "unknown"
    result = runtime._failure_result(intent, "publish-1", preview["preview_digest"], request["artifact_digest"])
    assert result["effects"]["pve"] == "unknown"


@pytest.mark.parametrize("available", [0, None])
def test_local_space_preflight_rejects_known_shortfall_only(tmp_path, monkeypatch, available):
    api = API()
    request, preview, execution = publish_setup(tmp_path, monkeypatch, api)

    def disk_usage(path):
        if available is None:
            raise OSError("space telemetry unavailable")
        return SimpleNamespace(free=available)

    monkeypatch.setattr(runtime.shutil, "disk_usage", disk_usage)
    if available == 0:
        with pytest.raises(Exception, match="insufficient known capacity"):
            runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")
        assert all(method == "GET" for method, *_ in api.calls)
    else:
        assert runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")["publication"] == "succeeded"


def test_template_conversion_cannot_silently_change_requested_disk_slot():
    request = contracts.validate_publish_request(publish_request())
    with pytest.raises(Exception, match="requested boot slot"):
        runtime._final_disk({"virtio0": "images:base-9001-disk-0"}, request)


def test_verified_template_must_match_requested_hardware(tmp_path, monkeypatch):
    class ChangedConfig(API):
        def request(self, method, path, **kwargs):
            result = super().request(method, path, **kwargs)
            if method == "POST" and path.endswith("/template"):
                self.config["memory"] = 1024
            return result

    request, preview, execution = publish_setup(tmp_path, monkeypatch, ChangedConfig())
    with pytest.raises(Exception, match="does not match the fixed publication request"):
        runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")


def test_download_enospc_has_no_remote_effects_and_removes_partial_file(tmp_path, monkeypatch):
    import errno
    import io

    api = API()
    download = runtime._download
    request, preview, execution = publish_setup(tmp_path, monkeypatch, api)
    original_open = Path.open

    class FullOutput:
        def __init__(self, path):
            self.output = original_open(path, "wb")

        def __enter__(self):
            return self

        def write(self, data):
            self.output.write(data[:2])
            raise OSError(errno.ENOSPC, "No space left on device")

        def __exit__(self, *args):
            self.output.close()

    def open_file(path, mode="r", *args, **kwargs):
        if path.suffix == ".qcow2" and mode == "wb":
            return FullOutput(path)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(runtime, "_download", download)
    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(runtime, "build_opener", lambda *args: SimpleNamespace(open=lambda *args, **kwargs: io.BytesIO(b"disk")))
    with pytest.raises(runtime.OperationFailed, match="artifact download failed"):
        runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")
    intent = json.loads((execution.outputs.path("diagnostics") / "publish-intent.json").read_text())
    result = runtime._failure_result(intent, "publish-1", preview["preview_digest"], request["artifact_digest"])
    assert result["publication"] == "failed"
    assert result["effects"]["pve"] == "none"
    assert all(method == "GET" for method, *_ in api.calls)
    assert not list(execution.outputs.path("work").rglob("*.qcow2"))
    assert intent["events"][0]["phase"] == "download" and intent["events"][0]["status"] == "intent"
    assert intent["events"][1]["phase"] == "download" and intent["events"][1]["status"] == "failed"
    assert intent["events"][1]["reason"] == "artifact download failed (os-error-28)"


def test_download_http_failure_records_status_without_locator(tmp_path, monkeypatch):
    from urllib.error import HTTPError

    class FailingOpener:
        def open(self, *args, **kwargs):
            raise HTTPError("https://objects.invalid/private?token=redacted", 503, "busy", {}, None)

    monkeypatch.setattr(runtime, "build_opener", lambda *args: FailingOpener())
    destination = tmp_path / "disk.qcow2"
    with pytest.raises(runtime.OperationFailed, match=r"artifact download failed \(HTTP 503\)"):
        runtime._download("https://objects.invalid/private?token=redacted", destination, "0" * 64, 1)
    assert not destination.exists()


@pytest.mark.parametrize("failed_phase", ["artifact-verify", "upload-target"])
def test_preupload_failure_journals_bounded_phase_and_known_local_effects(tmp_path, monkeypatch, failed_phase):
    api = API()
    request, preview, execution = publish_setup(tmp_path, monkeypatch, api)
    if failed_phase == "artifact-verify":
        monkeypatch.setattr(runtime, "_verify_qcow2",
                            lambda *args: (_ for _ in ()).throw(runtime.OperationFailed("private-token")))
        expected_reason = "artifact-format-verification-failed"
    else:
        monkeypatch.setattr(runtime, "_assert_upload_target_free",
                            lambda *args: (_ for _ in ()).throw(runtime.ValidationError("private-token")))
        expected_reason = "upload-target-rejected"

    with pytest.raises(Exception):
        runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")

    intent = json.loads((execution.outputs.path("diagnostics") / "publish-intent.json").read_text())
    failed = [event for event in intent["events"] if event["phase"] == failed_phase and event["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["reason"] == expected_reason
    assert intent["status"] == "failed"
    assert not any(event["phase"] == "upload" for event in intent["events"])
    assert "private-token" not in json.dumps(intent)
    result = runtime._failure_result(intent, "publish-1", preview["preview_digest"], request["artifact_digest"])
    assert result["status"] == "failed" and result["effects"] == {"pve": "none", "staging": "none"}
    assert all(method == "GET" for method, *_ in api.calls)


def test_same_artifact_supports_two_admitted_publications_without_rebuild(tmp_path, monkeypatch):
    """Two independent apply executions may consume one immutable artifact."""
    runtime_digest = "runtime@sha256:" + "a" * 64
    artifact_bytes = b"same-delivered-disk"
    download_calls: list[tuple[str, str]] = []

    class TargetAPI(API):
        def __init__(self, vmid: int) -> None:
            super().__init__()
            self.vmid = vmid

        def request(self, method, path, **kwargs):
            result = super().request(method, path, **kwargs)
            if method == "GET" and path.endswith("/access/permissions"):
                return {f"/vms/{self.vmid}": {"VM.Audit": 1}}
            if method == "POST" and path.endswith("/config"):
                self.config["scsi0"] = f"images:vm-{self.vmid}-disk-0,size=8G"
            if method == "POST" and path.endswith("/template"):
                self.config["scsi0"] = f"images:base-{self.vmid}-disk-0,size=8G"
            return result

    def download(locator, destination, digest, size):
        download_calls.append((digest, destination.name))
        destination.write_bytes(artifact_bytes)

    monkeypatch.setattr(runtime, "_download", download)
    monkeypatch.setattr(runtime, "_verify_qcow2", lambda *args: None)

    executions = []
    for execution_id, vmid in (("publish-a", 9001), ("publish-b", 9002)):
        raw_request = deepcopy(publish_request())
        raw_request["vmid"] = vmid
        raw_request["name"] = f"debian-template-{vmid}"
        request = contracts.validate_publish_request(raw_request)
        preview = contracts.build_publish_preview(request, runtime={"image_digest": runtime_digest},
                                                  observed={"vmid_free": True})
        admission = {
            "schema_version": 1, "execution_id": execution_id,
            "plan_digest": preview["preview_digest"].removeprefix("sha256:"),
            "target": request["target"], "approved": True,
            "consumption": {"reserved": True, "reservation_id": f"reservation-{execution_id}"},
            "pending": {"record_id": f"pending-{execution_id}"},
            "serialization": {"held": True, "context_id": f"lock-{execution_id}"},
        }
        preview_path = tmp_path / f"{execution_id}-preview.json"
        preview_path.write_text(json.dumps(preview))
        outputs = Outputs(tmp_path / execution_id)
        outputs.path("generated").mkdir()
        execution = SimpleNamespace(
            outputs=outputs,
            environ={"PVE_ARTIFACT_URL": request["source"]["object_ref"]},
            api=TargetAPI(vmid),
            finished=[],
        )
        execution.finish = execution.finished.append
        selected = SimpleNamespace(options={"action": "publish", "preview_digest": preview["preview_digest"],
                                             "admission": admission}, files={"preview": preview_path})
        monkeypatch.setattr(runtime, "_client", lambda _selected, current, _target: current.api)

        runtime.run(selected, "apply", "cohe", execution, image_digest=runtime_digest,
                    execution_id=execution_id)
        assert execution.finished[-1]["status"] == "succeeded"
        result = json.loads((outputs.path("diagnostics") / "result.json").read_text())
        assert result["artifact_digest"] == request["artifact_digest"]
        assert result["publication"] == "succeeded"
        executions.append((request, result))

    assert executions[0][0]["artifact_digest"] == executions[1][0]["artifact_digest"]
    assert [result["execution_id"] for _, result in executions] == ["publish-a", "publish-b"]
    assert [result["template_record"]["vmid"] for _, result in executions] == [9001, 9002]
    assert [digest for digest, _ in download_calls] == ["b" * 64, "b" * 64]
    assert [name for _, name in download_calls] == [
        "publish-a-" + "b" * 64 + ".qcow2", "publish-b-" + "b" * 64 + ".qcow2"
    ]
