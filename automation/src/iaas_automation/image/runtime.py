"""Direct, bounded local image lifecycle operations.

The image component is independent of PVE and OpenTofu. Build uses a pinned
Packer QEMU profile and performs identity cleanup after the last SSH phase.
Test always boots a disposable overlay and a fresh UEFI variable store, then
verifies that the source digest is unchanged.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import load_json, write_text
from iaas_automation.runtime_execution.execution import Execution, OperationFailed

from .contracts import (
    IDENTIFIER,
    RUNTIME_DIGEST,
    SUPPORTED_CHECKS,
    canonical_digest,
    load_strict_json,
    resolve_artifact_path,
    validate_artifact,
    validate_build_request,
    validate_test_request,
    validate_test_result,
)

TASK_VERSION = 1
TEST_USER = "iaas-test"
DYNAMIC_CHECKS = {"cloud-init", "guest-agent", "first-boot"}
STATIC_CHECKS = SUPPORTED_CHECKS - DYNAMIC_CHECKS
PROCESS_GRACE_SECONDS = 10
_TRACKER = (
    "import os, pathlib, sys; "
    "pid=os.getpid(); proc=pathlib.Path(f'/proc/{pid}/stat'); "
    "ticks=proc.read_text().split()[21] if proc.exists() else ''; "
    "pathlib.Path(sys.argv[1]).write_text(f'{pid} {ticks}\\n'); "
    "os.execvp(sys.argv[2], sys.argv[2:])"
)


def _options(selected: Any) -> dict[str, Any]:
    options = getattr(selected, "options", {})
    require(isinstance(options, Mapping), "image options must be a mapping")
    return dict(options)


def _document(selected: Any) -> dict[str, Any]:
    documents = getattr(selected, "documents", {})
    require(isinstance(documents, Mapping), "image documents must be a mapping")
    for name in ("request", "build", "test", "artifact"):
        value = documents.get(name)
        if isinstance(value, Mapping):
            return dict(value)
    raise ValidationError("image operation requires a request input")


def _path(selected: Any, *names: str) -> Path | None:
    files = getattr(selected, "files", {})
    if not isinstance(files, Mapping):
        return None
    for name in names:
        value = files.get(name)
        if value is not None:
            return Path(value)
    return None


def _execution_id(selected: Any, execution_id: str | None) -> str:
    value = execution_id or _options(selected).get("execution_id")
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ValidationError("image operation requires a bounded execution_id")
    return value


def _runtime_digest(selected: Any, resolved: str | None = None) -> str:
    value = resolved or _options(selected).get("runtime_digest", "")
    require(isinstance(value, str) and RUNTIME_DIGEST.fullmatch(value) is not None,
            "image operation requires a resolved runtime digest")
    return value


def _task_dir(execution: Execution, execution_id: str) -> Path:
    directory = execution.outputs.path("work") / "image-tasks" / execution_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    return directory


def _write_task(path: Path, value: Mapping[str, Any]) -> None:
    write_text(path, json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", secure=True)


@contextmanager
def _resource_lock(directory: Path) -> Iterator[None]:
    """Acquire a task lock; a stale PID is never treated as ownership."""
    with (directory / "resource.lock").open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValidationError("image execution resource lock is active") from None
        yield


def _load_task(selected: Any, execution: Execution, execution_id: str) -> tuple[Path, dict[str, Any]]:
    directory = _path(selected, "execution_dir")
    if directory is None:
        configured = _options(selected).get("execution_dir")
        directory = Path(str(configured)) if configured else None
    if directory is None or not directory.is_dir():
        raise ValidationError("image read/clean requires an explicit execution_dir")
    directory = directory.resolve()
    value = load_json(directory / "task.json")
    require(isinstance(value, Mapping) and value.get("execution_id") == execution_id,
            "image task record does not match execution_id")
    return directory, dict(value)


def _executor_check(resources: Mapping[str, int]) -> dict[str, Any]:
    platform_name = f"{platform.system().lower()}/{platform.machine()}"
    kvm = Path("/dev/kvm")
    free = shutil.disk_usage(Path.cwd()).free
    return {"platform": platform_name, "kvm_path": str(kvm),
            "kvm_readable": os.access(kvm, os.R_OK | os.W_OK), "available_bytes": free,
            "supported_platform": platform_name == "linux/x86_64",
            "supported_kvm": os.access(kvm, os.R_OK | os.W_OK),
            "enough_disk": free >= resources["work_min_free_bytes"], "accelerator": "kvm"}


def _require_executor(resources: Mapping[str, int]) -> dict[str, Any]:
    facts = _executor_check(resources)
    require(facts["supported_platform"], "image build/test requires a Linux amd64 executor")
    require(facts["supported_kvm"], "image build/test requires usable /dev/kvm; TCG fallback is unsupported")
    require(facts["enough_disk"], "image executor does not have the requested free disk budget")
    return facts


def _download_base(request: Mapping[str, Any], destination: Path, resources: Mapping[str, int]) -> None:
    base, checksum = request["base"], request["base"]["checksum"]
    digest = hashlib.new(checksum["algorithm"])
    free = shutil.disk_usage(destination.parent).free
    limit = min(max(0, free - resources["work_min_free_bytes"]), 1 << 40)
    deadline = time.monotonic() + resources["timeout_seconds"]
    size = 0
    try:
        with (urlopen(Request(base["object_ref"], headers={"Accept": "application/octet-stream"}),
                      timeout=min(60, resources["timeout_seconds"])) as response,
              destination.open("xb") as output):
            declared = response.headers.get("Content-Length")
            if declared is not None and declared.isdigit() and int(declared) > limit:
                raise OperationFailed("base image exceeds bounded download budget")
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OperationFailed("base image download exceeded its time budget")
                chunk = response.read(min(1024 * 1024, max(1, limit - size + 1)))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise OperationFailed("base image exceeds bounded download budget")
                digest.update(chunk)
                output.write(chunk)
    except (OSError, TimeoutError):
        raise OperationFailed("base image download failed; inspect protected task recovery material") from None
    require(digest.hexdigest() == checksum["value"], "base image checksum does not match request")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _current_budget(execution: Execution) -> int:
    value = getattr(execution, "image_max_output_bytes", None)
    return value if type(value) is int and value > 0 else 1 << 40


def _current_timeout(execution: Execution) -> int | None:
    value = getattr(execution, "image_timeout_seconds", None)
    return value if type(value) is int and value > 0 else None


def _run_tool(execution: Execution, phase: str, command: Sequence[str], cwd: Path) -> int:
    result = execution.run(phase, list(command), cwd, timeout_seconds=_current_timeout(execution),
                          max_output_bytes=_current_budget(execution))
    capture = execution.outputs.path("recovery") / f"{phase}.raw"
    if capture.is_file() and capture.stat().st_size > _current_budget(execution):
        raise OperationFailed(f"{phase} exceeded the protected output budget")
    return result.returncode


def _run_tracked_tool(execution: Execution, directory: Path, task: dict[str, Any], phase: str,
                      command: Sequence[str], cwd: Path) -> None:
    """Run a long lived tool with a durable pid marker for controller recovery."""
    marker = directory / f"{phase}.pid"
    entry: dict[str, Any] = {"pid": None, "start_ticks": None, "pid_file": str(marker),
                             "state": "starting", "command": list(command), "phase": phase}
    task.setdefault("processes", []).append(entry)
    task.setdefault("owned_resources", []).append(str(marker))
    _write_task(directory / "task.json", task)
    tracked = [sys.executable, "-c", _TRACKER, str(marker), *command]
    exit_code: int | None = None
    try:
        exit_code = _run_tool(execution, phase, tracked, cwd)
    finally:
        try:
            fields = marker.read_text(encoding="ascii").split()
            entry["pid"] = int(fields[0])
            entry["start_ticks"] = int(fields[1]) if len(fields) > 1 else None
        except (OSError, ValueError):
            pass
        entry["state"] = "stopped" if not _process_group_alive(entry) else "unknown"
        entry["exit_code"] = exit_code
        _write_task(directory / "task.json", task)


def _proc_start_ticks(pid: int) -> int | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").split()
        return int(fields[21])
    except (OSError, ValueError, IndexError):
        return None


def _process_alive(entry: Mapping[str, Any]) -> bool:
    pid = entry.get("pid")
    if type(pid) is not int and isinstance(entry.get("pid_file"), str):
        try:
            fields = Path(entry["pid_file"]).read_text(encoding="ascii").split()
            pid = int(fields[0])
            ticks = int(fields[1]) if len(fields) > 1 else None
        except (OSError, ValueError):
            return False
        expected = ticks
    else:
        expected = entry.get("start_ticks")
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return expected is None or expected == _proc_start_ticks(pid)


def _process_group_alive(entry: Mapping[str, Any]) -> bool:
    pid = entry.get("pid")
    if type(pid) is not int and isinstance(entry.get("pid_file"), str):
        try:
            pid = int(Path(entry["pid_file"]).read_text(encoding="ascii").split()[0])
        except (OSError, ValueError, IndexError):
            return False
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.killpg(pid, 0)
    except OSError:
        return False
    return True


def _task_has_active_process(task: Mapping[str, Any]) -> bool:
    processes = task.get("processes", [])
    return isinstance(processes, list) and any(
        isinstance(item, Mapping) and item.get("state") in {"starting", "running"} and _process_alive(item)
        for item in processes)


def _task_has_uncertain_process(task: Mapping[str, Any]) -> bool:
    processes = task.get("processes", [])
    return isinstance(processes, list) and any(
        isinstance(item, Mapping) and item.get("state") == "unknown" for item in processes)


def _stop_process(process: subprocess.Popen[bytes], entry: dict[str, Any]) -> None:
    # The leader may have exited while descendants in its start-new-session
    # process group remain. Always signal the group before marking it stopped.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=PROCESS_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    group_gone = False
    for _ in range(20):
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            group_gone = True
            break
        time.sleep(0.05)
    if not group_gone:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            group_gone = True
    entry["state"] = "stopped" if group_gone else "unknown"
    entry["exit_code"] = process.returncode


def _make_seed(execution: Execution, directory: Path, *, username: str, phase: str,
               task: dict[str, Any] | None = None) -> tuple[Path, Path]:
    key = directory / f"{phase}.key"
    seed = directory / f"{phase}.seed.img"
    user_data, meta_data = directory / f"{phase}.user-data", directory / f"{phase}.meta-data"
    if task is not None:
        owned = task.setdefault("owned_resources", [])
        for item in (seed, key, Path(f"{key}.pub"), user_data, meta_data):
            if str(item) not in owned:
                owned.append(str(item))
        _write_task(directory / "task.json", task)
    _run_tool(execution, f"{phase}-ssh-key", ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], directory)
    public_key = Path(f"{key}.pub").read_text(encoding="utf-8").strip()
    write_text(user_data, "#cloud-config\n" + json.dumps({
        "users": [{"name": username, "sudo": "ALL=(ALL) NOPASSWD:ALL", "shell": "/bin/bash",
                   "ssh_authorized_keys": [public_key]}], "ssh_pwauth": False, "disable_root": True}) + "\n", secure=True)
    write_text(meta_data, f"instance-id: iaas-{phase}\nlocal-hostname: iaas-{phase}\n", secure=True)
    cloud_localds = shutil.which("cloud-localds")
    if cloud_localds is None:
        raise ValidationError("image executor requires cloud-localds for transient SSH seed")
    _run_tool(execution, f"{phase}-seed", [cloud_localds, str(seed), str(user_data), str(meta_data)], directory)
    return seed, key


def _find_ovmf(kind: str) -> Path:
    variable = "IAAS_OVMF_CODE" if kind == "code" else "IAAS_OVMF_VARS_TEMPLATE"
    configured = os.environ.get(variable)
    candidates = [Path(configured)] if configured else []
    candidates += [Path(f"/usr/share/OVMF/OVMF_{'CODE' if kind == 'code' else 'VARS'}_4M.fd"),
                   Path(f"/usr/share/OVMF/OVMF_{'CODE' if kind == 'code' else 'VARS'}.fd"),
                   Path(f"/usr/share/edk2/ovmf/OVMF_{'CODE' if kind == 'code' else 'VARS'}.fd")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValidationError(f"UEFI {kind} firmware is unavailable")


def _qemu_info(path: Path, execution: Execution | None = None) -> dict[str, Any]:
    qemu_img = shutil.which("qemu-img")
    if qemu_img is None:
        raise ValidationError("image executor requires qemu-img")
    if execution is None:
        result = subprocess.run([qemu_img, "info", "--output=json", str(path)], capture_output=True, text=True, check=False)
        output = result.stdout
    else:
        capture: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="qemu-info-", dir=path.parent, delete=False) as capture_handle:
                capture = Path(capture_handle.name)
                result = subprocess.run([qemu_img, "info", "--output=json", str(path)], stdout=capture_handle,
                                         stderr=subprocess.DEVNULL, timeout=_current_timeout(execution), check=False)
                capture_handle.flush()
                require(capture_handle.tell() <= _current_budget(execution), "qemu-img metadata exceeded output budget")
            assert capture is not None
            output = capture.read_text(encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            raise OperationFailed("qemu-img inspection failed; inspect protected task recovery material") from None
        finally:
            if capture is not None:
                capture.unlink(missing_ok=True)
    require(result.returncode == 0, "qemu-img could not inspect image")
    try:
        info = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        raise ValidationError("qemu-img returned invalid image metadata") from None
    require(isinstance(info, Mapping), "qemu-img metadata is not an object")
    return dict(info)


def _require_self_contained(path: Path, execution: Execution | None = None) -> dict[str, Any]:
    info = _qemu_info(path, execution)
    require(info.get("format") == "qcow2", "image must be qcow2")
    require(not info.get("backing-filename") and not info.get("backing-filename-format"),
            "image has an external backing file")
    return info


def _find_packer_disk(output: Path) -> Path:
    candidates = [item for item in output.rglob("*") if item.is_file() and item.suffix.lower() in {".qcow2", ".img", ".raw"}]
    exact = output / "disk.qcow2"
    if exact.is_file():
        return exact
    require(len(candidates) == 1, "Packer output must contain exactly one disk image")
    return candidates[0]


def _flatten_image(execution: Execution, source: Path, destination: Path, cwd: Path) -> None:
    qemu_img = shutil.which("qemu-img")
    if qemu_img is None:
        raise ValidationError("image build requires qemu-img in the image-builder runtime")
    destination.unlink(missing_ok=True)
    _run_tool(execution, "flatten", [qemu_img, "convert", "-O", "qcow2", "-o", "compat=1.1,compression_type=zstd", str(source), str(destination)], cwd)
    _require_self_contained(destination, execution)


def _offline_cleanup(execution: Execution, disk: Path, cwd: Path) -> None:
    sysprep, customize = shutil.which("virt-sysprep"), shutil.which("virt-customize")
    if sysprep is None or customize is None:
        raise ValidationError("image build requires libguestfs virt-sysprep and virt-customize")
    _run_tool(execution, "offline-sysprep", [sysprep, "-a", str(disk), "--operations",
                                              "machine-id,ssh-hostkeys,cloud-init,logfiles,tmp-files,package-manager-cache,net-hwaddr"], cwd)
    _run_tool(execution, "offline-builder-clean", [customize, "-a", str(disk),
                                                    "--run-command", "rm -f /home/packer/.ssh/authorized_keys",
                                                    "--run-command", "if getent passwd packer >/dev/null; then userdel -r packer; fi",
                                                    "--run-command", "rm -f /etc/sudoers.d/packer /etc/sudoers.d/90-packer",
                                                    "--run-command", "rm -rf /var/lib/cloud/instances /var/lib/cloud/instance",
                                                    "--run-command", "rm -f /etc/network/interfaces.d/packer /etc/netplan/99-packer.yaml",
                                                    "--run-command", "rm -f /etc/ssh/ssh_host_*",
                                                    "--run-command", "truncate -s 0 /etc/machine-id"], cwd)


def _identity_cleanup_status(disk: Path) -> str:
    virt_cat, virt_ls = shutil.which("virt-cat"), shutil.which("virt-ls")
    if virt_cat is None or virt_ls is None:
        return "unknown"
    commands = [
        ([virt_cat, "-a", str(disk), "/etc/machine-id"], "machine"),
        ([virt_ls, "-a", str(disk), "/etc/ssh"], "ssh"),
        ([virt_ls, "-a", str(disk), "/home"], "home"),
        ([virt_ls, "-a", str(disk), "/home/packer/.ssh"], "keys"),
        ([virt_ls, "-a", str(disk), "/etc/sudoers.d"], "sudoers"),
    ]
    results: dict[str, subprocess.CompletedProcess[str]] = {}
    try:
        for command, name in commands:
            results[name] = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if results["machine"].returncode != 0:
        return "failed"
    if results["machine"].stdout.strip():
        return "failed"
    if results["ssh"].returncode != 0 or any(line.startswith("ssh_host_") for line in results["ssh"].stdout.splitlines()):
        return "failed"
    if results["home"].returncode == 0 and any(line.strip() == "packer" for line in results["home"].stdout.splitlines()):
        return "failed"
    if results["keys"].returncode == 0 and any(line.strip() == "authorized_keys" for line in results["keys"].stdout.splitlines()):
        return "failed"
    if results["sudoers"].returncode == 0 and any(line.strip() in {"packer", "90-packer"} for line in results["sudoers"].stdout.splitlines()):
        return "failed"
    return "passed"


def _static_status(check_id: str, *, request: Mapping[str, Any], artifact: Mapping[str, Any] | None = None,
                   disk: Path | None = None, info: Mapping[str, Any] | None = None) -> str:
    if check_id == "format":
        return "passed" if info and info.get("format") == "qcow2" else "failed"
    if check_id == "self-contained":
        return "passed" if info and not info.get("backing-filename") and not info.get("backing-filename-format") else "failed"
    if check_id == "disk-size":
        return "passed" if info and int(info.get("virtual-size", 0)) > 0 else "failed"
    if check_id == "firmware":
        firmware = request.get("guest", {}).get("firmware") if artifact is None else artifact.get("guest", {}).get("firmware")
        return "unknown" if firmware in {"bios", "uefi"} else "failed"
    if check_id == "identity-cleanup":
        require(disk is not None, "identity cleanup check requires a disk")
        assert disk is not None
        return _identity_cleanup_status(disk)
    return "not_performed"


def _new_task(execution_id: str, operation: str, input_digest: str, runtime_digest: str,
              resources: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    return {"kind": "image-task", "schema_version": TASK_VERSION, "execution_id": execution_id,
            "operation": operation, "status": "running", "input_digest": input_digest,
            "runtime_digest": runtime_digest, "resources": dict(resources), "processes": [],
            "owned_resources": [], **extra}


def _set_terminal(path: Path, task: dict[str, Any], status: str, *, reason: str | None = None) -> None:
    task["status"] = status
    if reason:
        task["reason"] = reason
    _write_task(path, task)


def _build_result(execution_id: str, input_digest: str, runtime_digest: str, *, phase: str, status: str,
                  checks: list[dict[str, Any]], cleanup: str, residue: list[str]) -> dict[str, Any]:
    return {"kind": "image-build-result", "schema_version": 1, "execution_id": execution_id,
            "component": "image", "operation": "build", "runtime_digest": runtime_digest,
            "input_digest": input_digest, "phase": phase, "status": status,
            "effects": {"source": "known" if status == "succeeded" else "unknown",
                        "guest": "known" if status == "succeeded" else "unknown"},
            "verification": [{"id": row["id"], "scope": row["scope"], "status": row["status"],
                              "evidence_ref": row.get("evidence_ref")} for row in checks],
            "collection": {"status": "succeeded" if status == "succeeded" else "unknown"},
            "cleanup": {"status": cleanup, "residue": residue}}


def _owned_path(directory: Path, value: str | Path) -> Path:
    path = Path(value)
    require(path.is_absolute() and path.resolve().is_relative_to(directory.resolve()),
            "image task resource is outside its execution directory")
    return path


def _remove_owned(directory: Path, task: dict[str, Any], *, preserve: set[Path]) -> tuple[list[str], list[str]]:
    if _task_has_active_process(task) or _task_has_uncertain_process(task):
        failures: list[str] = []
        for raw in task.get("owned_resources", []):
            try:
                path = _owned_path(directory, raw)
            except ValidationError:
                failures.append(str(raw))
                continue
            if path not in preserve and path not in {directory / "task.json", directory / "resource.lock"}:
                failures.append(str(path))
        task.setdefault("cleanup_errors", []).append("owned process state is active or unknown")
        return [], failures
    removed, failures = [], []
    for raw in task.get("owned_resources", []):
        try:
            path = _owned_path(directory, raw)
            if path in preserve or path in {directory / "task.json", directory / "resource.lock"}:
                continue
            if not path.exists() and not path.is_symlink():
                continue
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(str(path))
        except (OSError, ValidationError) as exc:
            failures.append(str(raw))
            task.setdefault("cleanup_errors", []).append(str(exc))
    return removed, failures


def _build(selected: Any, execution: Execution, execution_id: str, resolved_runtime_digest: str | None = None) -> None:
    request = validate_build_request(_document(selected))
    runtime_digest = _runtime_digest(selected, resolved_runtime_digest)
    execution.__dict__["image_max_output_bytes"] = request["resources"]["max_output_bytes"]
    execution.__dict__["image_timeout_seconds"] = request["resources"]["timeout_seconds"]
    task = _task_dir(execution, execution_id)
    task_path, input_digest = task / "task.json", canonical_digest(request)
    with _resource_lock(task):
        if task_path.exists():
            previous = load_json(task_path)
            require(isinstance(previous, Mapping) and previous.get("input_digest") == input_digest,
                    "execution_id is already bound to different image inputs")
            require(previous.get("status") not in {"running", "succeeded", "failed", "unknown", "interrupted"},
                    "existing image execution cannot be replayed")
        facts = _require_executor(request["resources"])
        task_record = _new_task(execution_id, "build", input_digest, runtime_digest, facts)
        base, packer_output, disk = task / "base.img", task / "packer-output", task / "disk.qcow2"
        build_result_path = task / "build-result.json"
        task_record["owned_resources"] = [str(base), str(packer_output), str(disk), str(build_result_path)]
        _write_task(task_path, task_record)
        build_result = _build_result(execution_id, input_digest, runtime_digest, phase="running", status="unknown",
                                     checks=[], cleanup="unknown", residue=[])
        _write_task(build_result_path, build_result)
        statuses: list[dict[str, Any]] = []
        try:
            _download_base(request, base, request["resources"])
            _require_self_contained(base, execution)
            task_record["base_sha256"] = _sha256_file(base)
            _write_task(task_path, task_record)
            _seed, key = _make_seed(execution, task, username="packer", phase="build", task=task_record)
            build_vars: Path | None = None
            if request["guest"]["firmware"] == "uefi":
                build_vars = task / "build.VARS.fd"
                shutil.copyfile(_find_ovmf("vars"), build_vars)
                task_record["owned_resources"].append(str(build_vars))
            _write_task(task_path, task_record)
            packer = shutil.which("packer")
            if packer is None:
                raise ValidationError("image build requires pinned packer in the image-builder runtime")
            profile = Path(__file__).resolve().parents[4] / "automation/packer/qemu/debian-13/packer.pkr.hcl"
            custom, env = request["customization"], dict(execution.environ)
            env.update({"PKR_VAR_base_image": str(base),
                        "PKR_VAR_base_checksum": f"{request['base']['checksum']['algorithm']}:{request['base']['checksum']['value']}",
                        "PKR_VAR_output_directory": str(packer_output), "PKR_VAR_firmware": request["guest"]["firmware"],
                        "PKR_VAR_seed_directory": str(task), "PKR_VAR_ssh_private_key_file": str(key),
                        "PKR_VAR_ssh_username": "packer", "PKR_VAR_apt_mirror": custom.get("apt_mirror", "https://deb.debian.org/debian"),
                        "PKR_VAR_apt_security_mirror": custom.get("apt_security_mirror", "https://security.debian.org/debian-security"),
                        "PKR_VAR_packages": json.dumps(custom.get("packages", [])), "PKR_VAR_timezone": custom.get("timezone", "UTC"),
                        "PKR_VAR_locale": custom.get("locale", "C.UTF-8"), "PKR_VAR_cloud_init": custom.get("cloud_init", "installed"),
                        "PKR_VAR_guest_agent": custom.get("guest_agent", "installed"),
                        "PKR_VAR_cpus": str(request["resources"]["cpus"]),
                        "PKR_VAR_memory_mib": str(request["resources"]["memory_mib"]),
                        "PKR_VAR_uefi_code": str(_find_ovmf("code")) if request["guest"]["firmware"] == "uefi" else "",
                        "PKR_VAR_uefi_vars": str(build_vars) if build_vars else ""})
            old_environ = execution.environ
            execution.environ = env
            try:
                packer_command: list[str] = [packer, "build", "-machine-readable", str(profile)]
                timeout_bin = shutil.which("timeout")
                if timeout_bin is not None:
                    packer_command = [timeout_bin, "--signal=TERM", str(request["resources"]["timeout_seconds"]), *packer_command]
                _run_tracked_tool(execution, task, task_record, "packer-build", packer_command, task)
            finally:
                execution.environ = old_environ
            _flatten_image(execution, _find_packer_disk(packer_output), disk, task)
            _offline_cleanup(execution, disk, task)
            info = _require_self_contained(disk, execution)
            statuses = [{"id": item["id"], "scope": item["scope"],
                         "status": _static_status(item["id"], request=request, disk=disk, info=info),
                         "evidence_ref": "task.json"}
                        for item in request["checks"]["required"] + request["checks"]["optional"]]
            dynamic = {row["id"] for row in statuses if row["id"] in DYNAMIC_CHECKS}
            if dynamic or any(row["id"] == "firmware" for row in statuses):
                boot_status = _boot_guest(execution, task, task_record, disk, request["guest"]["firmware"], request["resources"], username=TEST_USER, phase="build-test")
                statuses = [{**row, "status": boot_status.get(row["id"], row["status"])} for row in statuses]
            _finalize_artifact(task, request, runtime_digest, execution_id, statuses, info)
            task_record["artifact"] = "artifact.json"
            task_record["owned_resources"] += [str(disk), str(task / "artifact.json"), str(task / "disk.qcow2.sha256"), str(base), str(packer_output)]
            removed, failures = _remove_owned(task, task_record, preserve={disk, task / "artifact.json", task / "disk.qcow2.sha256", build_result_path})
            task_record["cleanup"] = {"status": "failed" if failures else "succeeded", "removed": removed, "failures": failures}
            required_ids = {item["id"] for item in request["checks"]["required"]}
            require(all(row["status"] == "passed" for row in statuses if row["id"] in required_ids), "required image checks did not pass")
            build_result = _build_result(execution_id, input_digest, runtime_digest, phase="succeeded", status="succeeded",
                                         checks=statuses, cleanup="failed" if failures else "succeeded", residue=failures)
            _write_task(build_result_path, build_result)
            _set_terminal(task_path, task_record, "succeeded" if not failures else "failed")
            if failures:
                raise OperationFailed("image build cleanup incomplete; inspect protected task recovery material")
        except KeyboardInterrupt:
            build_result = _build_result(execution_id, input_digest, runtime_digest, phase="interrupted", status="interrupted",
                                         checks=[], cleanup="unknown", residue=[])
            _write_task(build_result_path, build_result)
            _set_terminal(task_path, task_record, "interrupted", reason="image build was cancelled")
            raise OperationFailed("image build interrupted; inspect protected task recovery material") from None
        except Exception as exc:
            cleanup_record = task_record.get("cleanup", {})
            cleanup_status = cleanup_record.get("status", "unknown") if isinstance(cleanup_record, Mapping) else "unknown"
            residue = cleanup_record.get("failures", []) if isinstance(cleanup_record, Mapping) else []
            build_result = _build_result(execution_id, input_digest, runtime_digest, phase="failed", status="failed",
                                         checks=statuses, cleanup=cleanup_status if cleanup_status in {"succeeded", "failed", "unknown"} else "unknown",
                                         residue=residue if isinstance(residue, list) else [])
            _write_task(build_result_path, build_result)
            _set_terminal(task_path, task_record, "failed", reason=str(exc))
            raise


def _finalize_artifact(task: Path, request: Mapping[str, Any], runtime_digest: str, execution_id: str,
                      statuses: list[dict[str, Any]], info: Mapping[str, Any]) -> dict[str, Any]:
    disk, size = task / "disk.qcow2", (task / "disk.qcow2").stat().st_size
    digest, virtual_size = _sha256_file(disk), int(info.get("virtual-size", size))
    artifact = validate_artifact({"kind": "image-artifact", "schema_version": 1, "artifact_id": execution_id,
        "version": request["version"], "disk": {"path": "disk.qcow2", "format": "qcow2", "sha256": digest,
        "size_bytes": size, "virtual_size_bytes": virtual_size, "self_contained": True},
        "guest": {"architecture": "amd64", "firmware": request["guest"]["firmware"],
        "cloud_init": request["customization"].get("cloud_init", "installed"), "guest_agent": request["customization"].get("guest_agent", "installed")},
        "build": {"origin": "iaas", "recipe_id": request["profile"]["id"], "recipe_version": request["profile"]["version"],
        "runtime_digest": runtime_digest, "config_digest": canonical_digest(request), "execution_id": execution_id},
        "checks": statuses}, artifact_root=task, require_disk=True)
    write_text(task / "disk.qcow2.sha256", f"{digest}  disk.qcow2\n")
    _write_task(task / "artifact.json", artifact)
    return artifact


def _start_qemu(command: Sequence[str], cwd: Path, capture: Path, *, pid_file: Path | None = None) -> tuple[subprocess.Popen[bytes], Any]:
    capture.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(capture, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    sink = os.fdopen(fd, "wb", buffering=0)
    try:
        actual = [sys.executable, "-c", _TRACKER, str(pid_file), *command] if pid_file is not None else list(command)
        process = subprocess.Popen(actual, cwd=cwd, stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT, start_new_session=True, env=os.environ.copy())
    except OSError:
        sink.close()
        raise OperationFailed("qemu could not start; protected capture retained") from None
    return process, sink


def _wait_port(process: subprocess.Popen[bytes], port: int, timeout: int, *, deadline: float | None = None) -> None:
    deadline = deadline or time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise OperationFailed("disposable guest exited before SSH became available")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise OperationFailed("disposable guest did not become reachable within its budget")


def _watch_output(path: Path, process: subprocess.Popen[bytes], limit: int,
                  stop: threading.Event, overflow: threading.Event) -> None:
    """Stop a QEMU process whose durable capture exceeds the image budget."""
    while not stop.wait(0.05):
        try:
            exceeded = path.stat().st_size > limit
        except OSError:
            exceeded = False
        if exceeded:
            overflow.set()
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            return


def _boot_guest(execution: Execution, directory: Path, task: dict[str, Any], disk: Path, firmware: str,
                resources: Mapping[str, int], *, username: str, phase: str) -> dict[str, str]:
    qemu, qemu_img = shutil.which("qemu-system-x86_64"), shutil.which("qemu-img")
    if qemu is None or qemu_img is None:
        raise ValidationError("image test requires qemu-system-x86_64 and qemu-img")
    overlay, vars_path = directory / f"{phase}.overlay.qcow2", None
    owned: list[Path] = [overlay]
    if firmware == "uefi":
        vars_path = directory / f"{phase}.VARS.fd"
        owned.append(vars_path)
    pid_file = directory / f"{phase}.pid"
    owned += [directory / f"{phase}.known_hosts", directory / f"{phase}.serial.log",
              directory / f"{phase}.qemu.raw", directory / f"{phase}.qga.sock", pid_file]
    task.setdefault("owned_resources", []).extend(str(item) for item in owned if str(item) not in task.get("owned_resources", []))
    _write_task(directory / "task.json", task)
    _run_tool(execution, f"{phase}-overlay", [qemu_img, "create", "-f", "qcow2", "-F", "qcow2", "-b", str(disk), str(overlay)], directory)
    if firmware == "uefi":
        assert vars_path is not None
        shutil.copyfile(_find_ovmf("vars"), vars_path)
    seed, key = _make_seed(execution, directory, username=username, phase=phase, task=task)
    for item in (seed, key, Path(f"{key}.pub"), directory / f"{phase}.user-data", directory / f"{phase}.meta-data"):
        if str(item) not in task.get("owned_resources", []):
            task.setdefault("owned_resources", []).append(str(item))
    _write_task(directory / "task.json", task)
    port_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_socket.bind(("127.0.0.1", 0))
    port = int(port_socket.getsockname()[1])
    port_socket.close()
    command = [qemu, "-enable-kvm", "-machine", "q35", "-cpu", "host", "-m", str(resources["memory_mib"]), "-smp", str(resources["cpus"]),
               "-display", "none", "-serial", "file=" + str(directory / f"{phase}.serial.log"), "-no-reboot",
               "-drive", f"file={overlay},if=virtio,format=qcow2", "-drive", f"file={seed},media=cdrom,readonly=on,format=raw",
               "-chardev", f"socket,id=qga,path={directory / f'{phase}.qga.sock'},server=on,wait=off",
               "-device", "virtio-serial", "-device", "virtserialport,chardev=qga,name=org.qemu.guest_agent.0",
               "-netdev", f"user,id=n0,hostfwd=tcp:127.0.0.1:{port}-:22", "-device", "virtio-net-pci,netdev=n0"]
    if firmware == "uefi":
        command[1:1] = ["-drive", f"if=pflash,format=raw,readonly=on,file={_find_ovmf('code')}", "-drive", f"if=pflash,format=raw,file={vars_path}"]
    entry = {"pid": None, "start_ticks": None, "pid_file": str(pid_file), "state": "starting", "command": [qemu], "phase": phase}
    task.setdefault("processes", []).append(entry)
    _write_task(directory / "task.json", task)
    process, sink = _start_qemu(command, directory, directory / f"{phase}.qemu.raw", pid_file=pid_file)
    entry.update(pid=process.pid, start_ticks=_proc_start_ticks(process.pid), state="running")
    _write_task(directory / "task.json", task)
    watch_stop = threading.Event()
    watch_overflow = threading.Event()
    watcher = threading.Thread(target=_watch_output,
                                args=(directory / f"{phase}.qemu.raw", process,
                                      resources["max_output_bytes"], watch_stop, watch_overflow), daemon=True)
    watcher.start()
    try:
        _wait_port(process, port, resources["timeout_seconds"])
        if watch_overflow.is_set():
            raise OperationFailed("disposable guest exceeded the protected output budget")
        statuses = {"first-boot": "failed", "firmware": "unknown"}
        ssh = shutil.which("ssh")
        if ssh is None:
            raise ValidationError("image test requires ssh")
        common = [ssh, "-i", str(key), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=" + str(directory / f"{phase}.known_hosts"), "-o", "ConnectTimeout=3", "-p", str(port), f"{username}@127.0.0.1"]
        timeout_bin = shutil.which("timeout")
        if timeout_bin is None:
            raise ValidationError("image test requires timeout for the guest command budget")
        deadline = time.monotonic() + resources["timeout_seconds"]
        attempt = 0
        while True:
            if watch_overflow.is_set():
                raise OperationFailed("disposable guest exceeded the protected output budget")
            try:
                _run_tool(execution, f"{phase}-first-boot-{attempt}", [timeout_bin, str(resources["timeout_seconds"]), *common, "true"], directory)
                statuses.update({"first-boot": "passed", "firmware": "passed"})
                break
            except (OperationFailed, ValidationError):
                if time.monotonic() >= deadline:
                    return statuses
                attempt += 1
                time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        for check_id, remote in (("cloud-init", "cloud-init status --wait"), ("guest-agent", "systemctl is-active --quiet qemu-guest-agent")):
            try:
                _run_tool(execution, f"{phase}-{check_id}", [timeout_bin, str(resources["timeout_seconds"]), *common, remote], directory)
                statuses[check_id] = "passed"
            except (OperationFailed, ValidationError):
                statuses[check_id] = "failed"
        return statuses
    finally:
        watch_stop.set()
        watcher.join(timeout=1)
        _stop_process(process, entry)
        _write_task(directory / "task.json", task)
        sink.close()


def _unknown_test_result(execution_id: str, digest: str, runtime_digest: str, input_digest: str,
                         checks: Mapping[str, Any], phase: str) -> dict[str, Any]:
    rows = checks.get("required", []) + checks.get("optional", [])
    return {"kind": "image-test-result", "schema_version": 1, "execution_id": execution_id, "component": "image", "operation": "test", "phase": phase, "status": phase,
            "effects": {"guest": "unknown", "source": "unknown"}, "verification": [], "collection": {"status": "unknown"}, "disk_sha256": digest,
            "input_digest": input_digest,
            "test_config_digest": canonical_digest(checks), "runtime_digest": runtime_digest,
            "checks": [{"id": item["id"], "scope": item["scope"], "status": "unknown", "evidence_ref": None} for item in rows],
            "base_unchanged": None, "cleanup": {"status": "unknown", "residue": []}}


def _test(selected: Any, execution: Execution, execution_id: str, resolved_runtime_digest: str | None = None) -> None:
    request = validate_test_request(_document(selected))
    runtime_digest = _runtime_digest(selected, resolved_runtime_digest)
    execution.__dict__["image_max_output_bytes"] = request["resources"]["max_output_bytes"]
    execution.__dict__["image_timeout_seconds"] = request["resources"]["timeout_seconds"]
    root = Path(request["artifact_root"]).resolve()
    artifact = validate_artifact(request["artifact"], artifact_root=root, require_disk=True)
    disk = resolve_artifact_path(root, artifact)
    before = _sha256_file(disk)
    require(before == artifact["disk"]["sha256"], "test source digest does not match artifact")
    facts = _require_executor(request["resources"])
    directory, input_digest = _task_dir(execution, execution_id), canonical_digest(request)
    task_path = directory / "task.json"
    with _resource_lock(directory):
        if task_path.exists():
            previous = load_json(task_path)
            require(isinstance(previous, Mapping) and previous.get("input_digest") == input_digest, "execution_id is already bound to different image inputs")
            require(previous.get("status") not in {"running", "succeeded", "failed", "unknown", "interrupted"}, "existing image execution cannot be replayed")
        task = _new_task(execution_id, "test", input_digest, runtime_digest, facts, disk_sha256=before, source=str(disk), source_root=str(root))
        _write_task(task_path, task)
        result: dict[str, Any] | None = None
        try:
            info = _require_self_contained(disk, execution)
            rows = request["checks"]["required"] + request["checks"]["optional"]
            checks = [{"id": item["id"], "scope": item["scope"], "status": _static_status(item["id"], request=request, artifact=artifact, disk=disk, info=info) if item["id"] in STATIC_CHECKS else "not_performed", "evidence_ref": "test-result.json"} for item in rows]
            boot_status = _boot_guest(execution, directory, task, disk, artifact["guest"]["firmware"], request["resources"], username=TEST_USER, phase="test")
            checks = [{**row, "status": boot_status.get(row["id"], row["status"])} for row in checks]
            base_unchanged = _sha256_file(disk) == before
            required_ids = {item["id"] for item in request["checks"]["required"]}
            required_ok = base_unchanged and all(row["status"] == "passed" for row in checks if row["id"] in required_ids)
            result = {"kind": "image-test-result", "schema_version": 1, "execution_id": execution_id, "component": "image", "operation": "test",
                      "phase": "succeeded" if required_ok else "failed", "status": "succeeded" if required_ok else "failed", "effects": {"guest": "known", "source": "none"},
                      "verification": [{"id": "base-unchanged", "scope": "source", "status": "passed" if base_unchanged else "failed", "evidence_ref": "test-result.json"}], "collection": {"status": "succeeded"}, "disk_sha256": before,
                      "input_digest": input_digest,
                      "test_config_digest": canonical_digest(request["checks"]), "runtime_digest": runtime_digest, "checks": checks,
                      "base_unchanged": base_unchanged, "cleanup": {"status": "succeeded", "residue": []}}
            validate_test_result(result)
            _write_task(directory / "test-result.json", result)
            _set_terminal(task_path, task, "succeeded" if required_ok else "failed")
            if not required_ok:
                raise OperationFailed("required image test checks failed; inspect image-test-result/v1")
        except KeyboardInterrupt:
            result = result or _unknown_test_result(execution_id, before, runtime_digest, input_digest, request["checks"], "interrupted")
            _write_task(directory / "test-result.json", result)
            _set_terminal(task_path, task, "interrupted", reason="image test was cancelled")
            raise OperationFailed("image test interrupted; inspect protected task recovery material") from None
        except Exception as exc:
            if result is None:
                result = _unknown_test_result(execution_id, before, runtime_digest, input_digest, request["checks"], "failed")
                _write_task(directory / "test-result.json", result)
            _set_terminal(task_path, task, "failed", reason=str(exc))
            raise
        finally:
            preserve = {task_path, directory / "test-result.json"}
            removed, failures = _remove_owned(directory, task, preserve=preserve)
            task["cleanup"] = {"status": "failed" if failures else "succeeded", "removed": removed, "failures": failures}
            if result is not None:
                result["cleanup"] = {"status": "failed" if failures else result["cleanup"]["status"],
                                      "residue": failures}
                _write_task(directory / "test-result.json", result)
            if failures and task.get("status") == "succeeded":
                task["status"] = "failed"
            _write_task(task_path, task)
        if task.get("status") == "failed" and task.get("cleanup", {}).get("status") == "failed":
            raise OperationFailed("image test cleanup incomplete; inspect image-test-result/v1")


def _clean(selected: Any, execution: Execution, execution_id: str) -> None:
    directory, _ = _load_task(selected, execution, execution_id)
    with _resource_lock(directory):
        loaded = load_json(directory / "task.json")
        require(isinstance(loaded, Mapping), "image task record is invalid")
        task = dict(loaded)
        if _task_has_active_process(task):
            raise ValidationError("image task still has an active owned process")
        if _task_has_uncertain_process(task):
            raise ValidationError("image task still has an unknown owned process")
        if task.get("status") in {"running", "unknown"}:
            if task.get("status") == "running":
                task["status"], task["reason"] = "unknown", "no live owned process confirms running state"
                _write_task(directory / "task.json", task)
            raise ValidationError("image cleanup requires a known terminal task state")
        preserve = {directory / "task.json", directory / "resource.lock", directory / "artifact.json", directory / "disk.qcow2", directory / "disk.qcow2.sha256", directory / "test-result.json"}
        removed, failures = _remove_owned(directory, task, preserve=preserve)
        attempt = {"status": "failed" if failures else "succeeded", "removed": removed, "failures": failures, "timestamp": int(time.time())}
        task.setdefault("cleanup_attempts", []).append(attempt)
        task["cleanup"] = attempt
        _write_task(directory / "task.json", task)
    summary = {"component": "image", "operation": "clean", "execution_id": execution_id,
               "status": "succeeded" if not failures else "failed", "cleanup": attempt["status"]}
    execution.finish(summary)
    if failures:
        execution.outputs.summary({**summary, "status": "failed", "phases": execution.phases})


def run(selected: Any, operation: str, execution: Execution, *, execution_id: str | None = None,
        runtime_digest: str | None = None) -> None:
    require(operation in {"check", "build", "test", "read", "verify", "clean"}, "unsupported image operation")
    options = _options(selected)
    require(not set(options) - {"execution_id", "execution_dir", "runtime_digest", "artifact_root"}, "unknown image operation option")
    if operation == "check":
        document = _document(selected)
        if document.get("kind") == "image-build-request":
            normalized = validate_build_request(document)
            executor = _executor_check(normalized["resources"])
        elif document.get("kind") == "image-test-request":
            normalized = validate_test_request(document)
            executor = _executor_check(normalized["resources"])
        elif document.get("kind") == "image-artifact":
            normalized = validate_artifact(document)
            executor = {"note": "passive artifact check"}
        elif document.get("kind") == "image-test-result":
            normalized = validate_test_result(document)
            executor = {"note": "passive result check"}
        else:
            raise ValidationError("unsupported image check input")
        write_text(execution.outputs.path("diagnostics") / "normalized.json", json.dumps({"kind": normalized["kind"], "schema_version": normalized["schema_version"], "input_digest": canonical_digest(normalized), "input": normalized}, sort_keys=True, indent=2, allow_nan=False) + "\n", secure=True)
        execution.finish({"component": "image", "operation": operation, "schema_version": 1, "input_digest": canonical_digest(normalized), "executor": executor})
        return
    identity = _execution_id(selected, execution_id)
    if operation == "build":
        _build(selected, execution, identity, runtime_digest)
        task = load_json(execution.outputs.path("work") / "image-tasks" / identity / "task.json")
        summary = {"component": "image", "operation": operation, "execution_id": identity, "status": task.get("status", "unknown") if isinstance(task, Mapping) else "unknown"}
        execution.finish(summary)
        if summary["status"] != "succeeded":
            execution.outputs.summary({**summary, "status": "failed", "phases": execution.phases})
    elif operation == "test":
        _test(selected, execution, identity, runtime_digest)
        task = load_json(execution.outputs.path("work") / "image-tasks" / identity / "task.json")
        summary = {"component": "image", "operation": operation, "execution_id": identity, "status": task.get("status", "unknown") if isinstance(task, Mapping) else "unknown"}
        execution.finish(summary)
        if summary["status"] != "succeeded":
            execution.outputs.summary({**summary, "status": "failed", "phases": execution.phases})
    elif operation == "clean":
        _clean(selected, execution, identity)
    elif operation == "read":
        directory, task = _load_task(selected, execution, identity)
        if task.get("status") == "running" and not _task_has_active_process(task):
            task = {**task, "status": "unknown", "reason": "no live owned process confirms running state"}
        _write_task(execution.outputs.path("diagnostics") / "task.json", task)
        execution.finish({"component": "image", "operation": operation, "execution_id": identity, "status": task.get("status", "unknown"), "task_dir": str(directory)})
    else:
        artifact_path = _path(selected, "artifact")
        if artifact_path is None:
            raise ValidationError("image verify requires artifact.json")
        artifact = load_strict_json(artifact_path)
        require(isinstance(artifact, Mapping), "artifact must contain a mapping")
        root = Path(str(options.get("artifact_root", artifact_path.parent))).resolve()
        validated = validate_artifact(artifact, artifact_root=root, require_disk=True)
        _write_task(execution.outputs.path("diagnostics") / "artifact.json", validated)
        execution.finish({"component": "image", "operation": operation, "status": "verified", "artifact_digest": canonical_digest(validated)})
