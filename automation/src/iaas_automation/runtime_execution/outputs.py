"""Task-owned output categories and recovery retention, without auto state push."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Any

from iaas_automation.common.errors import require
from iaas_automation.common.io import write_text
from iaas_automation.runtime_paths import validate_paths


@dataclass(frozen=True)
class TaskOutputs:
    root: Path

    @classmethod
    def create(cls, root: Path, implementation: Path, inputs: list[Path]) -> TaskOutputs:
        validate_paths(None, implementation, [root], inputs)
        require(not root.exists(), "task output directory must be new")
        root.mkdir(parents=True, mode=0o700)
        for category in ("generated", "diagnostics", "plan", "recovery", "work"):
            (root / category).mkdir(mode=0o700)
        return cls(root.resolve())

    def path(self, category: str) -> Path:
        require(category in {"generated", "diagnostics", "plan", "recovery", "work"}, "unknown output category")
        return self.root / category

    def summary(self, value: dict[str, Any]) -> None:
        write_text(self.root / "summary.json", json.dumps(value, indent=2) + "\n", secure=True)

    def retain_state(self, working_root: Path) -> dict[str, Any]:
        source = working_root / "errored.tfstate"
        if not source.exists():
            return {"recovery_file": None}
        destination = self.path("recovery") / "errored.tfstate"
        try:
            source.chmod(0o600)
            # The source is kept until the launcher has collected the task.
            with source.open("rb") as reader:
                fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as writer:
                    shutil.copyfileobj(reader, writer)
                    writer.flush()
                    os.fsync(writer.fileno())
            return {"recovery_file": str(destination), "recovery_complete": True}
        except OSError:
            return {"recovery_file": str(source), "recovery_complete": False,
                    "retain_storage": True, "reason": "recovery export failed; retain original storage"}
