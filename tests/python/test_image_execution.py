from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import pytest
from iaas_automation.common.errors import ValidationError
from iaas_automation.image import runtime
from iaas_automation.image.contracts import (
    canonical_digest,
    validate_artifact,
    validate_build_request,
    validate_test_result,
)
from iaas_automation.runtime_execution.execution import Execution, OperationFailed
from iaas_automation.runtime_execution.outputs import TaskOutputs


def _request(*, firmware: str = "uefi", checks: dict | None = None) -> dict:
    return {
        "kind": "image-build-request", "schema_version": 1,
        "profile": {"id": "debian-13-amd64", "version": "1"}, "version": "v1",
        "base": {"object_ref": "https://objects.example.invalid/debian.qcow2",
                 "checksum": {"algorithm": "sha256", "value": "a" * 64}},
        "guest": {"architecture": "amd64", "firmware": firmware}, "customization": {},
        "resources": {"cpus": 1, "memory_mib": 512, "work_min_free_bytes": 1,
                       "max_output_bytes": 65536, "timeout_seconds": 2},
        "checks": checks or {"required": ["format"], "optional": []},
    }


def _execution(tmp_path: Path) -> Execution:
    implementation = tmp_path / "implementation"
    implementation.mkdir()
    outputs = TaskOutputs.create(tmp_path / "outputs", implementation, [])
    return Execution(outputs, {})


def _selected(document: dict, *, execution_id: str, execution_dir: Path | None = None,
              files: dict | None = None, options: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(documents={"request": document}, files=files or {},
                           options={"execution_id": execution_id,
                                    "runtime_digest": "runtime@sha256:" + "b" * 64,
                                    **({"execution_dir": str(execution_dir)} if execution_dir else {}),
                                    **(options or {})})


def _write_task(directory: Path, value: dict) -> None:
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    (directory / "task.json").write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_duplicate_active_execution_id_is_rejected(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    request = _request()
    directory = runtime._task_dir(execution, "same-id")
    _write_task(directory, {"execution_id": "same-id", "input_digest": canonical_digest(validate_build_request(request)), "status": "running"})

    with pytest.raises(ValidationError, match="cannot be replayed"):
        runtime._build(_selected(request, execution_id="same-id"), execution, "same-id")


@pytest.mark.parametrize("execution_id", [".", "..", "-bad"])
def test_execution_id_rejects_path_like_values(execution_id: str) -> None:
    with pytest.raises(ValidationError, match="bounded execution_id"):
        runtime._execution_id(SimpleNamespace(options={"execution_id": execution_id}), None)


def test_task_lock_rejects_duplicate_owner(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "locked")
    with runtime._resource_lock(directory), pytest.raises(ValidationError, match="resource lock is active"), runtime._resource_lock(directory):
        pass


def test_seed_paths_are_journaled_before_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "seed-failure")
    task = {"execution_id": "seed-failure", "owned_resources": []}

    def fail_tool(*args: object, **kwargs: object) -> None:
        raise ValidationError("controlled seed tool failure")

    monkeypatch.setattr(runtime, "_run_tool", fail_tool)
    with pytest.raises(ValidationError, match="controlled seed"):
        runtime._make_seed(execution, directory, username="packer", phase="build", task=task)
    recorded = json.loads((directory / "task.json").read_text(encoding="utf-8"))
    assert {str(directory / name) for name in ("build.seed.img", "build.key", "build.key.pub", "build.user-data", "build.meta-data")} <= set(recorded["owned_resources"])


def test_process_group_is_stopped_on_cancellation(tmp_path: Path) -> None:
    child_file = tmp_path / "child.pid"
    process = subprocess.Popen([sys.executable, "-c",
                                "import pathlib,subprocess; p=subprocess.Popen(['sleep','60']); pathlib.Path(__import__('sys').argv[1]).write_text(str(p.pid))",
                                str(child_file)], start_new_session=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 2
    while not child_file.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    entry = {"pid": process.pid, "start_ticks": runtime._proc_start_ticks(process.pid), "state": "running"}
    process.wait()
    runtime._stop_process(process, entry)
    assert process.poll() is not None
    assert entry["state"] == "stopped"
    child_pid = int(child_file.read_text())
    for _ in range(100):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.01)
    else:
        pytest.fail("descendant process survived process-group stop")


def test_tracked_tool_keeps_unknown_state_when_descendant_holds_capture(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "tracked-descendant")
    task = {"execution_id": "tracked-descendant", "owned_resources": [], "processes": []}
    _write_task(directory, task)
    command = ["/bin/sh", "-c", "sleep 60 & exit 0"]
    with pytest.raises(OperationFailed, match="tracked failed"):
        runtime._run_tracked_tool(execution, directory, task, "tracked", command, directory)
    recorded = json.loads((directory / "task.json").read_text(encoding="utf-8"))
    entry = recorded["processes"][0]
    assert entry["state"] == "unknown"
    try:
        os.killpg(int(entry["pid"]), 9)
    except ProcessLookupError:
        pass


def test_clean_rejects_active_and_unknown_resources(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "live")
    process = subprocess.Popen(["sleep", "60"], start_new_session=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _write_task(directory, {"execution_id": "live", "status": "running", "processes": [
        {"pid": process.pid, "start_ticks": runtime._proc_start_ticks(process.pid), "state": "running"}],
        "owned_resources": []})
    selected = _selected({}, execution_id="live", execution_dir=directory)
    try:
        with pytest.raises(ValidationError, match="active owned process"):
            runtime._clean(selected, execution, "live")
        runtime._stop_process(process, {"pid": process.pid, "start_ticks": None, "state": "running"})
        _write_task(directory, {"execution_id": "live", "status": "running", "processes": [], "owned_resources": []})
        with pytest.raises(ValidationError, match="known terminal"):
            runtime._clean(selected, execution, "live")
        assert json.loads((directory / "task.json").read_text())["status"] == "unknown"
        uncertain = runtime._task_dir(execution, "uncertain")
        owned = uncertain / "owned"
        owned.write_text("retain")
        _write_task(uncertain, {"execution_id": "uncertain", "status": "failed",
                                "processes": [{"pid": 999999, "start_ticks": None, "state": "unknown"}],
                                "owned_resources": [str(owned)]})
        with pytest.raises(ValidationError, match="unknown owned process"):
            runtime._clean(_selected({}, execution_id="uncertain", execution_dir=uncertain), execution, "uncertain")
        assert owned.exists()
    finally:
        if process.poll() is None:
            runtime._stop_process(process, {"pid": process.pid, "start_ticks": None, "state": "running"})


def test_wrong_checksum_and_external_backing_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disk = tmp_path / "disk.qcow2"
    disk.write_bytes(b"image")
    artifact = {
        "kind": "image-artifact", "schema_version": 1, "artifact_id": "a", "version": "v1",
        "disk": {"path": "disk.qcow2", "format": "qcow2", "sha256": "0" * 64,
                  "size_bytes": 5, "virtual_size_bytes": 4096, "self_contained": True},
        "guest": {"architecture": "amd64", "firmware": "bios", "cloud_init": "unknown", "guest_agent": "unknown"},
        "build": {"origin": "iaas", "recipe_id": "debian-13-amd64", "recipe_version": "1",
                  "runtime_digest": "runtime@sha256:" + "b" * 64,
                  "config_digest": "sha256:" + "c" * 64, "execution_id": "build-1"}, "checks": [],
    }
    with pytest.raises(ValidationError, match="SHA-256"):
        validate_artifact(artifact, artifact_root=tmp_path, require_disk=True)

    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/usr/bin/qemu-img")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=json.dumps({"format": "qcow2", "backing-filename": "/outside/base.qcow2"})))
    with pytest.raises(ValidationError, match="backing"):
        runtime._require_self_contained(disk)


def test_base_download_rejects_declared_size_over_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self) -> None:
            self.headers = {"Content-Length": "100"}

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            return b"x" * size

    monkeypatch.setattr(runtime, "urlopen", lambda *args, **kwargs: Response())
    request = _request()
    resources = {**request["resources"], "work_min_free_bytes": shutil.disk_usage(tmp_path).free}
    with pytest.raises(OperationFailed, match="bounded download"):
        runtime._download_base(request, tmp_path / "base.qcow2", resources)


def test_image_tool_timeout_stops_the_process_group(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    execution.image_timeout_seconds = 1
    execution.image_max_output_bytes = 1024
    with pytest.raises(OperationFailed, match="hang failed"):
        runtime._run_tool(execution, "hang", [sys.executable, "-c", "import time; time.sleep(30)"], tmp_path)


def test_image_tool_output_budget_stops_a_chatty_process(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    execution.image_timeout_seconds = 5
    execution.image_max_output_bytes = 128
    with pytest.raises(OperationFailed, match="spam failed"):
        runtime._run_tool(execution, "spam", [sys.executable, "-c", "print('x' * 100000)"], tmp_path)
    capture = execution.outputs.path("recovery") / "spam.raw"
    assert capture.stat().st_size <= 128


def test_test_boot_uses_fresh_uefi_vars_and_preserves_source_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "uefi")
    disk = directory / "disk.qcow2"
    disk.write_bytes(b"source disk")
    vars_template = tmp_path / "OVMF_VARS.fd"
    vars_template.write_bytes(b"fresh-template")
    monkeypatch.setattr(runtime, "_find_ovmf", lambda kind: vars_template)
    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/usr/bin/tool")
    def fake_tool(exe: Execution, phase: str, command: list[str], cwd: Path) -> None:
        if command[0] == "ssh-keygen":
            key = Path(command[-1]); key.write_text("private\n"); Path(str(key) + ".pub").write_text("public\n")
        elif command[0] == "cloud-localds":
            Path(command[1]).write_bytes(b"seed")
    monkeypatch.setattr(runtime, "_run_tool", fake_tool)
    monkeypatch.setattr(runtime, "_wait_port", lambda process, port, timeout: None)
    class FakeProcess:
        pid = os.getpid()
        returncode = 0
        def poll(self) -> int: return 0
        def wait(self, timeout: int | None = None) -> int: return 0
    monkeypatch.setattr(runtime, "_start_qemu", lambda command, cwd, capture, **kwargs: (FakeProcess(), io.BytesIO()))
    monkeypatch.setattr(runtime, "_stop_process", lambda process, entry: entry.update(state="stopped", exit_code=0))
    task = {"processes": [], "owned_resources": []}
    before = runtime._sha256_file(disk)
    runtime._boot_guest(execution, directory, task, disk, "uefi", _request()["resources"], username="iaas-test", phase="test-a")
    runtime._boot_guest(execution, directory, task, disk, "uefi", _request()["resources"], username="iaas-test", phase="test-b")
    assert (directory / "test-a.VARS.fd").read_bytes() == vars_template.read_bytes()
    assert (directory / "test-b.VARS.fd").read_bytes() == vars_template.read_bytes()
    assert (directory / "test-a.VARS.fd") != (directory / "test-b.VARS.fd")
    assert runtime._sha256_file(disk) == before


def test_cleanup_failure_keeps_test_result_and_records_residue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "cleanup-fail")
    residue = directory / "owned"
    residue.mkdir()
    (residue / "secret.tmp").write_text("x")
    result = {"kind": "image-test-result", "schema_version": 1, "execution_id": "cleanup-fail",
              "component": "image", "operation": "test", "phase": "failed", "status": "failed",
              "effects": {"guest": "none", "source": "none"}, "verification": [],
              "collection": {"status": "succeeded"}, "disk_sha256": "a" * 64,
              "input_digest": "sha256:" + "c" * 64,
              "test_config_digest": "sha256:" + "a" * 64, "runtime_digest": "runtime@sha256:" + "b" * 64,
              "checks": [], "base_unchanged": False, "cleanup": {"status": "unknown", "residue": []}}
    (directory / "test-result.json").write_text(json.dumps(result) + "\n")
    validate_test_result(result)
    _write_task(directory, {"execution_id": "cleanup-fail", "status": "failed", "processes": [],
                            "owned_resources": [str(residue)]})
    monkeypatch.setattr(runtime.shutil, "rmtree", lambda path: (_ for _ in ()).throw(OSError("busy")))
    runtime._clean(_selected({}, execution_id="cleanup-fail", execution_dir=directory), execution, "cleanup-fail")
    task = json.loads((directory / "task.json").read_text())
    assert task["cleanup"]["status"] == "failed"
    assert (directory / "test-result.json").is_file()
    assert residue.is_dir()
