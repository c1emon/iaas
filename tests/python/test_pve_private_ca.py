"""Representative PVE adapters exercised against a real local TLS endpoint."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import shutil
import ssl
import subprocess
import threading

import pytest
import yaml

from iaas.common.errors import ValidationError
from iaas.common.pve_tls import CA_PREPARATION_FAILED, ssl_context, write_ca_bundle
from iaas.pve_inventory.checks.preflight.api import create_api_client
from iaas.pve_inventory.pve_api import PveApiTlsError, ReadOnlyPveApi
from iaas.pve_inventory.pve_api.runtime import load_api_runtime_config, load_online_runtime_context
from iaas.runtime_execution.pve_results import api_client


@pytest.fixture(scope="module")
def certificates(tmp_path_factory):
    directory = tmp_path_factory.mktemp("pve-ca")
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("local TLS fixture requires openssl")

    def run(*args):
        subprocess.run([openssl, *map(str, args)], cwd=directory, check=True, capture_output=True)

    run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
        "-subj", "/CN=PVE test CA", "-addext", "basicConstraints=critical,CA:TRUE",
        "-keyout", "ca.key", "-out", "ca.pem")
    run("req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=PVE test server",
        "-keyout", "server.key", "-out", "server.csr")
    (directory / "index").write_text("")
    (directory / "serial").write_text("1000\n")
    now = datetime.now(timezone.utc)
    for name, san, start, end in [
        ("valid", "IP:127.0.0.1", now - timedelta(hours=1), now + timedelta(days=1)),
        ("mismatch", "DNS:wrong.invalid", now - timedelta(hours=1), now + timedelta(days=1)),
        ("expired", "IP:127.0.0.1", now - timedelta(days=2), now - timedelta(days=1)),
        ("future", "IP:127.0.0.1", now + timedelta(days=1), now + timedelta(days=2)),
    ]:
        (directory / "ca.conf").write_text(
            "[ca]\ndefault_ca=local\n[local]\ndatabase=index\nserial=serial\n"
            "new_certs_dir=.\ncertificate=ca.pem\nprivate_key=ca.key\ndefault_md=sha256\n"
            "policy=policy\nunique_subject=no\nx509_extensions=server\n"
            "[policy]\ncommonName=supplied\n[server]\nbasicConstraints=critical,CA:FALSE\n"
            f"subjectAltName={san}\nextendedKeyUsage=serverAuth\n")
        run("ca", "-batch", "-config", "ca.conf", "-in", "server.csr", "-out", f"{name}.pem",
            "-startdate", start.strftime("%Y%m%d%H%M%SZ"), "-enddate", end.strftime("%Y%m%d%H%M%SZ"))
    return directory


@contextmanager
def https_endpoint(certificates, variant="valid"):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            requests.append(self.path)
            body = json.dumps({"data": [{"node": "fixture"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificates / f"{variant}.pem", certificates / "server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def make_client(adapter, endpoint, ca_file, insecure=False):
    env = {"TF_VAR_pve_endpoint": endpoint, "TF_VAR_pve_api_username": "test@pve",
           "TF_VAR_pve_api_token_id": "test", "TF_VAR_pve_api_token_secret": "synthetic-token",
           "TF_VAR_pve_insecure": str(insecure).lower()}
    if ca_file is not None:
        env["PVE_API_CA"] = str(ca_file)
    if adapter == "preflight":
        return create_api_client(load_online_runtime_context(env))
    if adapter == "health":
        return ReadOnlyPveApi(load_api_runtime_config(env))
    return api_client({"api_endpoint": endpoint, "insecure": insecure}, env)


@pytest.mark.parametrize("adapter", ["preflight", "health", "results"])
def test_api_adapters_use_private_ca(certificates, adapter):
    with https_endpoint(certificates) as (endpoint, requests):
        assert make_client(adapter, endpoint, certificates / "ca.pem").nodes() == [{"node": "fixture"}]
        assert requests == ["/api2/json/nodes"]


@pytest.mark.parametrize("variant", ["untrusted", "wrong_ca", "mismatch", "expired", "future"])
@pytest.mark.parametrize("adapter", ["preflight", "health"])
def test_api_adapters_reject_invalid_server_trust(certificates, adapter, variant):
    with https_endpoint(certificates, "valid" if variant in {"untrusted", "wrong_ca"} else variant) as (endpoint, requests):
        ca = None if variant == "untrusted" else certificates / "ca.pem"
        if variant == "wrong_ca":
            ca = ssl.get_default_verify_paths().cafile
            assert ca
        with pytest.raises(PveApiTlsError, match="[Cc][Ee][Rr][Tt][Ii][Ff][Ii][Cc][Aa][Tt][Ee]"):
            make_client(adapter, endpoint, ca).nodes()
        assert requests == []


@pytest.mark.parametrize("contents", ["", "not a certificate"])
@pytest.mark.parametrize("adapter", ["preflight", "health"])
def test_unused_invalid_ca_is_only_rejected_in_strict_mode(certificates, tmp_path, adapter, contents):
    ca = tmp_path / "sensitive-path.pem"
    ca.write_text(contents)
    with https_endpoint(certificates) as (endpoint, requests):
        with pytest.raises(ValidationError) as error:
            make_client(adapter, endpoint, ca).nodes()
        assert str(error.value) == CA_PREPARATION_FAILED
        assert requests == []
        assert make_client(adapter, endpoint, ca, insecure=True).nodes() == [{"node": "fixture"}]


def test_context_and_bundle_preserve_public_roots(certificates, tmp_path):
    ca = certificates / "ca.pem"
    public = set(ssl.create_default_context().get_ca_certs(binary_form=True))
    assert public
    context = ssl_context(False, ca)
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert public < set(context.get_ca_certs(binary_form=True))
    bundle = write_ca_bundle(ca, tmp_path / "trust" / "bundle.pem")
    bundled = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    bundled.load_verify_locations(cafile=bundle)
    assert set(bundled.get_ca_certs(binary_form=True)) == set(context.get_ca_certs(binary_form=True))
    assert ssl_context(True, tmp_path / "does-not-exist").verify_mode == ssl.CERT_NONE


def test_invalid_ca_cannot_be_hidden_by_public_roots(tmp_path):
    invalid = tmp_path / "ca.pem"
    invalid.write_text("not a certificate")
    with pytest.raises(ValidationError, match=CA_PREPARATION_FAILED):
        write_ca_bundle(invalid, tmp_path / "bundle.pem")
    assert not (tmp_path / "bundle.pem").exists()


@pytest.mark.parametrize("failure", ["identity", "invalid_ca"])
def test_runtime_health_retains_tls_failure_in_protected_phase(certificates, tmp_path, monkeypatch, capsys, failure):
    from iaas.runtime_execution.__main__ import main

    repo = Path(__file__).resolve().parents[2]
    ca = certificates / "ca.pem"
    if failure == "invalid_ca":
        ca = tmp_path / "private-ca.pem"
        ca.write_text("not PEM material")
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({"schema_version": 1, "environment": "synthetic",
        "components": {"pve": {"inputs": {
            "cluster": str(repo / "tests/fixtures/runtime/pve-cluster.yml"),
            "vms": str(repo / "tests/fixtures/runtime/vms.yml")}, "files": {"api_ca": str(ca)}}}}))
    output = tmp_path / "health"
    monkeypatch.setenv("PYTHONPATH", str(repo / "src"))
    monkeypatch.setenv("TF_VAR_pve_api_username", "test@pve")
    monkeypatch.setenv("TF_VAR_pve_api_token_id", "test")
    monkeypatch.setenv("TF_VAR_pve_api_token_secret", "synthetic-secret")
    monkeypatch.setenv("TF_VAR_pve_insecure", "false")
    with https_endpoint(certificates, "mismatch") as (endpoint, requests):
        monkeypatch.setenv("TF_VAR_pve_endpoint", endpoint)
        assert main(["--environment", str(entry), "--component", "pve", "--operation", "health",
                     "--scope", "synthetic-pve", "--output", str(output)]) == 1
        assert requests == []
    public = json.loads(capsys.readouterr().out)
    assert public["status"] == "failed"
    assert public["phases"] == [{"phase": "health", "exit_code": 1}]
    assert public["output"] == str(output)
    assert "synthetic-secret" not in json.dumps(public)
    summary = json.loads((output / "summary.json").read_text())
    capture = Path(summary["phases"][0]["capture"])
    assert capture == output / "recovery" / "health.raw"
    assert capture.stat().st_mode & 0o777 == 0o600
    assert (output.stat().st_mode & 0o777) == 0o700
    diagnostic = capture.read_text()
    assert ("CERTIFICATE_VERIFY_FAILED" if failure == "identity" else CA_PREPARATION_FAILED) in diagnostic
    assert "synthetic-secret" not in diagnostic


def test_result_verification_does_not_swallow_tls_failure(certificates):
    from iaas.runtime_execution.pve_results import verify_configuration

    with https_endpoint(certificates, "mismatch") as (endpoint, requests):
        client = make_client("results", endpoint, certificates / "ca.pem")
        with pytest.raises(PveApiTlsError):
            verify_configuration([{"kind": "vm", "node": "fixture", "vmid": 100,
                                   "absent": False, "snapshot_complete": True,
                                   "snapshot_identity": "passed"}], client)
        assert requests == []


def test_runtime_direct_api_tls_failure_has_protected_capture(certificates, tmp_path, monkeypatch, capsys):
    import iaas.runtime_execution.__main__ as dispatch
    from test_runtime_dispatch import config, REPO

    entry = config(tmp_path, "pve", {"cluster": str(REPO / "tests/fixtures/runtime/pve-cluster.yml"),
                                    "vms": str(REPO / "tests/fixtures/runtime/vms.yml")},
                   {"api_ca": str(certificates / "ca.pem")})
    monkeypatch.setenv("TF_VAR_pve_api_username", "test@pve")
    monkeypatch.setenv("TF_VAR_pve_api_token_id", "test")
    monkeypatch.setenv("TF_VAR_pve_api_token_secret", "synthetic-secret")
    monkeypatch.setenv("TF_VAR_pve_insecure", "false")

    def direct_api(selected, operation, scope, execution, **kwargs):
        client = api_client({"api_endpoint": execution.environ["TF_VAR_pve_endpoint"], "insecure": False},
                            execution.environ)
        client.vm_config("fixture", 100)

    monkeypatch.setattr(dispatch, "run_component", direct_api)
    output = tmp_path / "direct"
    with https_endpoint(certificates, "mismatch") as (endpoint, requests):
        monkeypatch.setenv("TF_VAR_pve_endpoint", endpoint)
        assert dispatch.main(["--environment", str(entry), "--component", "pve", "--operation", "health",
                              "--scope", "synthetic-pve", "--output", str(output)]) == 2
        assert requests == []
    public = json.loads(capsys.readouterr().out)
    assert public["status"] == "failed"
    assert public["phases"] == [{"phase": "pve-api-tls", "exit_code": 2}]
    assert endpoint not in json.dumps(public) and "synthetic-secret" not in json.dumps(public)
    summary = json.loads((output / "summary.json").read_text())
    capture = Path(summary["phases"][0]["capture"])
    assert capture == output / "recovery" / "pve-api-tls.raw"
    assert capture.stat().st_mode & 0o777 == 0o600
    assert "CERTIFICATE_VERIFY_FAILED" in capture.read_text()
