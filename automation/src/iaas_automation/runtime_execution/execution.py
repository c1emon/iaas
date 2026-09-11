"""Sequential phases with truthful summaries and recovery-first retention."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from iaas_automation.common.errors import ValidationError
from .outputs import TaskOutputs
from .process import ProcessResult, run_protected


class OperationFailed(ValidationError):
    """The public error deliberately contains no raw tool output."""


@dataclass
class Execution:
    outputs: TaskOutputs
    environ: dict[str, str]
    phases: list[dict[str, Any]] = field(default_factory=list)

    def record(self, phase: str, result: ProcessResult, cwd: Path) -> None:
        recovery = self.outputs.retain_state(cwd)
        item = {"phase": phase, "exit_code": result.returncode,
                "capture_complete": result.capture_complete, "interrupted": result.interrupted,
                "capture": str(result.capture), **recovery}
        if not result.capture_complete:
            item.update(recovery_complete=False, retain_storage=True,
                        reason="protected capture failed; recovery completeness unconfirmed")
        self.phases.append(item)
        successful = result.successful and not recovery.get("retain_storage", False)
        self.outputs.summary({"status": "running" if successful else "failed", "phases": self.phases})
        if not successful:
            raise OperationFailed(f"{phase} failed; inspect protected task recovery material")

    def run(self, phase: str, command: Sequence[str], cwd: Path) -> ProcessResult:
        try:
            result = run_protected(command, cwd=cwd, environ=self.environ,
                                   capture=self.outputs.path("recovery") / f"{phase}.raw")
        except ValidationError:
            self.phases.append({"phase": phase, "status": "not-started", "reason": "protected process setup failed"})
            self.outputs.summary({"status": "failed", "phases": self.phases})
            raise OperationFailed(f"{phase} could not start; preserve task outputs") from None
        self.record(phase, result, cwd)
        return result

    def finish(self, summary: dict[str, Any]) -> None:
        self.outputs.summary({**summary, "status": "success", "phases": self.phases})
