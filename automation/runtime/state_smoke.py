"""Opt-in native S3 smoke, run inside the image against a disposable bucket.

Requires IAAS_TEST_S3_ENDPOINT, IAAS_TEST_S3_BUCKET, IAAS_TEST_OUTPUT and caller
AWS credentials. This manages only terraform_data, never real infrastructure.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time

from iaas_automation.runtime_execution.execution import Execution, OperationFailed
from iaas_automation.runtime_execution.outputs import TaskOutputs
from iaas_automation.runtime_execution.state import S3Backend


def main() -> None:
    output = Path(os.environ["IAAS_TEST_OUTPUT"])
    outputs = TaskOutputs.create(output, Path("/opt/iaas"), [])
    root = outputs.path("work")
    (root / ".terraform.lock.hcl").write_text("")
    marker = root / "lock-held"
    (root / "main.tf.json").write_text(json.dumps({"resource": {"terraform_data": {"synthetic": {
        "input": "synthetic-private-state",
        "provisioner": [{"local-exec": {"command": f"touch {marker}; sleep 3"}}],
    }}}}))
    backend = S3Backend({
        "bucket": os.environ["IAAS_TEST_S3_BUCKET"], "key": "native-smoke/state",
        "region": "us-east-1", "use_lockfile": True,
        "endpoints": {"s3": os.environ["IAAS_TEST_S3_ENDPOINT"]},
        "use_path_style": True, "skip_credentials_validation": True,
        "skip_requesting_account_id": True, "skip_metadata_api_check": True,
    }, "default")
    execution = Execution(outputs, {**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"})
    execution.record("backend-init", backend.initialize(root, execution.environ, outputs.path("recovery")), root)
    execution.run("plan", ["tofu", "plan", "-out=plan.tfplan", "-input=false"], root)
    execution.run("stale-plan", ["tofu", "plan", "-out=stale.tfplan", "-input=false"], root)

    errors = []

    def apply() -> None:
        try:
            execution.run("apply", ["tofu", "apply", "-input=false", "plan.tfplan"], root)
        except Exception as exc:
            errors.append(type(exc).__name__)

    worker = threading.Thread(target=apply)
    worker.start()
    deadline = time.monotonic() + 20
    while not marker.exists() and worker.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert marker.exists(), "native apply did not enter the locked phase"
    # Use a separate result collector so concurrent phases do not overwrite a
    # shared task summary. The backend itself is deliberately the same.
    contention_outputs = TaskOutputs.create(output.parent / "contention", Path("/opt/iaas"), [])
    contention = Execution(contention_outputs, execution.environ)
    try:
        contention.run("lock-conflict", ["tofu", "plan", "-input=false", "-lock-timeout=1s"], root)
    except OperationFailed:
        assert "Error acquiring the state lock" in (contention_outputs.path("recovery") / "lock-conflict.raw").read_text()
    else:
        raise AssertionError("concurrent native state operation unexpectedly acquired the lock")
    worker.join(timeout=30)
    assert not worker.is_alive() and not errors, "native apply failed"
    execution.run("state-read", ["tofu", "state", "pull"], root)
    state = json.loads((outputs.path("recovery") / "state-read.raw").read_text())
    assert state["resources"][0]["type"] == "terraform_data"
    assert state["serial"] >= 1
    try:
        execution.run("stale-apply", ["tofu", "apply", "-input=false", "stale.tfplan"], root)
    except OperationFailed:
        assert "Saved plan is stale" in (outputs.path("recovery") / "stale-apply.raw").read_text()
    else:
        raise AssertionError("stale native plan was not rejected")
    print("native S3 smoke passed: state read/write, lock contention, stale saved-plan rejection; synthetic resource only")


if __name__ == "__main__":
    main()
