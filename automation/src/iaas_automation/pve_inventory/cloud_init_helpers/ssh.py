from __future__ import annotations

import os
import shlex
import subprocess
from argparse import Namespace

from iaas_automation.common.errors import ValidationError, require

from .model import CloudInitSnippet, DEFAULT_SSH_TIMEOUT_SECONDS, validate_sha256_hex, validate_snippet_file_name, validate_storage_id


def _quote_remote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _validate_ssh_inputs(snippet: CloudInitSnippet, storage_id: str, verify: bool = False) -> None:
    validate_storage_id(storage_id)
    validate_snippet_file_name(snippet.file_name)
    if verify:
        validate_sha256_hex(snippet.sha256)


def resolve_ssh_timeout(arg_timeout: float | None) -> float:
    require("ASTRA_PVE_SSH_TIMEOUT_SECONDS" not in os.environ,
            "ASTRA_PVE_SSH_TIMEOUT_SECONDS is no longer supported; use IAAS_PVE_SSH_TIMEOUT_SECONDS")
    if arg_timeout is not None:
        require(arg_timeout > 0, "--ssh-timeout must be greater than zero")
        return arg_timeout
    env_timeout = os.environ.get("IAAS_PVE_SSH_TIMEOUT_SECONDS", "").strip()
    if not env_timeout:
        return DEFAULT_SSH_TIMEOUT_SECONDS
    try:
        timeout = float(env_timeout)
    except ValueError as exc:
        raise ValidationError("IAAS_PVE_SSH_TIMEOUT_SECONDS must be a number") from exc
    require(timeout > 0, "IAAS_PVE_SSH_TIMEOUT_SECONDS must be greater than zero")
    return timeout


def run_ssh_snippet_command(snippet: CloudInitSnippet, args: Namespace, command: list[str], input_text: str | None = None) -> None:
    remote = f"{args.ssh_user}@{args.pve_host}"
    ssh_argv = ["ssh", remote, _quote_remote_command(command)]
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
        _validate_ssh_inputs(snippet, args.storage_id)
    for snippet in snippets:
        run_ssh_snippet_command(
            snippet,
            args,
            [
                "sudo",
                "-n",
                "/usr/local/sbin/iaas-pve-snippet-upload",
                "--storage",
                args.storage_id,
                "--filename",
                snippet.file_name,
            ],
            input_text=snippet.content,
        )


def verify_snippets(snippets: list[CloudInitSnippet], args: Namespace) -> None:
    for snippet in snippets:
        _validate_ssh_inputs(snippet, args.storage_id, verify=True)
    for snippet in snippets:
        run_ssh_snippet_command(
            snippet,
            args,
            [
                "sudo",
                "-n",
                "/usr/local/sbin/iaas-pve-snippet-upload",
                "--storage",
                args.storage_id,
                "--filename",
                snippet.file_name,
                "--verify",
                "--sha256",
                snippet.sha256,
            ],
        )
