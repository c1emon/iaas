"""Offline HTTPS transport checks, including noisy server-side plugin logs."""

import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import runpy
import ssl
import subprocess
import threading
from types import SimpleNamespace

import pytest


PROBE = Path(__file__).resolve().parents[2] / "automation/pve-node/bin/iaas-pve-storage-status"
TICKET = "PVE:root@pam:synthetic-ticket"


@pytest.fixture
def probe(tmp_path, monkeypatch):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=synthetic-pve", "-keyout", str(key), "-out", str(cert)],
                   check=True, capture_output=True)
    state = {"status": 200, "body": json.dumps({"data": {"content": "images", "enabled": 1,
             "active": 1, "avail": 9999999999, "private_plugin_field": "not-for-output"}}).encode(),
             "content_type": "application/json", "requests": [], "auth_calls": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"].append((self.path, self.headers.get("Cookie")))
            print("TrueNAS synthetic plugin writes to server stdout")
            self.send_response(state["status"])
            self.send_header("Content-Type", state["content_type"])
            self.end_headers()
            self.wfile.write(state["body"])

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    read = runpy.run_path(str(PROBE))["storage_status"]
    env = read.__globals__
    env["CERTIFICATES"] = (cert,)
    monkeypatch.setattr(env["os"], "geteuid", lambda: 0)
    monkeypatch.setattr(env["socket"], "gethostname", lambda: "cohe.example.invalid")
    original = http.client.HTTPSConnection

    def connect(host, port, **kwargs):
        assert (host, port) == ("127.0.0.1", 8006)
        assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
        assert kwargs["context"].verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
        return original(host, server.server_port, **kwargs)

    env["http"] = SimpleNamespace(client=SimpleNamespace(
        HTTPSConnection=connect, HTTPException=http.client.HTTPException))

    def authenticate(argv, **kwargs):
        state["auth_calls"].append(argv)
        assert TICKET not in str(argv) and TICKET not in str(kwargs)
        assert "PVE::AccessControl" not in str(argv)  # Its getter can rotate auth keys.
        assert 'open my $fh, "<", "/etc/pve/priv/authkey.key"' in argv[-1]
        assert kwargs["timeout"] == 5 and "PERL5OPT" not in kwargs["env"]
        return subprocess.CompletedProcess(argv, state.get("auth_exit", 0), state.get("ticket", TICKET), "private diagnostic")

    monkeypatch.setattr(env["subprocess"], "run", authenticate)
    yield read, state
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_https_keeps_server_stdout_outside_json_and_filters_fields(probe, monkeypatch, capsys):
    read, state = probe
    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted.invalid:8888")
    result = read("cohe", "local-dir")
    assert result == {"content": "images", "enabled": 1, "active": 1, "avail": 9999999999}
    assert state["requests"] == [("/api2/json/nodes/cohe/storage/local-dir/status", f"PVEAuthCookie={TICKET}")]
    assert "plugin writes" in capsys.readouterr().out


@pytest.mark.parametrize("status", [301, 401, 403, 404, 500])
def test_http_errors_do_not_follow_redirects_or_leak_response(probe, status):
    read, state = probe
    state.update(status=status, body=b"private server response")
    with pytest.raises(RuntimeError, match=f"HTTP {status}") as caught:
        read("cohe", "local")
    assert "private" not in str(caught.value) and TICKET not in str(caught.value)
    assert len(state["requests"]) == 1


@pytest.mark.parametrize("body,content_type", [(b"plugin noise\n{}", "application/json"),
    (b'{"data":[]}', "application/json"), (b'{}', "application/json"),
    (b"{}", "text/html"), (b"x" * 65537, "application/json")],
    ids=["polluted", "array", "missing-data", "html", "oversized"])
def test_malformed_http_data_fails_closed(probe, body, content_type):
    read, state = probe
    state.update(body=body, content_type=content_type)
    with pytest.raises(RuntimeError):
        read("cohe", "local")


@pytest.mark.parametrize("node,storage", [("other", "local"), ("cohe", "../local"),
                                         ("cohe", "local?redirect=x"), ("cohe", "local\n")])
def test_invalid_targets_fail_before_authentication(probe, node, storage):
    read, state = probe
    with pytest.raises(RuntimeError):
        read(node, storage)
    assert not state["auth_calls"] and not state["requests"]


@pytest.mark.parametrize("ticket,code", [("PVE:root@pam:secret\nInjected:header", 0), (TICKET, 1)])
def test_authentication_failure_sends_no_request(probe, ticket, code):
    read, state = probe
    state.update(ticket=ticket, auth_exit=code)
    with pytest.raises(RuntimeError, match="authentication unavailable"):
        read("cohe", "local")
    assert not state["requests"]


def test_certificate_mismatch_blocks_ticket_generation(probe, monkeypatch):
    read, state = probe
    monkeypatch.setattr(read.__globals__["ssl"], "PEM_cert_to_DER_cert", lambda pem: b"another certificate")
    with pytest.raises(RuntimeError, match="certificate mismatch"):
        read("cohe", "local")
    assert not state["auth_calls"] and not state["requests"]


def test_tls_failure_blocks_ticket_generation(probe, monkeypatch):
    read, state = probe
    def fail(*args, **kwargs):
        raise ssl.SSLError("private TLS diagnostic")
    monkeypatch.setattr(ssl.SSLSocket, "do_handshake", fail)
    with pytest.raises(RuntimeError, match="HTTPS request failed"):
        read("cohe", "local")
    assert not state["auth_calls"] and not state["requests"]
