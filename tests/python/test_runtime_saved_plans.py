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
from iaas_automation.runtime_execution.process import run_protected
from iaas_automation.runtime_execution.state import S3Backend


REPO = Path(__file__).resolve().parents[2]
IMAGE = "example/iaas@sha256:" + "a" * 64


@pytest.fixture
def setup_plan(tmp_path, monkeypatch):
    from iaas_automation.runtime_execution import pve_provider, pve_state, plans
    from iaas_automation.runtime_execution.pve_state import StateObservation
    monkeypatch.setattr(pve_provider, "validate_root", lambda *a: {}, raising=False)
    monkeypatch.setattr(pve_provider, "prepare_provider_environment", lambda *a: None, raising=False)
    monkeypatch.setattr(pve_provider, "validate_plan_provider", lambda *a: None, raising=False)
    monkeypatch.setattr(pve_provider, "verify_ssh_trust", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(pve_provider, "verify_helper_trust", lambda *a: None)
    from types import SimpleNamespace
    monkeypatch.setattr(plans, "api_client", lambda *a: SimpleNamespace(
        cluster_vm_resources=lambda: [], effective_permissions=lambda path: {path: {"VM.Audit": 1}}))
    monkeypatch.setattr(pve_state, "observe_state", lambda backend, env: StateObservation(
        "present", backend.config["bucket"], backend.state_key(), backend.workspace, None,
        lineage="synthetic-lineage", serial=1, empty=True,
        raw={"version": 4, "lineage": "synthetic-lineage", "serial": 1, "resources": []}), raising=False)
    (tmp_path / "main.tf").write_text('terraform {}\n')
    (tmp_path / "lock.hcl").write_text("")
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({"schema_version": 1, "environment": "lab", "components": {"pve": {
        "inputs": {"cluster": str(REPO / "tests/fixtures/runtime/pve-cluster.yml"),
                   "vms": str(REPO / "tests/fixtures/runtime/vms.yml")},
        "files": {"main": "main.tf", "lock": "lock.hcl"},
        "options": {"root": {"id": "complete-root", "directory": ".", "files": {"main.tf": "main", ".terraform.lock.hcl": "lock"}},
                    "pve": {"storage_id": "synthetic-snippets", "ssh_host": "synthetic.invalid", "ssh_user": "pve-ops",
                            "api_endpoint": "https://synthetic.invalid:8006", "insecure": False}},
    }}}))
    selected = load_environment(entry, "pve")
    generated = json.loads(compile_documents(selected)["pve.tfvars.json"])
    cloud_init = generated["cluster"]["automation"]["cloud_init"]
    role = cloud_init["snippet_storage_role"]
    selected.options["pve"]["storage_id"] = generated["cluster"]["storage_roles"][role]["datastore"]
    env = {"PATH": f"{tmp_path}:{os.environ['PATH']}", "PYTHONPATH": str(REPO / "automation/src"), "HOME": str(tmp_path)}
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
    print('{}' if '-json' in sys.argv else 'sensitive review')
elif sys.argv[1] == 'apply':
    assert not any(arg.startswith('-var-file') for arg in sys.argv)
    if os.environ.get('STATE_WRITE_FAIL'):
        Path('errored.tfstate').write_text('private recovery state')
    raise SystemExit(int(os.environ.get('APPLY_EXIT','0')))
""")
    tofu.chmod(0o700)
    ssh = tmp_path / "ssh"
    ssh.write_text(f"#!{sys.executable}\nimport os,sys\nraise SystemExit(int(os.environ.get('SSH_EXIT','0')))\n")
    ssh.chmod(0o700)
    backend = S3Backend({"bucket": "synthetic", "key": "lab", "region": "us-east-1", "use_lockfile": True}, "default")
    state_admission = tmp_path / "state-admission.json"
    state_admission.write_text(json.dumps({"schema_version": 1, "root_id": "complete-root", "mode": "existing",
                                         "lineage": "synthetic-lineage", "workspace": "default", "backend": backend.identity()}))
    state_admission.chmod(0o600)
    selected.files["state_admission"] = state_admission

    def execution(name, **changes):
        outputs = TaskOutputs.create(tmp_path / name, REPO, list(selected.reader.sources))
        return Execution(outputs, {**env, **changes})

    original_apply = plans.apply_saved_plan

    def admitted_apply(plan, bundle, selected, execution, backend, scope, image, tofu="tofu"):
        admission_path = tmp_path / "admission.json"
        admission_path.write_text(json.dumps({"schema_version": 1, "execution_id": "synthetic-execution",
            "plan_digest": plans.sha256(plan), "target": selected.options["pve"], "approved": True,
            "consumption": {"reserved": True, "reservation_id": "reservation"}, "pending": {"record_id": "pending"},
            "serialization": {"held": True, "context_id": "lock"}}))
        admission_path.chmod(0o600)
        selected.files["execution_admission"] = admission_path
        return original_apply(plan, bundle, selected, execution, backend, scope, image, tofu, execution_id="synthetic-execution")

    monkeypatch.setattr(sys.modules[__name__], "apply_saved_plan", admitted_apply)

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
    assert [phase["phase"] for phase in prepare.phases] == ["render-snippets", "backend-init", "plan", "review", "review-json"]
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
    result = json.loads((apply.outputs.root / "pve-result.json").read_text())
    assert result["phase"] == "failed"
    assert result["effects"]["facility"] == "unknown"
    assert result["native_execution"]["status"] == ("not_attempted" if phase == "upload-snippets" else "failed")


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
    result = json.loads((apply.outputs.root / "pve-result.json").read_text())
    assert result["verification"]["scope"] == "empty"
    assert result["native_execution"]["status"] == "success"
    assert result["state_persistence"]["status"] == "passed"


def test_collection_failure_preserves_native_success(setup_plan, monkeypatch):
    from iaas_automation.runtime_execution import pve_state
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    observe = pve_state.observe_state
    calls = []

    def fail_collection(*args):
        calls.append(1)
        result = observe(*args)
        if len(calls) == 3:
            from dataclasses import replace
            return replace(result, status="error", raw=None, reason="access_denied")
        return result

    monkeypatch.setattr(pve_state, "observe_state", fail_collection)
    apply = execution("apply")
    with pytest.raises(ValidationError):
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    result = json.loads((apply.outputs.root / "pve-result.json").read_text())
    assert result["native_execution"]["status"] == "success"
    assert result["state_persistence"]["status"] == "passed"
    assert result["collection"]["status"] == "unknown"
    assert (apply.outputs.path("recovery") / "apply.raw").exists()


def test_independent_verify_keeps_original_and_never_initializes(setup_plan, monkeypatch):
    from iaas_automation.runtime_execution.plans import verify_pve
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    apply = execution("apply")
    apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    original = apply.outputs.root / "pve-result.json"
    selected.files["execution_result"] = original
    original_bytes = original.read_bytes()
    monkeypatch.setattr(S3Backend, "initialize", lambda *a, **k: pytest.fail("verify cannot initialize state"))
    verify_pve(plan, plan.parent, selected, execution("verify"), "complete-root", IMAGE)
    assert original.read_bytes() == original_bytes
    selected.options["verification_requirements"] = {"requirements": [{"category": "configuration", "scope": "empty",
                                                                       "required": True, "responsibility": "iaas"}]}
    with pytest.raises(ValidationError, match="verification"):
        verify_pve(plan, plan.parent, selected, execution("downgrade"), "complete-root", IMAGE)


def test_required_external_acceptance_remains_incomplete(setup_plan):
    selected, backend, tofu, execution = setup_plan
    selected.options["verification_requirements"] = {"requirements": [
        {"category": "configuration", "scope": "changed_objects", "required": True, "responsibility": "iaas"},
        {"category": "guest", "scope": "changed_objects", "required": True, "responsibility": "caller"}]}
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    apply = execution("apply")
    apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    result = json.loads((apply.outputs.root / "pve-result.json").read_text())
    assert result["phase"] == "succeeded"
    assert result["caller_acceptance"] == "incomplete"
    assert result["guest"]["status"] == "not_attempted"


def test_recovery_read_preserves_original_and_rejects_cross_root(setup_plan, monkeypatch):
    from iaas_automation.runtime_execution.plans import read_pve
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    apply = execution("apply")
    apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    original = apply.outputs.root / "pve-result.json"
    selected.files["execution_result"] = original
    before = original.read_bytes()
    monkeypatch.setattr(S3Backend, "initialize", lambda *a, **k: pytest.fail("read cannot initialize"))
    read = execution("read")
    read_pve(selected, read, backend, "complete-root", IMAGE)
    assert original.read_bytes() == before and not read.phases
    report = json.loads((read.outputs.path("diagnostics") / "observation.json").read_text())
    assert report["historical_success"] == "unknown"
    selected.options["root"]["id"] = "other-root"
    with pytest.raises(ValidationError, match="association"):
        read_pve(selected, execution("wrong-root"), backend, "other-root", IMAGE)


def test_state_transition_only_admits_matching_initialization():
    from iaas_automation.runtime_execution.plans import _state_transition
    absent = {"status": "absent"}
    present = {"status": "present", "lineage": "original", "empty": True}
    _state_transition(absent, present, allow_initialization=True)
    _state_transition(present, present)
    for prior, current, initialize in [(present, absent, False),
                                       (present, {**present, "lineage": "other"}, False),
                                       (absent, present, False),
                                       (absent, {**present, "empty": False}, True)]:
        with pytest.raises(ValidationError):
            _state_transition(prior, current, allow_initialization=initialize)


def test_native_state_write_failure_keeps_emergency_state(setup_plan):
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    apply = execution("apply", STATE_WRITE_FAIL="1", APPLY_EXIT="1")
    with pytest.raises(OperationFailed):
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    result = json.loads((apply.outputs.root / "pve-result.json").read_text())
    assert result["state_persistence"]["status"] == "failed"
    assert result["collection"]["status"] == "not_attempted"
    assert (apply.outputs.path("recovery") / "errored.tfstate").read_text() == "private recovery state"
    assert (apply.outputs.path("plan") / "selected/workspace/errored.tfstate").exists()


def test_missing_saved_helper_fails_before_any_execution(setup_plan, tmp_path):
    selected, backend, tofu, execution = setup_plan
    helper = tmp_path / "helper.sh"
    helper.write_text("#!/bin/sh\nexit 0\n")
    selected.files["helper"] = helper
    selected.options["root"]["files"]["scripts/helper.sh"] = "helper"
    plan = prepare_plan(selected, execution("prepare-helper"), backend, "complete-root", IMAGE, tofu)
    (plan.parent / "workspace/scripts/helper.sh").unlink()
    # Admission must use the saved declaration, not today's options.
    selected.options["root"]["files"].pop("scripts/helper.sh")
    apply = execution("apply-helper")
    with pytest.raises(ValidationError, match="companion file"):
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert apply.phases == []


def test_old_plan_without_file_inventory_requires_replanning(setup_plan):
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution("prepare"), backend, "complete-root", IMAGE, tofu)
    summary = plan.parent / "summary.json"
    metadata = json.loads(summary.read_text())
    assert set(metadata.pop("companion_files")) == {"workspace/main.tf", "workspace/.terraform.lock.hcl"}
    summary.write_text(json.dumps(metadata))
    apply = execution("apply")
    with pytest.raises(ValidationError, match="prepare the plan again"):
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert apply.phases == []


@pytest.mark.skipif(shutil.which("tofu") is None, reason="native OpenTofu is not installed")
def test_native_plan_missing_helper_is_rejected_before_resource_creation(setup_plan, tmp_path, monkeypatch):
    selected, backend, _, execution = setup_plan
    tofu = shutil.which("tofu")
    helper = tmp_path / "helper.sh"
    helper.write_text("#!/bin/sh\nexit 0\n")
    selected.files["helper"] = helper
    selected.options["root"]["files"]["helper.sh"] = "helper"
    selected.files["main"].write_text('terraform {}\n')

    def initialize_local(self, root, environ, recovery, executable, **kwargs):
        # This test substitutes only S3 with an isolated local backend. The
        # native built-in resource needs no downloads or facility credentials.
        (root / "zz_iaas_backend_override.tf.json").write_text('{}')
        return run_protected([executable, "init", "-backend=false", "-input=false"], cwd=root,
                             environ=environ, capture=recovery / "backend-init.raw")

    monkeypatch.setattr(S3Backend, "initialize", initialize_local)
    plan = prepare_plan(selected, execution("native-plan"), backend, "complete-root", IMAGE, tofu)
    assert plan.is_file()
    (plan.parent / "workspace/helper.sh").unlink()
    apply = execution("native-apply")
    with pytest.raises(ValidationError, match="companion file"):
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert apply.phases == []
    assert not list(tmp_path.rglob("terraform.tfstate"))
