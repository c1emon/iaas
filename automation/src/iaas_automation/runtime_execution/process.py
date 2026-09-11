"""Never connect tool output (including emergency state dumps) to public logs."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import threading
from typing import BinaryIO, Mapping, Sequence

from iaas_automation.common.errors import ValidationError


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    capture_complete: bool
    interrupted: bool
    capture: Path

    @property
    def successful(self) -> bool:
        return self.returncode == 0 and self.capture_complete and not self.interrupted


def _capture_output(source: BinaryIO, destination: BinaryIO, failures: list[bool]) -> None:
    """Drain even after disk failure; never fall back to terminal output."""
    try:
        while chunk := source.read(65536):
            if not failures:
                try:
                    remaining = memoryview(chunk)
                    while remaining:
                        count = destination.write(remaining)
                        if not count:
                            raise OSError("capture write made no progress")
                        remaining = remaining[count:]
                except OSError:
                    failures.append(True)
        if not failures:
            try:
                destination.flush()
                os.fsync(destination.fileno())
            except OSError:
                failures.append(True)
    except OSError:
        failures.append(True)
    finally:
        source.close()


def run_protected(
    command: Sequence[str], *, cwd: Path, environ: Mapping[str, str], capture: Path,
) -> ProcessResult:
    """Capture before spawn, preserve exit status, and forward cancellation.

    This function runs inside the facility container. A caller may publish only
    the structured outcome; the capture itself is a sensitive recovery artifact.
    """
    try:
        capture.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        capture.parent.chmod(0o700)
        descriptor = os.open(capture, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        sink = os.fdopen(descriptor, "wb", buffering=0)
    except OSError:
        raise ValidationError("protected output capture unavailable; operation not started") from None
    failures: list[bool] = []
    interrupted = False
    old_handlers = {}

    def cancel(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    with sink:
        try:
            process = subprocess.Popen(list(command), cwd=cwd, env=dict(environ),
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True, umask=0o077)
        except OSError:
            raise ValidationError("runtime executable could not start; protected capture retained") from None
        assert process.stdout is not None
        worker = threading.Thread(target=_capture_output, args=(process.stdout, sink, failures), daemon=True)
        worker.start()
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGINT, signal.SIGTERM):
                old_handlers[signum] = signal.signal(signum, cancel)
        try:
            code = process.wait()
        except KeyboardInterrupt:
            interrupted = True
            # Ignore repeated cancellation while retaining the first result.
            for signum in old_handlers:
                signal.signal(signum, signal.SIG_IGN)
            try:
                os.killpg(process.pid, signal.SIGINT)
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
            except ProcessLookupError:
                code = process.wait()
        finally:
            worker.join()
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
    if interrupted and code == 0:
        code = 130
    return ProcessResult(code if code >= 0 else 128 - code, not failures, interrupted, capture)
