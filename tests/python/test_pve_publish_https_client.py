"""Exercise HTTP serialization and trust at a real local TLS boundary."""

from __future__ import annotations

import hashlib
import json
import shutil
import ssl
import subprocess
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from iaas.pve_template.runtime import PveHttpsClient
from iaas.runtime_execution.execution import OperationFailed


@pytest.fixture
def https_api(tmp_path):
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("local TLS fixture requires openssl")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
         "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1",
         "-keyout", str(key), "-out", str(cert)],
        check=True, capture_output=True,
    )
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append((self.path, dict(self.headers), body))
            if self.path == "/reject-large":
                self.send_response(413)
                self.end_headers()
                return
            if self.path == "/redirect":
                self.send_response(307)
                self.send_header("Location", "/must-not-receive-token")
                self.end_headers()
                return
            response = json.dumps({"data": "UPID:local:task"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}", cert, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_post_fields_cross_tls_as_form_data_without_environment_proxy(https_api, monkeypatch):
    endpoint, cert, requests = https_api
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("no_proxy", "")
    client = PveHttpsClient(endpoint, "test@pve!publisher=synthetic", ca_file=str(cert))
    fields = {"vmid": 9001, "scsi0": "local:0,import-from=images:import/source.qcow2"}
    assert client.request("POST", "/api2/json/nodes/cohe/qemu", fields=fields) == "UPID:local:task"
    path, headers, body = requests[0]
    assert path == "/api2/json/nodes/cohe/qemu"
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert parse_qs(body.decode()) == {key: [str(value)] for key, value in fields.items()}


def test_token_request_refuses_redirect_and_untrusted_certificate(https_api):
    endpoint, cert, requests = https_api
    client = PveHttpsClient(endpoint, "synthetic-secret", ca_file=str(cert))
    with pytest.raises(OperationFailed) as error:
        client.request("POST", "/redirect", fields={"vmid": 9001})
    assert "synthetic-secret" not in str(error.value)
    assert [row[0] for row in requests] == ["/redirect"]
    with pytest.raises(OperationFailed):
        PveHttpsClient(endpoint, "synthetic-secret").request("POST", "/untrusted")
    assert len(requests) == 1


def test_import_upload_streams_file_and_preserves_multipart_fields(https_api, tmp_path, monkeypatch):
    endpoint, cert, requests = https_api
    disk = tmp_path / "source.qcow2"
    payload = b"qcow2-fixture\x00" * 180000
    disk.write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    original_open = Path.open
    reads = []

    class BoundedReader:
        def __enter__(self):
            self.source = original_open(disk, "rb")
            return self

        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024, "disk upload must use bounded reads"
            reads.append(size)
            return self.source.read(size)

        def __exit__(self, *_args):
            self.source.close()

    def guarded_open(path, *args, **kwargs):
        return BoundedReader() if path == disk else original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    client = PveHttpsClient(endpoint, "synthetic-secret", ca_file=str(cert))
    assert client.upload_file("/api2/json/nodes/cohe/storage/images/upload", disk,
                              "publish-1.qcow2", checksum) == "UPID:local:task"
    _, headers, body = requests[0]
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {headers['Content-Type']}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    parts = {part.get_param("name", header="Content-Disposition"): part for part in message.iter_parts()}
    assert int(headers["Content-Length"]) == len(body)
    assert parts["content"].get_payload(decode=True) == b"import"
    assert parts["checksum"].get_payload(decode=True) == checksum.encode()
    assert parts["checksum-algorithm"].get_payload(decode=True) == b"sha256"
    assert parts["filename"].get_filename() == "publish-1.qcow2"
    assert parts["filename"].get_payload(decode=True) == payload
    assert len(reads) >= 3


def test_import_upload_rejects_http_413_without_returning_a_task(https_api, tmp_path):
    endpoint, cert, requests = https_api
    disk = tmp_path / "source.qcow2"
    disk.write_bytes(b"disk")
    client = PveHttpsClient(endpoint, "synthetic-secret", ca_file=str(cert))
    with pytest.raises(OperationFailed) as error:
        client.upload_file("/reject-large", disk, "publish-1.qcow2", "a" * 64)
    assert "synthetic-secret" not in str(error.value)
    assert len(requests) == 1
