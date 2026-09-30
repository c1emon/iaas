"""Linux Docker consumer acceptance using an isolated task network.

Run with uv run python tests/integration/controlled_proxy_acceptance.py
--launcher /absolute/released/iaas --image repo@sha256:... --output NEW_DIR.
Requires the selected runtime and docker:dind already pulled on the host.
Only synthetic proxy authentication is used. No facility is contacted.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
import uuid
from urllib.parse import urlsplit
import zipfile


def proxy_server() -> None:
    """A CONNECT proxy; logs destinations/results, never request headers."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            target = urlsplit(self.path)
            if target.scheme != "http" or not target.hostname:
                self.send_error(400, "HTTP target required")
                return
            connection = None
            try:
                connection = http.client.HTTPConnection(target.hostname, target.port or 80, timeout=30)
                connection.request("GET", target.path + ("?" + target.query if target.query else ""))
                response = connection.getresponse()
                body = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.getheader("Content-Type", "application/octet-stream"))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                print(json.dumps({"target": self.path, "status": response.status}), flush=True)
            except OSError:
                self.send_error(502, "upstream unavailable")
            finally:
                if connection is not None:
                    connection.close()

        def do_CONNECT(self):
            expected = os.environ.get("TEST_PROXY_AUTH", "")
            if expected and self.headers.get("Proxy-Authorization") != "Basic " + expected:
                self.send_response(407)
                self.send_header("Proxy-Authenticate", 'Basic realm="acceptance"')
                self.end_headers()
                print(json.dumps({"target": self.path, "status": 407}), flush=True)
                return
            try:
                host, port = self.path.rsplit(":", 1)
                upstream = socket.create_connection((host, int(port)), timeout=30)
            except (ValueError, OSError):
                self.send_error(502, "upstream unavailable")
                print(json.dumps({"target": self.path, "status": 502}), flush=True)
                return
            self.send_response(200)
            self.end_headers()
            print(json.dumps({"target": self.path, "status": 200}), flush=True)
            with upstream:
                peers = [self.connection, upstream]
                while True:
                    ready, _, _ = select.select(peers, [], [], 120)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.connection else self.connection).sendall(data)
    ThreadingHTTPServer(("0.0.0.0", 3128), Handler).serve_forever()


def module_server() -> None:
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as bundle:
        bundle.writestr("main.tf", "locals { acceptance = true }\n")
    archive = body.getvalue()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(archive)))
            self.end_headers()
            self.wfile.write(archive)
            print(json.dumps({"target": self.path, "status": 200}), flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--dind-image", default="docker:28-dind")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engines", nargs="+", choices=["local", "dind"], default=["local", "dind"])
    args = parser.parse_args()
    assert "@sha256:" in args.image, "use an immutable published image digest"
    args.launcher = args.launcher.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[2]
    docker = shutil.which("docker")
    assert docker, "Docker CLI required"
    identity = "iaas-proxy-" + uuid.uuid4().hex[:12]
    network = identity + "-internal"
    containers = []
    results = []
    username, password = "acceptance-" + uuid.uuid4().hex, "synthetic-" + uuid.uuid4().hex
    wrong_password = "rejected-" + uuid.uuid4().hex
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    rejected_auth = base64.b64encode(f"{username}:{wrong_password}".encode()).decode()
    forbidden = [username.encode(), password.encode(), wrong_password.encode(), auth.encode(), rejected_auth.encode()]

    def command(argv, *, env=None, check=True, timeout=600):
        result = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f"acceptance setup command failed ({result.returncode}): {argv[:3]}")
        return result

    def dc(*argv, **kwargs):
        return command([docker, *argv], **kwargs)

    def inspect_ip(container):
        data = json.loads(dc("inspect", container).stdout)[0]
        return data["NetworkSettings"]["Networks"][network]["IPAddress"]

    def start_proxy(suffix, authenticated):
        name = identity + "-" + suffix
        containers.append(name)
        proxy_env = dict(os.environ, TEST_PROXY_AUTH=auth if authenticated else "")
        dc("run", "-d", "--name", name, "--network", "bridge", "--env", "TEST_PROXY_AUTH",
           "--mount", f"type=bind,src={Path(__file__).resolve()},dst=/proxy.py,readonly",
           "--entrypoint", "python", args.image, "/proxy.py", "--serve", env=proxy_env)
        dc("network", "connect", network, name)
        for _ in range(30):
            ready = dc("exec", name, "python", "-c", "import socket; socket.create_connection(('127.0.0.1',3128),1).close()", check=False, timeout=5)
            if ready.returncode == 0:
                return inspect_ip(name)
            time.sleep(1)
        raise RuntimeError("proxy did not become ready")

    try:
        dc("network", "create", "--internal", network)
        plain_ip = start_proxy("plain", False)
        auth_ip = start_proxy("auth", True)
        target_name = identity + "-module"
        containers.append(target_name)
        dc("run", "-d", "--name", target_name, "--network", network,
           "--mount", f"type=bind,src={Path(__file__).resolve()},dst=/proxy.py,readonly",
           "--entrypoint", "python", args.image, "/proxy.py", "--module-server")
        target_ip = inspect_ip(target_name)
        for _ in range(30):
            if dc("exec", target_name, "python", "-c", "import socket; socket.create_connection(('127.0.0.1',8080),1).close()", check=False, timeout=5).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("module target did not become ready")
        with tempfile.TemporaryDirectory(prefix=identity + "-") as temp:
            work = Path(temp)
            wrapper = work / "bin"
            wrapper.mkdir()
            # Formal launcher remains unchanged. Only the task daemon routing
            # is selected; explicit offline network none is always preserved.
            wrapper_code = '#!/usr/bin/env python3\nimport os,sys,json\na=sys.argv[1:]\nwith open(os.environ["TEST_DOCKER_AUDIT"],"a") as f: f.write(json.dumps(a)+"\\n")\nif a and a[0] in ("run","create") and "--network" not in a and os.environ["TEST_TASK_NETWORK"]:\n a[1:1]=["--network",os.environ["TEST_TASK_NETWORK"]]\nos.execv(os.environ["TEST_REAL_DOCKER"],[os.environ["TEST_REAL_DOCKER"],*a])\n'
            (wrapper / "docker").write_text(wrapper_code)
            (wrapper / "docker").chmod(0o700)
            lock = repo / "tests/fixtures/runtime-root/.terraform.lock.hcl"
            root = work / "root"
            root.mkdir()
            shutil.copyfile(lock, root / lock.name)
            (root / "main.tf").write_text('terraform {\n required_providers {\n proxmox = { source = "bpg/proxmox", version = "~> 0.111.0" }\n }\n}\n')
            entry = work / "environment.json"
            entry.write_text(json.dumps({"schema_version": 1, "environment": "proxy-acceptance", "components": {"pve": {"inputs": {}, "files": {"main": str(root / "main.tf"), "lock": str(root / lock.name), "backend": str(work / "never-read-backend"), "state_admission": str(work / "never-read-state")}, "options": {"root": {"id": "proxy-acceptance", "directory": ".", "files": {"main.tf": "main", ".terraform.lock.hcl": "lock"}}}}}}))
            runtime = work / "runtime.json"
            runtime.write_text(json.dumps({"interface_version": 1, "image": args.image, "platform": "linux/amd64"}))
            for engine in args.engines:
                env = {k: v for k, v in os.environ.items() if not k.upper().endswith("_PROXY") and not k.startswith(("PVE_", "AWS_", "TF_VAR_"))}
                env.update(TEST_TASK_NETWORK=network, TEST_REAL_DOCKER=docker, TEST_DOCKER_AUDIT=str(args.output / f"{engine}-docker-audit.jsonl"), PVE_API_TOKEN="facility-decoy-must-not-forward", AWS_SECRET_ACCESS_KEY="state-decoy-must-not-forward", TF_VAR_pve_api_token_secret="provider-decoy-must-not-forward")
                env["PATH"] = str(wrapper) + os.pathsep + env["PATH"]
                if engine == "dind":
                    env["TEST_TASK_NETWORK"] = ""
                    daemon = identity + "-dind"
                    containers.append(daemon)
                    dc("run", "-d", "--privileged", "--name", daemon, "--network", network, "--env", "DOCKER_TLS_CERTDIR=", "-p", "127.0.0.1::2375", args.dind_image)
                    dc("network", "connect", "bridge", daemon)
                    mapping = dc("port", daemon, "2375/tcp").stdout.decode().strip()
                    env["DOCKER_HOST"] = "tcp://" + mapping
                    for _ in range(60):
                        if dc("info", env=env, check=False, timeout=10).returncode == 0:
                            break
                        time.sleep(1)
                    else:
                        raise RuntimeError("DinD daemon did not become ready")
                    # Preserve repository digest by pulling before isolation.
                    dc("pull", args.image, env=env)
                    dc("network", "disconnect", "bridge", daemon)
                for case, proxy, success in [("direct", "", False), ("plain", f"http://{plain_ip}:3128", True), ("basic", f"http://{username}:{password}@{auth_ip}:3128", True), ("bad-basic", f"http://{username}:{wrong_password}@{auth_ip}:3128", False), ("unreachable", f"http://{plain_ip}:1", False)]:
                    case_env = dict(env)
                    if proxy:
                        case_env["HTTPS_PROXY"] = proxy
                    output = args.output / f"{engine}-{case}"
                    result = command([str(args.launcher), "run", "--runtime-config", str(runtime), "--environment", str(entry), "--engine", engine, "--component", "pve", "--operation", "prepare-dependencies", "--scope", "proxy-acceptance", "--output", str(output)], env=case_env, check=False)
                    assert (result.returncode == 0) == success, f"{engine}/{case}: unexpected exit {result.returncode}"
                    assert (root / lock.name).read_bytes() == lock.read_bytes(), "caller lock mutated"
                    (args.output / f"{engine}-{case}.log").write_bytes(result.stdout)
                    archive = list(output.rglob("dependencies.tar.gz")) if output.exists() else []
                    if success:
                        assert len(archive) == 1, "dependency archive missing"
                        with tarfile.open(archive[0]) as bundle:
                            members = bundle.getmembers()
                            assert any(m.isfile() and "terraform-provider-proxmox" in m.name for m in members), "provider package missing"
                            for member in members:
                                if member.isfile():
                                    stream = bundle.extractfile(member)
                                    assert stream is not None
                                    contents = stream.read()
                                    assert not any(secret in contents for secret in forbidden), "authentication persisted in archive"
                    results.append({"engine": engine, "case": case, "exit": result.returncode, "archive": bool(archive)})
                module_root = work / f"{engine}-module-root"
                module_root.mkdir()
                (module_root / "main.tf").write_text(f'module "acceptance" {{ source = "http://{target_ip}:8080/module.zip" }}\n')
                (module_root / lock.name).write_text("")
                module_config = json.loads(entry.read_text())
                module_config["components"]["pve"]["files"]["main"] = str(module_root / "main.tf")
                module_config["components"]["pve"]["files"]["lock"] = str(module_root / lock.name)
                module_entry = work / f"{engine}-module.json"
                module_entry.write_text(json.dumps(module_config))
                for bypass in (True, False):
                    case = "no-proxy-match" if bypass else "no-proxy-miss"
                    before_proxy = dc("logs", identity + "-plain").stdout.count(target_ip.encode())
                    before_target = dc("logs", target_name).stdout.count(b'"status": 200')
                    module_env = dict(env, HTTP_PROXY=f"http://{plain_ip}:3128", NO_PROXY=target_ip if bypass else "unmatched.invalid")
                    output = args.output / f"{engine}-{case}"
                    result = command([str(args.launcher), "run", "--runtime-config", str(runtime), "--environment", str(module_entry), "--engine", engine, "--component", "pve", "--operation", "prepare-dependencies", "--scope", "proxy-acceptance", "--output", str(output)], env=module_env, check=False)
                    (args.output / f"{engine}-{case}.log").write_bytes(result.stdout)
                    assert result.returncode == 0, f"{engine}/{case}: failed module download"
                    after_proxy = dc("logs", identity + "-plain").stdout.count(target_ip.encode())
                    after_target = dc("logs", target_name).stdout.count(b'"status": 200')
                    assert after_target > before_target, "module target not consumed"
                    assert (after_proxy == before_proxy) if bypass else (after_proxy > before_proxy), "NO_PROXY route evidence mismatch"
                    assert (module_root / lock.name).read_bytes() == b"", "module lock mutated"
                    assert list(output.rglob("dependencies.tar.gz")), "module dependency archive missing"
                    results.append({"engine": engine, "case": case, "exit": result.returncode, "target_requests": after_target - before_target, "proxy_requests": after_proxy - before_proxy})
                offline_config = json.loads(entry.read_text())
                offline_config["components"]["pve"]["inputs"] = {
                    "cluster": str(repo / "tests/fixtures/environment/inventory/pve-cluster.yml"),
                    "vms": str(repo / "tests/fixtures/environment/inventory/vms.yml"),
                }
                offline_entry = work / f"{engine}-offline.json"
                offline_entry.write_text(json.dumps(offline_config))
                audit_path = args.output / f"{engine}-docker-audit.jsonl"
                audit_before = len(audit_path.read_text().splitlines())
                proxy_before = [dc("logs", identity + "-" + suffix).stdout for suffix in ("plain", "auth")]
                offline_env = dict(env, HTTPS_PROXY="malformed-proxy-config", https_proxy="conflicting-malformed-config", HTTP_PROXY=f"http://{plain_ip}:3128", ALL_PROXY="also-malformed")
                offline_output = args.output / f"{engine}-offline"
                offline = command([str(args.launcher), "run", "--runtime-config", str(runtime), "--environment", str(offline_entry), "--engine", engine, "--component", "pve", "--operation", "check", "--output", str(offline_output)], env=offline_env, check=False)
                (args.output / f"{engine}-offline.log").write_bytes(offline.stdout)
                assert offline.returncode == 0, f"{engine}/offline: check failed"
                offline_calls = [json.loads(line) for line in audit_path.read_text().splitlines()[audit_before:]]
                isolated = [call for call in offline_calls if call and call[0] in {"run", "create"}]
                assert isolated, "no actual offline task container evidence"
                for call in isolated:
                    assert "--network" in call and call[call.index("--network") + 1] == "none", "offline network changed"
                    for family in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY", "FTP_PROXY"):
                        for name in (family, family.lower()):
                            assert name + "=" in call and name not in call, "offline proxy was not explicitly cleared"
                assert proxy_before == [dc("logs", identity + "-" + suffix).stdout for suffix in ("plain", "auth")], "offline operation contacted proxy"
                results.append({"engine": engine, "case": "offline", "exit": offline.returncode, "network": "none", "proxy": "cleared"})
                audit = (args.output / f"{engine}-docker-audit.jsonl").read_text()
                for decoy in ("never-read-backend", "never-read-state", "PVE_API_TOKEN", "AWS_SECRET_ACCESS_KEY", "TF_VAR_pve_api_token_secret"):
                    assert decoy not in audit, "facility/state decoy selected or forwarded"
        for name in containers:
            if name.endswith(("-plain", "-auth")):
                logs = dc("logs", name).stdout
                assert b'"status": 200' in logs, "no actual proxy CONNECT evidence"
                (args.output / (name.rsplit("-", 1)[-1] + "-targets.jsonl")).write_bytes(logs)
        (args.output / "module-targets.jsonl").write_bytes(dc("logs", target_name).stdout)
        for path in args.output.rglob("*"):
            if path.is_file() and path.name != "dependencies.tar.gz":
                assert not any(secret in path.read_bytes() for secret in forbidden), "authentication persisted in diagnostics"
        (args.output / "acceptance.json").write_text(json.dumps({"image": args.image, "launcher_sha256": hashlib.sha256(args.launcher.read_bytes()).hexdigest(), "network": "task-specific internal", "results": results}, indent=2) + "\n")
        print(json.dumps({"status": "passed", "cases": len(results)}))
    finally:
        residual = []
        for name in reversed(containers):
            dc("rm", "-f", "-v", name, check=False)
            if dc("inspect", name, check=False).returncode == 0:
                residual.append(name)
        dc("network", "rm", network, check=False)
        if dc("network", "inspect", network, check=False).returncode == 0:
            residual.append(network)
        if residual:
            raise RuntimeError("acceptance cleanup left task resources: " + ", ".join(residual))


if __name__ == "__main__":
    if "--serve" in os.sys.argv:
        proxy_server()
    elif "--module-server" in os.sys.argv:
        module_server()
    else:
        main()
