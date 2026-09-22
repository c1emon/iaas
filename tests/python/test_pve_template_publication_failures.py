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
    assert intent["events"][-1]["phase"] == "upload" and intent["events"][-1]["status"] == "intent"
    result = runtime._failure_result(intent, "publish-1", preview["preview_digest"], request["artifact_digest"])
    assert result["effects"]["pve"] == "unknown" and result["publication"] == "unknown"
    assert result["collection"]["status"] == "succeeded"


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
