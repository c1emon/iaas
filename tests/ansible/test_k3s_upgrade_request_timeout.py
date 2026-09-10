"""Upgrade API retries must also bound each individual kubectl request."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading
import time

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS = [ROOT / "automation/ansible/roles" / path for path in [
    "k3s_upgrade/tasks/verify-upgraded.yml", "k3s_upgrade/tasks/main.yml",
    "k3s_snapshot/tasks/main.yml", "k3s_verify/tasks/main.yml",
]]


def api_commands():
    return [task["ansible.builtin.command"]["argv"] for path in TASKS for task in yaml.safe_load(path.read_text())
            if "kubectl" in task.get("ansible.builtin.command", {}).get("argv", [])]


def test_every_upgrade_api_command_has_a_finite_request_timeout():
    commands = api_commands()
    assert len(commands) == 9
    assert all("--request-timeout=15s" in command for command in commands)


@pytest.mark.skipif(shutil.which("kubectl") is None, reason="standalone kubectl unavailable")
def test_real_kubectl_times_out_on_an_incomplete_response():
    stop = threading.Event()

    class IncompleteResponse(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"o")
            self.wfile.flush()
            stop.wait(22)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), IncompleteResponse)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Use the shipped task's arguments after the k3s kubectl wrapper, with
        # only the kubeconfig/server explicitly isolated to this loopback fixture.
        command = api_commands()[0][2:]
        start = time.monotonic()
        result = subprocess.run(
            ["kubectl", "--kubeconfig=/dev/null", f"--server=http://127.0.0.1:{server.server_port}", *command],
            text=True, capture_output=True, timeout=20,
        )
        assert result.returncode != 0
        assert time.monotonic() - start < 20
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join()
