import json
import os
from pathlib import Path
import shutil
import sys

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_config import load_environment
from iaas_automation.runtime_config.compile import compile_documents
from iaas_automation.runtime_execution.execution import Execution, OperationFailed
from iaas_automation.runtime_execution.outputs import TaskOutputs
from iaas_automation.runtime_execution.plans import admit_plan, apply_saved_plan, prepare_plan, target_selection
from iaas_automation.runtime_execution.state import S3Backend


REPO = Path(__file__).resolve().parents[2]
IMAGE = "example/iaas@sha256:" + "a" * 64


@pytest.fixture
def setup_plan(tmp_path):
    (tmp_path / "main.tf").write_text('terraform {}\n')
    (tmp_path / "lock.hcl").write_text("")
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({"schema_version": 1, "environment": "lab", "components": {"pve": {
        "inputs": {"cluster": str(REPO / "tests/fixtures/runtime/pve-cluster.yml"),
                   "vms": str(REPO / "tests/fixtures/runtime/vms.yml")},
        "files": {"main": "main.tf", "lock": "lock.hcl"},
        "options": {"root": {"id": "complete-root", "directory": ".", "files": {"main.tf": "main", ".terraform.lock.hcl": "lock"}},
                    "pve": {"storage_id": "synthetic-snippets", "ssh_host": "synthetic.invalid", "ssh_user": "pve-ops"}},
    }}}))
    selected = load_environment(entry, "pve")
    generated = json.loads(compile_documents(selected)["pve.tfvars.json"])
    cloud_init = generated["cluster"]["automation"]["cloud_init"]
    role = cloud_init["snippet_storage_role"]
    selected.options["pve"]["storage_id"] = generated["cluster"]["storage_roles"][role]["datastore"]
    env = {"PATH": f"{tmp_path}:{os.environ['PATH']}", "PYTHONPATH": str(REPO / "automation/src")}
    for user in cloud_init["users"]:
        env[user["password_env"]] = "synthetic-password"
        env[user["public_key_env"]] = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGsynthetic runtime-test"
    tofu = tmp_path / "tofu"
    tofu.write_text(f"#!{sys.executable}\n" + """import os,sys
from pathlib import Path
if sys.argv[1] == 'plan':
    path = next(arg[5:] for arg in sys.argv if arg.startswith('-out='))
    Path(path).write_text(os.environ.get('PLAN_LABEL','plan-A'))
elif sys.argv[1] == 'show':
    print('sensitive review')
elif sys.argv[1] == 'apply':
    assert not any(arg.startswith('-var-file') for arg in sys.argv)
    raise SystemExit(int(os.environ.get('APPLY_EXIT','0')))
""")
    tofu.chmod(0o700)
    ssh = tmp_path / "ssh"
    ssh.write_text(f"#!{sys.executable}\nimport os,sys\nraise SystemExit(int(os.environ.get('SSH_EXIT','0')))\n")
    ssh.chmod(0o700)
    backend = S3Backend({"bucket": "synthetic", "key": "lab", "region": "us-east-1", "use_lockfile": True}, "default")

    def execution(name, **changes):
        outputs = TaskOutputs.create(tmp_path / name, REPO, list(selected.reader.sources))
        return Execution(outputs, {**env, **changes})

    return selected, backend, str(tofu), execution


def test_prepare_and_apply_from_another_directory(setup_plan, tmp_path):
    selected, backend, tofu, execution = setup_plan
    prepare = execution("prepare")
    plan = prepare_plan(selected, prepare, backend, "complete-root", IMAGE, tofu)
    metadata = json.loads((plan.parent / "summary.json").read_text())
    wrong_platform = "linux/arm64" if metadata["runtime_platform"] == "linux/amd64" else "linux/amd64"
    with pytest.raises(ValidationError, match="runtime mismatch"):
        admit_plan(plan, plan.parent,
                   {**target_selection(selected, "complete-root", IMAGE), "runtime_platform": wrong_platform}, backend)
    assert [phase["phase"] for phase in prepare.phases] == ["render-snippets", "backend-init", "plan", "review"]
    moved = tmp_path / "moved-companions"
    shutil.copytree(plan.parent, moved)
    saved_bytes = (moved / "snippets/manifest.json").read_bytes()
    apply = execution("apply")
    # Applying the saved bundle must not compile changed current inputs.
    selected.documents = {"cluster": {"invalid": True}}
    apply_saved_plan(moved / "plan.tfplan", moved, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert [phase["phase"] for phase in apply.phases] == ["backend-init", "upload-snippets", "verify-snippets", "apply"]
    assert (moved / "snippets/manifest.json").read_bytes() == saved_bytes


def test_mixed_native_plan_and_companions_fail_before_ssh(setup_plan):
    selected, backend, tofu, execution = setup_plan
    plan_a = prepare_plan(selected, execution("plan-a"), backend, "complete-root", IMAGE, tofu)
    plan_b = prepare_plan(selected, execution("plan-b", PLAN_LABEL="plan-B"), backend, "complete-root", IMAGE, tofu)
    apply = execution("apply")
    with pytest.raises(ValidationError, match="does not match"):
        apply_saved_plan(plan_a, plan_b.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert apply.phases == []


@pytest.mark.parametrize("failure,phase", [({"SSH_EXIT": "9"}, "upload-snippets"), ({"APPLY_EXIT": "17"}, "apply")])
def test_failure_stops_without_replanning(setup_plan, failure, phase):
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    apply = execution("apply", **failure)
    with pytest.raises(OperationFailed):
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert apply.phases[-1]["phase"] == phase
    assert not any(item["phase"] in {"plan", "render-snippets"} for item in apply.phases)
    assert json.loads((apply.outputs.root / "summary.json").read_text())["status"] == "failed"


def test_missing_binding_and_partial_scope_are_rejected(setup_plan):
    selected, backend, tofu, execution = setup_plan
    with pytest.raises(ValidationError, match="complete"):
        target_selection(selected, "one-vm", IMAGE)
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    manifest = plan.parent / "snippets/manifest.json"
    content = json.loads(manifest.read_text())
    del content["plan_sha256"]
    manifest.write_text(json.dumps(content))
    with pytest.raises(ValidationError, match="does not match"):
        admit_plan(plan, plan.parent, target_selection(selected, "complete-root", IMAGE), backend)


def test_empty_vm_plan_skips_ssh_and_preserves_root_executable(setup_plan, tmp_path):
    selected, backend, tofu, execution = setup_plan
    selected.documents["vms"]["vms"] = []
    helper = tmp_path / "helper.sh"
    helper.write_text("#!/bin/sh\nexit 0\n")
    helper.chmod(0o700)
    selected.files["helper"] = helper
    selected.options["root"]["files"]["helper.sh"] = "helper"
    plan = prepare_plan(selected, execution("empty-plan"), backend, "complete-root", IMAGE, tofu)
    apply = execution("empty-apply", SSH_EXIT="9")
    apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert [item["phase"] for item in apply.phases] == ["backend-init", "apply"]
    assert (apply.outputs.path("plan") / "selected/workspace/helper.sh").stat().st_mode & 0o100
