"""Real boto3 reads against a local, write-observing S3 substitute."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

import pytest

from iaas_automation.runtime_execution.pve_state import BotoS3ReadTransport, S3StateObserver
from iaas_automation.runtime_execution.state import S3Backend


STATE = {
    "version": 4,
    "terraform_version": "1.12.6",
    "serial": 7,
    "lineage": "synthetic-lineage",
    "resources": [],
}


class _S3Stub:
    def __init__(self, *, status: int = 200, code: str | None = None):
        self.status = status
        self.code = code
        self.requests: list[dict[str, object]] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def _record(self) -> None:
                stub.requests.append({
                    "method": self.command,
                    "path": unquote(urlsplit(self.path).path),
                    "authorization": self.headers.get("Authorization", ""),
                })

            def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
                self._record()
                if stub.status == 200:
                    body = json.dumps(STATE).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                else:
                    body = (f"<?xml version=\"1.0\"?><Error><Code>{stub.code}</Code>"
                            f"<Message>synthetic</Message></Error>").encode()
                    self.send_response(stub.status)
                    self.send_header("Content-Type", "application/xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _unexpected_write(self) -> None:
                self._record()
                self.send_error(405)

            do_POST = _unexpected_write  # noqa: N815 - stdlib handler API
            do_PUT = _unexpected_write  # noqa: N815 - stdlib handler API
            do_DELETE = _unexpected_write  # noqa: N815 - stdlib handler API

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self) -> "_S3Stub":
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _backend(endpoint: str, workspace: str = "default") -> S3Backend:
    config = {
        "bucket": "synthetic-bucket",
        "key": "root.tfstate",
        "region": "us-east-1",
        "endpoint": endpoint,
        "workspace_key_prefix": "env:",
        "use_path_style": True,
        "use_lockfile": True,
    }
    return S3Backend(config, workspace)


def _credential_files(tmp_path: Path) -> tuple[Path, Path]:
    credentials = tmp_path / "mapped-credentials"
    credentials.write_text(
        "[mapped-profile]\n"
        "aws_access_key_id = mapped-access\n"
        "aws_secret_access_key = mapped-secret\n"
    )
    credentials.chmod(0o600)
    ca_bundle = tmp_path / "mapped-ca.pem"
    ca_bundle.write_text("synthetic CA bundle")
    ca_bundle.chmod(0o600)
    return credentials, ca_bundle


def test_boto_get_uses_explicit_endpoint_path_style_workspace_key_and_mapped_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials, ca_bundle = _credential_files(tmp_path)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ambient-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "ambient-secret")
    monkeypatch.setenv("AWS_PROFILE", "ambient-profile")
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "http://127.0.0.1:1/ambient")
    monkeypatch.setenv("AWS_CA_BUNDLE", str(tmp_path / "ambient-ca.pem"))

    with _S3Stub() as stub:
        environ = {
            "AWS_PROFILE": "mapped-profile",
            "AWS_SHARED_CREDENTIALS_FILE": str(credentials),
            "AWS_CA_BUNDLE": str(ca_bundle),
        }
        transport = BotoS3ReadTransport(environ)
        observed_verify: list[object] = []
        original_client = transport._boto3.session.Session.client

        def client_spy(session: object, *args: object, **kwargs: object):
            observed_verify.append(kwargs.get("verify"))
            return original_client(session, *args, **kwargs)

        monkeypatch.setattr(transport._boto3.session.Session, "client", client_spy)
        default = S3StateObserver(transport).observe(_backend(stub.endpoint))
        review = S3StateObserver(transport).observe(_backend(stub.endpoint, "review"))

    assert default.status == "present"
    assert default.key == "root.tfstate"
    assert review.status == "present"
    assert review.key == "env:/review/root.tfstate"
    assert [request["method"] for request in stub.requests] == ["GET", "GET"]
    assert [request["path"] for request in stub.requests] == [
        "/synthetic-bucket/root.tfstate",
        "/synthetic-bucket/env:/review/root.tfstate",
    ]
    assert all("Credential=mapped-access/" in str(request["authorization"])
               for request in stub.requests)
    assert all("ambient-access" not in str(request["authorization"])
               for request in stub.requests)
    assert observed_verify == [str(ca_bundle), str(ca_bundle)]


@pytest.mark.parametrize(
    ("status", "code", "expected_status", "expected_reason"),
    [
        (404, "NoSuchKey", "absent", "missing_object"),
        (404, "NoSuchBucket", "error", "observation_error"),
        (403, "AccessDenied", "error", "access_denied"),
    ],
)
def test_boto_read_classifies_s3_errors_and_never_writes(
    tmp_path: Path, status: int, code: str, expected_status: str, expected_reason: str,
) -> None:
    credentials, _ = _credential_files(tmp_path)
    environ = {
        "AWS_SHARED_CREDENTIALS_FILE": str(credentials),
        "AWS_PROFILE": "mapped-profile",
    }
    with _S3Stub(status=status, code=code) as stub:
        observation = S3StateObserver(BotoS3ReadTransport(environ)).observe(_backend(stub.endpoint, "review"))

    assert observation.status == expected_status
    assert observation.reason == expected_reason
    assert len(stub.requests) == 1
    assert stub.requests[0]["method"] == "GET"
    assert not any(request["method"] in {"POST", "PUT", "DELETE", "PATCH"}
                   for request in stub.requests)
