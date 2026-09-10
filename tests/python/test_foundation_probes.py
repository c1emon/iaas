"""Bounded wire fixtures and a disposable loopback TLS endpoint."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import ssl
import struct
import subprocess
import threading

import pytest

from iaas_automation.foundation_inventory import health


def response(request, kind, data):
    packet_id = struct.unpack("!H", request[:2])[0]
    return (struct.pack("!HHHHHH", packet_id, 0x8180, 1, 1, 0, 0) + request[12:]
            + b"\xc0\x0c" + struct.pack("!HHIH", kind, 1, 30, len(data)) + data)


@pytest.mark.parametrize("record_type,kind,data,answer", [
    ("a", 1, socket.inet_pton(socket.AF_INET, "192.0.2.8"), "192.0.2.8"),
    ("aaaa", 28, socket.inet_pton(socket.AF_INET6, "2001:db8::8"), "2001:db8::8"),
    ("cname", 5, health._encode_dns_name("alias.example"), "alias.example"),
    ("txt", 16, b"\x05hello\x06 world", "hello world"),
    ("srv", 33, struct.pack("!HHH", 10, 20, 443) + health._encode_dns_name("api.example"), "10 20 443 api.example"),
    ("any", 16, b"\x05hello", "hello"),
])
def test_dns_records_use_explicit_connected_resolver(monkeypatch, record_type, kind, data, answer):
    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, timeout):
            assert timeout == 3

        def connect(self, destination):
            assert destination == ("192.0.2.53", 53)

        def send(self, request):
            self.request = request

        def recv(self, limit):
            assert limit == 4097
            return response(self.request, kind, data)

    monkeypatch.setattr(health.socket, "getaddrinfo", lambda host, port, **kw:
                        [(socket.AF_INET, socket.SOCK_DGRAM, 17, "", (host, port))])
    monkeypatch.setattr(health.socket, "socket", lambda *args: Socket())
    check = {"target": "query.example", "resolver": "192.0.2.53", "record_type": record_type,
             "expected_answer": answer}
    result = health.probe_dns(check)
    assert result.status == "passed"
    assert answer not in result.message
    check["expected_answer"] = "mismatch"
    assert health.probe_dns(check).status == "failed"


@pytest.mark.parametrize("case", ["short", "id", "question", "truncated", "pointer-cycle", "rdata", "huge-count"])
def test_dns_malformed_or_unrelated_response_is_rejected(case):
    request = struct.pack("!HHHHHH", 123, 0x100, 1, 0, 0, 0) + health._encode_dns_name("query.example") + struct.pack("!HH", 1, 1)
    payload = response(request, 1, b"\xc0\x00\x02\x08")
    if case == "short":
        payload = payload[:5]
    elif case == "id":
        payload = b"\x00\x00" + payload[2:]
    elif case == "question":
        payload = payload.replace(b"query", b"other")
    elif case == "truncated":
        payload = payload[:2] + struct.pack("!H", 0x8380) + payload[4:]
    elif case == "pointer-cycle":
        payload = payload[:12] + b"\xc0\x0c" + payload[14:]
    elif case == "rdata":
        payload = payload[:-1]
    else:
        payload = payload[:6] + b"\xff\xff" + payload[8:]
    with pytest.raises((ValueError, struct.error)):
        health._dns_answers(payload, 123, "query.example", 1)


def test_missing_dns_resolver_and_probe_exception_do_not_leak_or_stop_other_services():
    assert health.probe_dns({"target": "query.example"}).status == "failed"
    def broken(check):
        raise ValueError("https://user:private@example.test/?token=hidden")
    model = {"foundation_services": [
        {"name": "one", "health_check": {"type": "api"}},
        {"name": "two", "health_check": {"type": "dns"}},
    ]}
    results = health.run_health_checks(model, {"api": broken, "dns": lambda _: health.ProbeOutcome("passed", "ok")})
    assert len(results) == 2
    assert "private" not in str(results) and "hidden" not in str(results)
    assert "PASS" in str(results[1])


def test_https_requires_trusted_ca_and_exact_identity(tmp_path):
    cert, key = tmp_path / "ca.crt", tmp_path / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=loopback", "-addext", "subjectAltName=IP:127.0.0.1",
                    "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        target = f"https://127.0.0.1:{server.server_port}/?token=private"
        assert health.probe_https({"target": target, "ca_file": str(cert)}).status == "passed"
        failure = health.probe_https({"target": target})
        assert failure.status == "failed" and "private" not in failure.message
        assert health.probe_api({"target": target.replace("127.0.0.1", "localhost"), "ca_file": str(cert)}).status == "failed"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
