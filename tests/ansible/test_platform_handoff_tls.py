"""Check endpoint arguments against real, disposable X.509 certificates."""

import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "handoff_filter", ROOT / "automation/ansible/filter_plugins/platform_handoff.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(scope="module")
def certificates(tmp_path_factory):
    directory = tmp_path_factory.mktemp("handoff-tls")
    for name, san in [("endpoint", "DNS:api.example.test,IP:192.0.2.10,IP:2001:db8::10"),
                      ("unrelated", "DNS:other.example.test")]:
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-subj", f"/CN={name}", "-addext", f"subjectAltName={san}",
            "-keyout", str(directory / f"{name}.key"), "-out", str(directory / f"{name}.crt"),
        ], check=True, capture_output=True)
    return directory


@pytest.mark.parametrize("address,connection", [
    ("api.example.test", "api.example.test:6443"),
    ("192.0.2.10", "192.0.2.10:6443"),
    ("2001:db8::10", "[2001:db8::10]:6443"),
])
def test_endpoint_identity_with_real_certificates(certificates, address, connection):
    endpoint = MODULE.platform_handoff_tls_endpoint(address)
    assert endpoint["connect"] == connection
    certificate = str(certificates / "endpoint.crt")
    for ca, identity, success in [
        (certificate, endpoint["identity"], True),
        (str(certificates / "unrelated.crt"), endpoint["identity"], False),
        (certificate, "wrong.example.test" if endpoint["verify_option"] == "-verify_hostname" else "192.0.2.99", False),
    ]:
        result = subprocess.run([
            "openssl", "verify", "-CAfile", ca, endpoint["verify_option"], identity, certificate,
        ], capture_output=True, text=True)
        assert (result.returncode == 0) == success
