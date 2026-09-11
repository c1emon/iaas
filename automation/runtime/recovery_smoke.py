"""Opt-in S3 outage test using only a disposable terraform_data resource.

After work/ready appears, the authorized test coordinator makes the test S3
endpoint unavailable and creates work/continue. No real provider is involved.
"""

import json
import os
from pathlib import Path

from iaas_automation.runtime_execution.execution import Execution, OperationFailed
from iaas_automation.runtime_execution.outputs import TaskOutputs
from iaas_automation.runtime_execution.state import S3Backend


def main() -> None:
    output = Path(os.environ["IAAS_TEST_OUTPUT"])
    outputs = TaskOutputs.create(output, Path("/opt/iaas"), [])
    root = outputs.path("work")
    (root / ".terraform.lock.hcl").write_text("")
    (root / "main.tf.json").write_text(json.dumps({"resource": {"terraform_data": {"synthetic": {
        "input": "synthetic-private-recovery",
        "provisioner": [{"local-exec": {"command": "touch ready; for i in $(seq 1 120); do test ! -f continue || exit 0; sleep 1; done; exit 1"}}],
    }}}}))
    backend = S3Backend({
        "bucket": os.environ["IAAS_TEST_S3_BUCKET"], "key": "recovery-smoke/state",
        "region": "us-east-1", "use_lockfile": True,
        "endpoints": {"s3": os.environ["IAAS_TEST_S3_ENDPOINT"]},
        "use_path_style": True, "skip_credentials_validation": True,
        "skip_requesting_account_id": True, "skip_metadata_api_check": True,
    }, "default")
    execution = Execution(outputs, {**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"})
    execution.record("backend-init", backend.initialize(root, execution.environ, outputs.path("recovery")), root)
    execution.run("plan", ["tofu", "plan", "-input=false", "-out=plan.tfplan"], root)
    try:
        execution.run("apply", ["tofu", "apply", "-input=false", "plan.tfplan"], root)
    except OperationFailed:
        recovered = outputs.path("recovery") / "errored.tfstate"
        state = json.loads(recovered.read_text())
        assert state["resources"][0]["type"] == "terraform_data"
        assert recovered.stat().st_mode & 0o077 == 0
        assert (root / "errored.tfstate").is_file()
        print("native S3 outage smoke passed: failed state write retained private recovery state; no retry or state push")
    else:
        raise AssertionError("test endpoint remained available or state write unexpectedly succeeded")


if __name__ == "__main__":
    main()
