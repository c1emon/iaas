from __future__ import annotations

import os
import subprocess
from argparse import Namespace

from scripts.common.errors import ValidationError, require

from scripts.pve_inventory.cloud_init_helpers.model import CloudInitSnippet, DEFAULT_SSH_TIMEOUT_SECONDS


def resolve_ssh_timeout(arg_timeout: float | None) -> float:
    if arg_timeout is not None:
        require(arg_timeout > 0, "--ssh-timeout must be greater than zero")
        return arg_timeout
    env_timeout = os.environ.get("ASTRA_PVE_SSH_TIMEOUT_SECONDS", "").strip()
    if not env_timeout:
        return DEFAULT_SSH_TIMEOUT_SECONDS
    try:
        timeout = float(env_timeout)
    except ValueError as exc:
        raise ValidationError("ASTRA_PVE_SSH_TIMEOUT_SECONDS must be a number") from exc
    require(timeout > 0, "ASTRA_PVE_SSH_TIMEOUT_SECONDS must be greater than zero")
    return timeout


def run_ssh_snippet_command(snippet: CloudInitSnippet, args: Namespace, command: list[str], input_text: str | None = None) -> None:
    remote = f"{args.ssh_user}@{args.pve_host}"
    ssh_argv = ["ssh", remote, *command]
    timeout = resolve_ssh_timeout(getattr(args, "ssh_timeout", None))
    try:
        subprocess.run(
            ssh_argv,
            input=input_text,
            text=input_text is not None,
            check=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ValidationError("ssh is required for snippet operations") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidationError(
            f"ssh timed out after {timeout:.0f}s while processing {snippet.file_name} for VM {snippet.name} ({snippet.vmid})"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ValidationError(
            f"ssh command failed with exit code {exc.returncode} while processing {snippet.file_name} for VM {snippet.name} ({snippet.vmid})"
        ) from exc


def upload_snippets(snippets: list[CloudInitSnippet], args: Namespace) -> None:
    for snippet in snippets:
        run_ssh_snippet_command(
            snippet,
            args,
            [
                "sudo",
                "-n",
                "/usr/local/sbin/astra-pve-snippet-upload",
                "--storage",
                args.storage_id,
                "--filename",
                snippet.file_name,
            ],
            input_text=snippet.content,
        )


def verify_snippets(snippets: list[CloudInitSnippet], args: Namespace) -> None:
    for snippet in snippets:
        run_ssh_snippet_command(
            snippet,
            args,
            [
                "sudo",
                "-n",
                "/usr/local/sbin/astra-pve-snippet-upload",
                "--storage",
                args.storage_id,
                "--filename",
                snippet.file_name,
                "--verify",
                "--sha256",
                snippet.sha256,
            ],
        )
