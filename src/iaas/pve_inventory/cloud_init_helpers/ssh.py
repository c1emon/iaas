from __future__ import annotations

import os
import json
import shlex
import subprocess
from argparse import Namespace

from iaas.common.errors import ValidationError, require

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


def run_ssh_snippet_command(snippet: CloudInitSnippet, args: Namespace, command: list[str], input_text: str | None = None, *, budget=None, observe_only: bool = False):
    remote = f"{args.ssh_user}@{args.pve_host}"
    config = getattr(args, "ssh_config", None)
    port = getattr(args, "ssh_port", 22)
    require(type(port) is int and 1 <= port <= 65535, "invalid SSH port")
    ssh_argv = ["ssh", *(["-F", str(config)] if config else []),
                "-p", str(port), "-o", "BatchMode=yes", remote, _quote_remote_command(command)]
    timeout = resolve_ssh_timeout(getattr(args, "ssh_timeout", None))
    if budget is not None:
        timeout = min(timeout, budget.remaining('work'))
    try:
        result = subprocess.run(
            ssh_argv,
            input=input_text,
            text=input_text is not None or observe_only,
            capture_output=observe_only,
            check=True,
            timeout=timeout,
        )
        if budget is not None:
            budget.remaining('work')
        return result
    except FileNotFoundError as exc:
        raise ValidationError("ssh is required for snippet operations") from exc
    except subprocess.TimeoutExpired as exc:
        if observe_only:
            raise SnippetReadTimeout() from None
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


class SnippetReadTimeout(Exception):
    pass


def verify_snippets(snippets: list[CloudInitSnippet], args: Namespace) -> None:
    for snippet in snippets:
        _validate_ssh_inputs(snippet, args.storage_id, verify=True)
    from iaas.observation import Decision, EvidenceSink, ObservationBudget, observe
    budget = ObservationBudget(resolve_ssh_timeout(getattr(args, 'ssh_timeout', None)), source='ssh-timeout')
    evidence = EvidenceSink()
    args.observation_window = budget.facts()
    args.observations = []
    for snippet in snippets:
        last_error: list[ValidationError | None] = [None]
        def probe(remaining):
            answer = run_ssh_snippet_command(snippet, args, [
                'sudo', '-n', '/usr/local/sbin/iaas-pve-snippet-upload', '--storage', args.storage_id,
                '--filename', snippet.file_name, '--verify', '--sha256', snippet.sha256, '--observe'],
                budget=budget, observe_only=True)
            require(isinstance(answer.stdout, str) and len(answer.stdout) <= 16384, 'invalid snippet observation')
            value = json.loads(answer.stdout)
            require(isinstance(value, dict) and value.get('schema_version') == 1, 'invalid snippet observation')
            return value
        def classify(value):
            if not (value.get('status') in {'ready', 'pending', 'failed', 'unknown'}
                    and value.get('reason_code') in {'exact_target_absent', 'digest_confirmed', 'digest_mismatch',
                        'not_exclusive_regular_file', 'content_or_identity_changed', 'invalid_cloud_init_content',
                        'inspection_unavailable'}):
                return Decision('unknown', 'invalid_snippet_observation', {'category': 'invalid_response'})
            return Decision(value['status'], value['reason_code'],
                            {key: value[key] for key in ('exists', 'digest', 'inode') if key in value})
        def retry_error(exc):
            if isinstance(exc, SnippetReadTimeout):
                return Decision('pending', 'temporary_read_timeout', {'category': 'temporary_read'})
            # Input, permission, helper and malformed-response failures are not retries.
            if isinstance(exc, ValidationError):
                last_error[0] = exc
                return Decision('failed', 'helper_verification_failed', {'category': 'helper_failure'})
            return Decision('unknown', 'inspection_unconfirmed', {'category': 'unclassified'})
        decision = observe(probe, classify, budget, 'work', 'snippet_upload',
                           {'vmid': snippet.vmid, 'storage': args.storage_id, 'slot': snippet.file_name,
                            'digest': snippet.sha256}, sink=evidence,
                           interval=getattr(args, 'observation_interval', 1), retry_error=retry_error)
        args.observations = evidence.rows()
        if decision.status != 'ready' and last_error[0] is not None:
            raise last_error[0]
        require(decision.status == 'ready', 'snippet verification ' + decision.reason)
