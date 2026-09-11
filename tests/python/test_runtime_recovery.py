import io
import json
import os
from pathlib import Path
import sys

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_execution.outputs import TaskOutputs
from iaas_automation.runtime_execution.process import _capture_output, run_protected
from iaas_automation.runtime_execution.state import S3Backend
from iaas_automation.runtime_execution.operations import credential_names, operation_for, process_environment
from iaas_automation.runtime_execution.execution import Execution, OperationFailed


def test_emergency_state_output_is_protected_even_without_recovery_file(tmp_path, capfd):
    # A real subprocess represents the tool's double-failure terminal fallback.
    capture = tmp_path / "recovery/emergency.raw"
    result = run_protected([sys.executable, "-c", "import sys; print('STATE-SECRET'); print('CREDENTIAL',file=sys.stderr); sys.exit(1)"],
                           cwd=tmp_path, environ={}, capture=capture)
    assert result.returncode == 1 and result.capture_complete and not result.successful
    assert capture.read_text().count("STATE-SECRET") == 1
    assert "CREDENTIAL" in capture.read_text()
    assert capture.stat().st_mode & 0o777 == 0o600
    assert capfd.readouterr() == ("", "")


def test_capture_cannot_be_prepared_prevents_spawn(tmp_path):
    capture = tmp_path / "occupied"
    capture.write_text("existing")
    marker = tmp_path / "started"
    with pytest.raises(ValidationError, match="not started"):
        run_protected([sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
                      cwd=tmp_path, environ={}, capture=capture)
    assert not marker.exists()


def test_mid_capture_failure_drains_without_public_fallback(capfd):
    class FullDisk(io.BytesIO):
        def write(self, value):
            raise OSError("disk full")
    source = io.BytesIO(b"private-state" * 10000)
    failures = []
    _capture_output(source, FullDisk(), failures)
    assert failures and source.closed
    assert capfd.readouterr() == ("", "")


def test_retain_recovery_state_and_failed_collection(tmp_path):
    outputs = TaskOutputs.create(tmp_path / "task", tmp_path / "implementation", [])
    root = outputs.path("work")
    state = root / "errored.tfstate"
    state.write_text("private-state")
    result = outputs.retain_state(root)
    assert result["recovery_complete"]
    assert Path(result["recovery_file"]).stat().st_mode & 0o777 == 0o600
    assert state.exists()
    failed = outputs.retain_state(root)  # refuses to overwrite the retained copy
    assert failed["retain_storage"] and not failed["recovery_complete"]
    assert state.read_text() == "private-state"


def test_backend_identity_and_native_lock_are_caller_owned(tmp_path):
    document = {"workspace": "review", "config": {"bucket": "synthetic", "key": "state",
                "region": "us-east-1", "workspace_key_prefix": "projects", "use_lockfile": True}}
    config = tmp_path / "s3.json"
    config.write_text(json.dumps(document))
    backend = S3Backend.load(config)
    assert backend.identity()["workspace_key_prefix"] == "projects"
    assert backend.identity()["workspace"] == "review"
    for change in [{"use_lockfile": False}, {"bucket": ""}, {"access_key": "secret"}]:
        config.write_text(json.dumps({**document, "config": {**document["config"], **change}}))
        with pytest.raises(ValidationError):
            S3Backend.load(config)


def test_backend_failure_preserves_exit_without_fallback(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    fake = tmp_path / "tofu"
    fake.write_text("#!/bin/sh\nexit 17\n")
    fake.chmod(0o700)
    backend = S3Backend({"bucket": "synthetic", "key": "state", "region": "us-east-1", "use_lockfile": True}, "default")
    result = backend.initialize(root, {}, tmp_path / "recovery", str(fake))
    assert result.returncode == 17 and not result.successful
    assert not (root / "terraform.tfstate").exists()
    assert json.loads((root / "zz_iaas_backend_override.tf.json").read_text())["terraform"]["backend"]["s3"]["use_lockfile"] is True


def test_credential_selection_and_operation_effects():
    supplied = {"AWS_SECRET_ACCESS_KEY": "s3", "OP_SERVICE_ACCOUNT_TOKEN": "never",
                "TF_VAR_pve_api_token_secret": "pve", "GUEST_PASSWORD": "guest",
                "TF_CLI_ARGS": "-lock=false", "PATH": "/usr/bin"}
    assert process_environment("pve", "check", supplied) == {"PATH": "/usr/bin"}
    assert "AWS_SECRET_ACCESS_KEY" not in process_environment("pve", "health", supplied)
    assert not credential_names("pve", "prepare-dependencies")
    plan = process_environment("pve", "plan", supplied, ("GUEST_PASSWORD",))
    assert set(plan) == {"PATH", "AWS_SECRET_ACCESS_KEY", "TF_VAR_pve_api_token_secret", "GUEST_PASSWORD"}
    assert "GUEST_PASSWORD" not in process_environment("pve", "apply-saved-plan", supplied)
    assert operation_for("k3s", "snapshot").infrastructure_write
    with pytest.raises(ValidationError):
        operation_for("switch", "apply")
    with pytest.raises(ValidationError):
        credential_names("pve", "plan", ("OP_SERVICE_ACCOUNT_TOKEN",))


def test_cancellation_propagates_and_captures_child_output(tmp_path):
    result = run_protected([sys.executable, "-c",
                           "import os, signal, time; time.sleep(.1); os.kill(os.getppid(), signal.SIGTERM); time.sleep(30)"],
                           cwd=tmp_path, environ={}, capture=tmp_path / "cancel.raw")
    assert result.interrupted and result.returncode != 0
    assert result.capture_complete


def test_failed_phase_stops_dependents_and_preserves_private_state(tmp_path, capfd):
    outputs = TaskOutputs.create(tmp_path / "task", tmp_path / "implementation", [])
    execution = Execution(outputs, {})
    with pytest.raises(OperationFailed):
        execution.run("apply", [sys.executable, "-c",
                               "open('errored.tfstate','w').write('secret-state'); print('secret-state'); raise SystemExit(3)"],
                      outputs.path("work"))
        pytest.fail("dependent phase must not execute")
    summary = json.loads((outputs.root / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert summary["phases"][0]["exit_code"] == 3
    assert "secret-state" not in json.dumps(summary)
    assert (outputs.path("recovery") / "errored.tfstate").read_text() == "secret-state"
    assert capfd.readouterr() == ("", "")
