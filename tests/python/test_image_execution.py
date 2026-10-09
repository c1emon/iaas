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
from typing import Any, Self

import pytest
from iaas.common.errors import ValidationError
from iaas.image import runtime
from iaas.image.contracts import (
    canonical_digest,
    validate_artifact,
    validate_build_request,
    validate_test_result,
)
from iaas.runtime_execution.execution import Execution, OperationFailed
from iaas.runtime_execution.outputs import TaskOutputs


def _request(*, firmware: str = "uefi", checks: dict | None = None) -> dict:
    return {
        "kind": "image-build-request", "schema_version": 2, "disk_size_gib": 8,
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
    assert {"build.seed.img", "build.key", "build.key.pub", "build.user-data", "build.meta-data"} <= set(recorded["owned_resources"])


def test_offline_cleanup_uses_supported_sysprep_and_clears_cloud_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    commands: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(runtime.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(runtime, "_run_tool",
                        lambda _execution, phase, command, _cwd: commands.append((phase, command)))

    runtime._offline_cleanup(execution, tmp_path / "disk.qcow2", tmp_path)

    sysprep = next(command for phase, command in commands if phase == "offline-sysprep")
    assert sysprep[-1] == ",".join(runtime.OFFLINE_SYSPREP_OPERATIONS)
    assert "cloud-init" not in sysprep[-1]
    cleanup = next(command for phase, command in commands if phase == "offline-builder-clean")
    cleanup_text = " ".join(cleanup)
    for path in ("/var/lib/cloud/instance", "/var/lib/cloud/instances", "/var/lib/cloud/sem",
                 "/var/lib/cloud/data", "/var/lib/cloud/seed", "/var/lib/cloud/handlers",
                 "/var/lib/cloud/scripts", "/var/log/cloud-init.log", "/var/log/cloud-init-output.log"):
        assert path in cleanup_text
    assert "/etc/sudoers.d/90-cloud-init-users" in cleanup_text
    assert "mkdir -p /var/lib/cloud" in cleanup_text
    assert runtime._has_packer_sudo_rule("# User rules for packer\npacker ALL=(ALL) NOPASSWD:ALL\n")
    assert not runtime._has_packer_sudo_rule("# User rules for packer\n")


def test_identity_cleanup_fails_closed_on_required_directory_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    disk = tmp_path / "disk.qcow2"
    monkeypatch.setattr(runtime.shutil, "which", lambda name: f"/usr/bin/{name}")

    def probe(fail_target: str | None = None, *, cloud_file: bool = False):
        def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            target = command[-1]
            if target == fail_target:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="read failed")
            if target == "/etc/sudoers.d":
                output = "90-cloud-init-users\n" if cloud_file else ""
                return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")
            if target == "/etc/sudoers.d/90-cloud-init-users" and not cloud_file:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="missing")
            output = "iaas-test\n" if target == "/home" else "syslog\n" if target == "/var/log" else ""
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")
        return run

    for required_directory in ("/home", "/etc/sudoers.d"):
        monkeypatch.setattr(runtime.subprocess, "run", probe(required_directory))
        assert runtime._identity_cleanup_status(disk) == "failed"

    monkeypatch.setattr(runtime.subprocess, "run", probe("/etc/sudoers.d/90-cloud-init-users", cloud_file=True))
    assert runtime._identity_cleanup_status(disk) == "failed"


@pytest.mark.skipif(sys.platform != "linux", reason="exact process-group cancellation qualifies the Linux image executor")
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


def test_process_group_permission_failure_retains_unknown_cleanup_gate(monkeypatch):
    class Process:
        pid = 123
        returncode = 0
        def wait(self, **kwargs):
            return 0
        def poll(self):
            return 0
    signals = []
    def signal_group(pid, sig):
        signals.append(sig)
        if sig == 0:
            raise PermissionError("group state inaccessible")
    monkeypatch.setattr(runtime.os, "killpg", signal_group)
    entry = {"pid": 123, "state": "running"}
    runtime._stop_process(Process(), entry)
    assert entry["state"] == "unknown"
    assert runtime._task_has_uncertain_process({"processes": [entry]})
    assert signals == [runtime.signal.SIGTERM, 0, runtime.signal.SIGKILL]


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
                                "owned_resources": ["owned"]})
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


def test_qemu_info_keeps_metadata_capture_outside_readonly_source_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = _execution(tmp_path)
    source_root = tmp_path / "readonly-input"
    source_root.mkdir()
    disk = source_root / "disk.qcow2"
    disk.write_bytes(b"image")
    capture_parents: list[Path] = []
    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/usr/bin/qemu-img")

    def inspect(command: list[str], *, stdout: Any, **_: object) -> subprocess.CompletedProcess[str]:
        capture_parents.append(Path(str(stdout.name)).parent)
        stdout.write(b'{"format":"qcow2","virtual-size":4096}')
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", inspect)
    assert runtime._qemu_info(disk, execution) == {"format": "qcow2", "virtual-size": 4096}
    assert capture_parents == [execution.outputs.path("work")]


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
    capture = Path(execution.phases[-1]['capture'])
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
            key = Path(command[-1])
            key.write_text("private\n")
            Path(str(key) + ".pub").write_text("public\n")
        elif command[0] == "cloud-localds":
            Path(command[1]).write_bytes(b"seed")
    monkeypatch.setattr(runtime, "_run_tool", fake_tool)
    monkeypatch.setattr(runtime, "_wait_port", lambda process, port, timeout, **kwargs: None)
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
                            "owned_resources": ["owned"]})
    monkeypatch.setattr(runtime.shutil, "rmtree", lambda path: (_ for _ in ()).throw(OSError("busy")))
    runtime._clean(_selected({}, execution_id="cleanup-fail", execution_dir=directory), execution, "cleanup-fail")
    task = json.loads((directory / "task.json").read_text())
    assert task["cleanup"]["status"] == "failed"
    assert (directory / "test-result.json").is_file()
    assert residue.is_dir()


def test_automatic_cleanup_retains_unknown_owned_resources(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "automatic-unknown")
    owned = directory / "owned"
    owned.write_text("retain")
    task = {"execution_id": "automatic-unknown", "status": "failed",
            "processes": [{"pid": 999999, "start_ticks": None, "state": "unknown"}],
            "owned_resources": ["owned"]}

    removed, failures = runtime._remove_owned(directory, task, preserve={directory / "task.json"})

    assert removed == []
    assert failures == [str(owned.resolve())]
    assert owned.exists()
    assert task["cleanup_errors"]


def test_clean_resolves_relative_owned_resources_after_task_directory_move(tmp_path: Path) -> None:
    execution = _execution(tmp_path)
    original = runtime._task_dir(execution, "moved")
    owned = original / "owned"
    owned.write_text("remove")
    _write_task(original, {"execution_id": "moved", "status": "failed", "processes": [],
                           "owned_resources": ["owned"]})

    moved = tmp_path / "relocated-task"
    shutil.move(str(original), str(moved))
    runtime._clean(_selected({}, execution_id="moved", execution_dir=moved), execution, "moved")

    assert not (moved / "owned").exists()
    record = json.loads((moved / "task.json").read_text(encoding="utf-8"))
    assert record["cleanup"]["status"] == "succeeded"


def test_owned_resources_reject_absolute_and_escaping_paths(tmp_path: Path) -> None:
    directory = tmp_path / "task"
    directory.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("retain")

    with pytest.raises(ValidationError, match="relative"):
        runtime._owned_path(directory, outside)
    with pytest.raises(ValidationError, match="outside"):
        runtime._owned_path(directory, "../outside")

    task = {"processes": [], "owned_resources": [str(outside)]}
    removed, failures = runtime._remove_owned(directory, task, preserve=set())
    assert removed == []
    assert failures == [str(outside)]
    assert outside.exists()


def test_owned_symlink_cleanup_removes_link_but_keeps_target(tmp_path: Path) -> None:
    directory = tmp_path / "task"
    directory.mkdir()
    target = directory / "target"
    link = directory / "link"
    target.write_text("keep")
    link.symlink_to(target.name)
    assert runtime._relative_resource(directory, link) == "link"
    task = {"processes": [], "owned_resources": ["link"]}

    removed, failures = runtime._remove_owned(directory, task, preserve=set())

    assert failures == []
    assert removed == [str(link)]
    assert not link.exists() and not link.is_symlink()
    assert target.read_text() == "keep"

    outside = tmp_path / "outside"
    outside.write_text("retain")
    link.symlink_to(outside)
    task["owned_resources"] = ["link"]
    removed, failures = runtime._remove_owned(directory, task, preserve=set())
    assert removed == []
    assert failures == ["link"]
    assert link.is_symlink()
    assert outside.read_text() == "retain"


@pytest.mark.parametrize("host,limit,usage,status", [
    (256, "max", 0, "insufficient"),
    (1024, "700", 300, "insufficient"),
    (1024, "max", 0, "unknown"),
    (None, "1024", 100, "unknown"),
    (None, "300", 0, "insufficient"),
    (1024, "1024", 100, "sufficient"),
])
def test_runtime_memory_observation_scopes(tmp_path, host, limit, usage, status):
    proc, cgroup = tmp_path / "proc", tmp_path / "cgroup"
    (proc / "self").mkdir(parents=True)
    cgroup.mkdir()
    if host is not None:
        (proc / "meminfo").write_text(f"MemAvailable: {host * 1024} kB\n")
    (proc / "self/cgroup").write_text("0::/\n")
    (cgroup / "memory.max").write_text("max" if limit == "max" else str(int(limit) * 1024 ** 2))
    (cgroup / "memory.current").write_text(str(usage * 1024 ** 2))
    facts = runtime._memory_observation(_request()["resources"], proc=proc, cgroup=cgroup)
    assert facts["status"] == status
    assert facts["requested_memory_mib"] == 512
    assert {row["scope"] for row in facts["observations"]} == {"host", "current_container"}
    assert facts["sampled_at"] > 0


@pytest.mark.parametrize("status,blocked", [("insufficient", True), ("unknown", False)])
def test_build_memory_refusal_persists_before_dispatch(tmp_path, monkeypatch, status, blocked):
    execution = _execution(tmp_path)
    monkeypatch.setattr(runtime, "_executor_check", lambda _: {"supported_platform": True, "supported_kvm": True, "enough_disk": True})
    memory = {"status": status, "requested_memory_mib": 512, "sampled_at": 123, "observations": []}
    monkeypatch.setattr(runtime, "_memory_observation", lambda _: memory)
    downloads = []
    def stop(*args, **kwargs):
        downloads.append(True)
        raise OperationFailed("download stop")
    monkeypatch.setattr(runtime, "_download_base", stop)
    with pytest.raises((OperationFailed, ValidationError)):
        runtime._build(_selected(_request(), execution_id="memory"), execution, "memory")
    task = json.loads((runtime._task_dir(execution, "memory") / "task.json").read_text())
    assert task["resources"]["memory_observation"] == memory
    assert task["status"] == "failed"
    assert bool(downloads) != blocked
    assert task["processes"] == []


def test_fixed_base_transfer_retries_only_partial_get(tmp_path, monkeypatch):
    import hashlib
    request = _request()
    request["base"]["checksum"]["value"] = hashlib.sha256(b"verified").hexdigest()
    request["resources"]["timeout_seconds"] = 3
    calls = []
    class Response(io.BytesIO):
        headers = {}
        def read(self, size=-1):
            if len(calls) == 1:
                super().read(2)
                raise ConnectionResetError("private URL must not escape")
            return super().read(size)
    def open_url(*args, **kwargs):
        calls.append(kwargs["timeout"])
        return Response(b"verified")
    monkeypatch.setattr(runtime, "urlopen", open_url)
    destination = tmp_path / "base.img"
    runtime._download_base(request, destination, request["resources"])
    assert len(calls) == 2
    assert destination.read_bytes() == b"verified"
    assert not (tmp_path / "base.img.part").exists()


@pytest.mark.parametrize("failure", ["checksum", "permission", "tls"])
def test_fixed_base_transfer_does_not_retry_rejected_reads(tmp_path, monkeypatch, failure):
    import ssl
    from urllib.error import HTTPError, URLError
    calls = []
    class Response(io.BytesIO):
        headers = {}
    def open_url(*args, **kwargs):
        calls.append(True)
        if failure == "permission":
            raise HTTPError("https://private.invalid", 403, "secret", {}, None)
        if failure == "tls":
            raise URLError(ssl.SSLCertVerificationError("secret"))
        return Response(b"incorrect")
    monkeypatch.setattr(runtime, "urlopen", open_url)
    with pytest.raises(OperationFailed) as error:
        runtime._download_base(_request(), tmp_path / "base.img", _request()["resources"])
    assert len(calls) == 1
    assert "secret" not in str(error.value)
    assert not (tmp_path / "base.img.part").exists()


def test_image_task_timeout_is_not_renewed_by_substage(tmp_path):
    from iaas.observation import ObservationBudget
    now = [100.0]
    execution = _execution(tmp_path)
    execution.image_timeout_seconds = 20
    execution.image_observation_budget = ObservationBudget(20, utc=lambda: now[0], monotonic=lambda: now[0])
    assert runtime._current_timeout(execution) == 20
    now[0] += 15
    assert runtime._current_timeout(execution) == 5
    now[0] += 5
    with pytest.raises(OperationFailed, match="timeout expired"):
        runtime._current_timeout(execution)


@pytest.mark.parametrize("status", ["insufficient", "unknown"])
def test_qemu_memory_observation_controls_dispatch(tmp_path, monkeypatch, status):
    execution = _execution(tmp_path)
    directory = runtime._task_dir(execution, "memory-qemu")
    disk = directory / "disk.qcow2"
    disk.write_bytes(b"disk")
    key = directory / "key"
    key.write_text("unused fixture")
    monkeypatch.setattr(runtime.shutil, "which", lambda _: "/usr/bin/tool")
    monkeypatch.setattr(runtime, "_run_tool", lambda *args: None)
    monkeypatch.setattr(runtime, "_make_seed", lambda *args, **kwargs: (directory / "seed", key))
    monkeypatch.setattr(runtime, "_memory_observation", lambda _: {"status": status, "requested_memory_mib": 512})
    calls = []
    def dispatch(*args, **kwargs):
        calls.append(True)
        raise OperationFailed("dispatch fixture stop")
    monkeypatch.setattr(runtime, "_start_qemu", dispatch)
    task = {"processes": [], "owned_resources": []}
    with pytest.raises((OperationFailed, ValidationError)):
        runtime._boot_guest(execution, directory, task, disk, "bios", _request()["resources"], username="test", phase="memory-test")
    assert bool(calls) == (status == "unknown")
    if status == "insufficient":
        assert task["processes"] == []
    assert json.loads((directory / "task.json").read_text())["resources"]["memory_observation"]["status"] == status
