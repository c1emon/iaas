"""Sequential phases with truthful summaries and recovery-first retention."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from iaas.common.errors import ValidationError
from iaas.common.public_diagnostics import capture_diagnostics, safe_diagnostics

from .outputs import TaskOutputs
from .process import ProcessResult, run_protected
from .network_proxy import proxy_configured


class OperationFailed(ValidationError):
    """The public error deliberately contains no raw tool output."""


class OperationNotStarted(OperationFailed):
    """Protected setup failed before the child process was started."""

    process_started = False


@dataclass
class Execution:
    outputs: TaskOutputs
    environ: dict[str, str]
    phases: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def record(self, phase: str, result: ProcessResult, cwd: Path) -> None:
        recovery = self.outputs.retain_state(cwd)
        item = {"phase": phase, "exit_code": result.returncode,
                "proxy_configured": proxy_configured(self.environ),
                "capture_complete": result.capture_complete, "interrupted": result.interrupted,
                "capture": str(result.capture), **recovery}
        entries = capture_diagnostics(result.capture)
        if result.returncode and not any(entry['severity'] == 'error' for entry in entries):
            entries.extend(safe_diagnostics([{'code': 'timeout' if result.returncode == 124 else
                'process_interrupted' if result.interrupted else 'process_failed', 'exit_code': result.returncode}]))
        if not result.capture_complete:
            entries.extend(safe_diagnostics([{'code': 'capture_incomplete'}]))
            item.update(recovery_complete=False, retain_storage=True,
                        reason="protected capture failed; recovery completeness unconfirmed")
        self.phases.append(item)
        if entries:
            item['diagnostics'] = entries
            self.diagnostics = safe_diagnostics(self.diagnostics + entries)
        successful = result.successful and not recovery.get("retain_storage", False)
        self.outputs.summary({"status": "running" if successful else "failed", "phases": self.phases,
                              'diagnostics': self.diagnostics})
        if not successful:
            raise OperationFailed(f"{phase} failed; inspect protected task recovery material")

    def run(self, phase: str, command: Sequence[str], cwd: Path, *, timeout_seconds: int | None = None,
            max_output_bytes: int | None = None) -> ProcessResult:
        try:
            result = run_protected(command, cwd=cwd, environ=self.environ,
                                   capture=self.outputs.path("recovery") / f"{phase}-{uuid4().hex}.raw",
                                   timeout_seconds=timeout_seconds, max_output_bytes=max_output_bytes)
        except ValidationError:
            self.diagnostics = safe_diagnostics(self.diagnostics + [{'code': 'process_start_failed'}])
            self.phases.append({"phase": phase, "status": "not-started", "reason": "protected process setup failed"})
            self.outputs.summary({"status": "failed", "phases": self.phases, 'diagnostics': self.diagnostics})
            raise OperationNotStarted(f"{phase} could not start; preserve task outputs") from None
        self.record(phase, result, cwd)
        return result

    def finish(self, summary: dict[str, Any]) -> None:
        self.outputs.summary({**summary, "status": "success", "phases": self.phases, 'diagnostics': self.diagnostics})
