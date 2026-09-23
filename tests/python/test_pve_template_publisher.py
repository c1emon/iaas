from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from iaas_automation.pve_template import contracts, runtime

from test_image_publish_contracts import request as publish_request


class Outputs:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True)
        for name in ("diagnostics", "work"):
            (root / name).mkdir()

    def path(self, category: str) -> Path:
        return self.root / category


class API:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self.config = {
            "smbios1": "uuid=template-uuid",
            "scsihw": "virtio-scsi-single",
            "cores": 2,
            "memory": 2048,
        }

    def upload_file(self, path, file, filename, checksum):
        self.calls.append(("UPLOAD", path, {"filename": filename, "checksum": checksum}))
        return "/nodes/cohe/tasks/UPID:cohe:00000000:00000000:00000001:upload:100:root@pam:"

    def request(self, method, path, *, fields=None, **kwargs):
        self.calls.append((method, path, dict(fields) if fields else None))
        if method == "GET" and path.endswith("/access/permissions"):
            if isinstance(fields, dict) and isinstance(fields.get("path"), str) and fields["path"].startswith("/storage/"):
                return {fields["path"]: {"Datastore.Audit": 1, "Datastore.Allocate": 1,
                                          "Datastore.AllocateTemplate": 1,
                                          "Datastore.AllocateSpace": 1}}
            return {"/vms/9001": {"VM.Audit": 1}}
        if method == "GET" and path.endswith("/cluster/resources"):
            return []
        if method == "GET" and path.endswith("/storage"):
            return [{"storage": "images", "enabled": 1, "active": 1,
                     "content": "images,import", "avail": 32 * 1024 ** 3}]
        if method == "POST" and path.endswith("/qemu"):
            self.config.update({key: value for key, value in fields.items() if key != "vmid"})
            return "/nodes/cohe/tasks/UPID:cohe:00000000:00000000:00000002:create:100:root@pam:"
        if method == "POST" and path.endswith("/config"):
            self.config.update(fields)
            self.config["scsi0"] = "images:vm-9001-disk-0,size=8G"
            self.config["ide2"] = "images:vm-9001-cloudinit,media=cdrom"
            return "/nodes/cohe/tasks/UPID:cohe:00000000:00000000:00000003:config:100:root@pam:"
        if method == "POST" and path.endswith("/template"):
            self.config["template"] = 1
            self.config["scsi0"] = "images:base-9001-disk-0,size=8G"
            return "/nodes/cohe/tasks/UPID:cohe:00000000:00000000:00000004:template:100:root@pam:"
        if method == "GET" and path.endswith("/status"):
            return {"status": "stopped", "exitstatus": "OK"}
        if method == "GET" and path.endswith("/config"):
            return dict(self.config)
        if method == "GET" and path.endswith("/content"):
            return []
        raise AssertionError((method, path, fields))


def test_publish_uses_config_import_from_and_remote_residue_check(tmp_path, monkeypatch):
    request = publish_request()
    preview = contracts.build_publish_preview(
        request,
        runtime={"image_digest": "registry.invalid/runtime@sha256:" + "a" * 64},
        observed={"vmid_free": True},
    )
    api = API()
    outputs = Outputs(tmp_path / "outputs")
    execution = SimpleNamespace(outputs=outputs, environ={"PVE_ARTIFACT_URL": request["source"]["object_ref"]})
    selected = SimpleNamespace()

    def download(locator, destination, digest, size):
        destination.write_bytes(b"qcow2-placeholder")

    monkeypatch.setattr(runtime, "_client", lambda selected, execution, target: api)
    monkeypatch.setattr(runtime, "_download", download)
    monkeypatch.setattr(runtime, "_verify_qcow2", lambda path, artifact: None)

    result = runtime._publish(selected, execution, contracts.validate_publish_request(request), preview, "exec-1")

    config_calls = [call for call in api.calls if call[0] == "POST" and call[1].endswith("/config")]
    assert len(config_calls) == 1
    fields = config_calls[0][2]
    assert fields is not None
    assert fields["scsi0"] == "images:0,import-from=images:import/exec-1-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.qcow2"
    assert "template" not in fields
    assert "hostname" not in fields
    assert not any("importdisk" in call[1] for call in api.calls)
    config_index = next(i for i, call in enumerate(api.calls) if call[1].endswith("/config") and call[0] == "POST")
    template_index = next(i for i, call in enumerate(api.calls) if call[1].endswith("/template"))
    assert config_index < template_index
    assert result["publication"] == "succeeded"
    assert result["template_record"]["volumes"]["scsi0"] == "images:base-9001-disk-0"
    assert "scsihw" not in result["template_record"]["volumes"]
    assert "efidisk0" not in result["template_record"]["volumes"]
    assert "ide2" not in result["template_record"]["volumes"]
    assert result["template_record"]["configuration"]["scsihw"] == "virtio-scsi-single"
    assert (outputs.path("diagnostics") / "publish-intent.json").is_file()


def test_upid_requires_valid_identity_and_explicit_ok_exitstatus() -> None:
    class StatusAPI:
        def request(self, method, path, **kwargs):
            return {"status": "stopped"}

    with pytest.raises(Exception, match="valid UPID"):
        runtime._upid(StatusAPI(), "UPID:short", "create", node="cohe")
    valid = "UPID:cohe:00000000:00000000:00000001:create:100:root@pam:"
    with pytest.raises(Exception, match="did not finish successfully"):
        runtime._upid(StatusAPI(), valid, "create", node="cohe")

    empty_task_id = "UPID:cohe:00267DCD:0AA89612:6AB35280:imgcopy::pve-ops@pve!opentofu:"
    assert runtime._normalize_upid(empty_task_id, "cohe") == empty_task_id


def test_observed_storage_with_shared_staging_and_images_requires_both_capabilities() -> None:
    request = contracts.validate_publish_request(publish_request())

    class StorageAPI:
        def request(self, method, path, *, fields=None):
            if path.endswith("/access/permissions"):
                if isinstance(fields, dict) and isinstance(fields.get("path"), str) and fields["path"].startswith("/storage/"):
                    return {fields["path"]: {"Datastore.Audit": 1, "Datastore.Allocate": 1,
                                              "Datastore.AllocateTemplate": 1,
                                              "Datastore.AllocateSpace": 1}}
                return {"/vms/9001": {"VM.Audit": 1}}
            if path.endswith("/cluster/resources"):
                return []
            return [{"storage": "images", "enabled": 1, "active": 1, "avail": 2**40,
                     "content": "import"}]

    with pytest.raises(Exception, match="does not support images content"):
        runtime._observed(None, StorageAPI(), request["target"], request)


def test_observed_accepts_zero_storage_permission_propagation_value() -> None:
    request = contracts.validate_publish_request(publish_request())

    class PermissionAPI:
        def request(self, method, path, *, fields=None):
            if path.endswith("/access/permissions"):
                if fields and fields.get("path") == "/vms/9001":
                    return {"/vms/9001": {"VM.Audit": 1}}
                return {"/storage/images": {"Datastore.Audit": 1, "Datastore.Allocate": 0,
                                             "Datastore.AllocateTemplate": 0,
                                             "Datastore.AllocateSpace": 0}}
            if path.endswith("/cluster/resources"):
                return []
            if path.endswith("/storage"):
                return [{"storage": "images", "enabled": 1, "active": 1,
                         "content": "images,import", "avail": 2**40}]
            raise AssertionError((method, path, fields))

    observed = runtime._observed(None, PermissionAPI(), request["target"], request)
    assert observed["vmid_free"] is True


def test_storage_content_does_not_send_invalid_combined_content_filter() -> None:
    calls: list[dict | None] = []

    class StrictContentAPI:
        def request(self, method, path, *, fields=None):
            calls.append(fields)
            if fields == {"content": "import,images"}:
                raise runtime.OperationFailed("PVE API HTTP 400 errors.content invalid content type")
            return [{"volid": "images:import/example.qcow2"}]

    content = runtime._storage_content(StrictContentAPI(), "cohe", "images")
    assert content == [{"volid": "images:import/example.qcow2"}]
    assert calls == [None]


def test_pve_http_error_preserves_status_without_response_body() -> None:
    client = runtime.PveHttpsClient("https://pve.example.invalid:8006", "user!token=secret")

    class FailingOpener:
        def open(self, *args, **kwargs):
            raise HTTPError("https://pve.example.invalid/private", 400, "invalid content", {}, None)

    client.opener = FailingOpener()
    with pytest.raises(runtime.OperationFailed, match=r"PVE API GET request failed \(HTTP 400\)") as error:
        client.request("GET", "/api2/json/nodes/cohe/storage/images/content")
    assert "invalid content" not in str(error.value)
    assert "private" not in str(error.value)


def test_upload_multipart_uses_quoted_headers_and_pve_field_order(tmp_path, monkeypatch) -> None:
    disk = tmp_path / "image.qcow2"
    disk.write_bytes(b"qcow2")
    sent: list[bytes] = []

    class Response:
        status = 200

        def read(self):
            return b'{"data":"UPID:cohe:task"}'

    class Connection:
        def putrequest(self, *args, **kwargs):
            pass

        def putheader(self, *args, **kwargs):
            pass

        def endheaders(self):
            pass

        def send(self, data):
            sent.append(data)

        def getresponse(self):
            return Response()

        def close(self):
            pass

    connection = Connection()
    client = runtime.PveHttpsClient("https://pve.example.invalid:8006", "user!token=secret")
    monkeypatch.setattr(runtime.http.client, "HTTPSConnection", lambda *args, **kwargs: connection)
    client.upload_file("/api2/json/upload", disk, disk.name, "a" * 64)
    body = b"".join(sent)
    content = body.index(b'name="content"')
    checksum_algorithm = body.index(b'name="checksum-algorithm"')
    checksum = body.index(b'name="checksum"')
    filename = body.index(b'name="filename"; filename="image.qcow2"')
    assert content < checksum_algorithm < checksum < filename
    assert b"name=filename; filename=image.qcow2" not in body


@pytest.mark.parametrize("failure, expected", [("http", "HTTP 507"), ("brokenpipe", "os-error-32")])
def test_upload_file_preserves_safe_failure_category(tmp_path, monkeypatch, failure, expected) -> None:
    disk = tmp_path / "image.qcow2"
    disk.write_bytes(b"qcow2")

    class Connection:
        def putrequest(self, *args, **kwargs):
            pass

        def putheader(self, *args, **kwargs):
            pass

        def endheaders(self):
            pass

        def send(self, data):
            if failure == "brokenpipe":
                raise BrokenPipeError(32, "peer closed")

        def getresponse(self):
            return SimpleNamespace(status=507, read=lambda: b"")

        def close(self):
            pass

    client = runtime.PveHttpsClient("https://pve.example.invalid:8006", "user!token=secret")
    monkeypatch.setattr(runtime.http.client, "HTTPSConnection", lambda *args, **kwargs: Connection())
    with pytest.raises(runtime.OperationFailed, match=expected) as error:
        client.upload_file("/api2/json/upload", disk, disk.name, "a" * 64)
    assert "secret" not in str(error.value)
