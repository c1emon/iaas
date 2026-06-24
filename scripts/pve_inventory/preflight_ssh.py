"""Optional SSH adjunct checks for PVE preflight.

These checks are deliberately read-only: they only ask for wrapper help via
`sudo -n ... --help` and skip entirely when no SSH context is provided.
"""

from __future__ import annotations

import subprocess
from typing import Any, Callable

from .preflight_config import RuntimeConfig
from .preflight_results import CheckResult, Severity


def _emit(results: list[CheckResult], severity: Severity, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=severity, check_id=check_id, message=message))


def run_ssh_checks(runtime: RuntimeConfig, results: list[CheckResult], runner: Callable[..., Any] = subprocess.run) -> None:
    """Check wrapper presence/help without uploading or mutating anything."""
    if not (runtime.ssh_host and runtime.ssh_user):
        _emit(results, "SKIP", "ssh.context", "SSH adjunct checks skipped because PVE_HOST/PVE_SSH_USER were not both provided")
        return

    checks = [
        ("ssh.wrapper.snippet-upload", "/usr/local/sbin/astra-pve-snippet-upload --help"),
        ("ssh.wrapper.template-build", "/usr/local/sbin/astra-pve-template-build --help"),
    ]
    for check_id, remote in checks:
        command = ["ssh", "-o", "BatchMode=yes", f"{runtime.ssh_user}@{runtime.ssh_host}", f"sudo -n {remote}"]
        try:
            completed = runner(command, check=False, capture_output=True, text=True, timeout=20)
        except FileNotFoundError:
            _emit(results, "FAIL", check_id, "ssh command is unavailable")
            continue
        except subprocess.SubprocessError as exc:
            _emit(results, "FAIL", check_id, f"SSH adjunct check failed: {exc}")
            continue

        tool = remote.split()[0].rsplit("/", 1)[-1]
        if completed.returncode == 0:
            _emit(results, "PASS", check_id, f"{tool} is reachable with passwordless sudo")
        else:
            stderr = (completed.stderr or completed.stdout or "").strip().splitlines()[:1]
            detail = stderr[0] if stderr else f"exit {completed.returncode}"
            _emit(results, "FAIL", check_id, f"{tool} check failed: {detail}")
