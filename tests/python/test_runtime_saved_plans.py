import json
import os
from pathlib import Path
import shutil
import ssl
import sys

import pytest
import yaml

from iaas.common.errors import ValidationError
from iaas.runtime_config import load_environment
from iaas.runtime_config.compile import compile_documents
from iaas.runtime_execution.execution import Execution, OperationFailed
from iaas.runtime_execution.outputs import TaskOutputs
from iaas.runtime_execution.plans import admit_plan, apply_saved_plan, prepare_plan, target_selection
from iaas.runtime_execution.process import run_protected
from iaas.runtime_execution.state import S3Backend


REPO = Path(__file__).resolve().parents[2]
IMAGE = "example/iaas@sha256:" + "a" * 64


@pytest.fixture
def api_ca(tmp_path):
    # Artifact tests only need loadable public trust; handshake tests use a local CA.
    certificate = ssl.create_default_context().get_ca_certs(binary_form=True)[0]
    path = tmp_path / "caller-ca.pem"
    path.write_text(ssl.DER_cert_to_PEM_cert(certificate))
    path.chmod(0o644)
    return path


@pytest.fixture
def setup_plan(tmp_path, monkeypatch):
    from iaas.runtime_execution import pve_provider, pve_state, plans
    from iaas.runtime_execution.pve_state import StateObservation
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
        "options": {"cluster_scope": "synthetic-cluster", "root": {"id": "complete-root", "directory": ".", "files": {"main.tf": "main", ".terraform.lock.hcl": "lock"}},
                    "pve": {"storage_id": "synthetic-snippets", "ssh_host": "synthetic.invalid", "ssh_user": "pve-ops",
                            "api_endpoint": "https://synthetic.invalid:8006", "insecure": False}},
    }}}))
    selected = load_environment(entry, "pve")
    generated = json.loads(compile_documents(selected)["pve.tfvars.json"])
    cloud_init = generated["cluster"]["automation"]["cloud_init"]
    role = cloud_init["snippet_storage_role"]
    selected.options["pve"]["storage_id"] = generated["cluster"]["storage_roles"][role]["datastore"]
    env = {"PATH": f"{tmp_path}:{os.environ['PATH']}", "PYTHONPATH": str(REPO / "src"), "HOME": str(tmp_path)}
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
    print(os.environ.get('NATIVE_PLAN_JSON', '{}') if '-json' in sys.argv else 'sensitive review')
elif sys.argv[1] == 'apply':
    assert not any(arg.startswith('-var-file') for arg in sys.argv)
    if os.environ.get('STATE_WRITE_FAIL'):
        Path('errored.tfstate').write_text('private recovery state')
    raise SystemExit(int(os.environ.get('APPLY_EXIT','0')))
""")
    tofu.chmod(0o700)
    ssh = tmp_path / "ssh"
    ssh.write_text(f"#!{sys.executable}\nimport os,sys,json\nif '--observe' in sys.argv[-1]: print(json.dumps({{'schema_version':1, 'status':'ready', 'reason_code':'digest_confirmed'}}))\nraise SystemExit(int(os.environ.get('SSH_EXIT','0')))\n")
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
            "serialization": {"held": True, "context_id": "lock"},
            "vmid_reservation": {"cluster_scope": "synthetic-cluster",
                "vmids": json.loads((bundle / "summary.json").read_text())["vm_policy"]["vmids"],
                "reservation_id": "reservation", "context_id": "lock"}}))
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
    # Saved inputs remain the apply materials; current placement policy is
    # checked against them without rendering new snippets.
    apply_saved_plan(moved / "plan.tfplan", moved, selected, apply, backend, "complete-root", IMAGE, tofu)
    assert [phase["phase"] for phase in apply.phases] == ["backend-init", "upload-snippets", "verify-snippets", "apply"]
    assert (moved / "snippets/manifest.json").read_bytes() == saved_bytes


@pytest.mark.parametrize('fault,reason', [('missing', 'saved review material missing'),
                                       ('invalid', 'saved review material invalid'),
                                       ('policy', 'saved review policy conflict')])
def test_review_refuses_before_state_or_snippet_writes(setup_plan, fault, reason):
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution('prepare'), backend, 'complete-root', IMAGE, tofu)
    review = plan.parent / 'review.json'
    if fault == 'missing':
        review.unlink()
    elif fault == 'invalid':
        review.write_text('protected-secret-sentinel')
    else:
        data = json.loads(review.read_text())
        data['vm_policy']['cluster_scope'] = 'other-cluster'
        review.write_text(json.dumps(data))
    apply = execution('apply')
    with pytest.raises(ValidationError, match=reason) as caught:
        apply_saved_plan(plan, plan.parent, selected, apply, backend, 'complete-root', IMAGE, tofu)
    assert 'protected-secret-sentinel' not in str(caught.value)
    assert apply.phases == []


def test_launcher_transfer_reaches_real_saved_plan_admission(setup_plan):
    import subprocess
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution('prepare'), backend, 'complete-root', IMAGE, tofu)
    result = subprocess.run(['go', 'test', '-tags=runtime_integration', '-run',
                             '^TestTransferredSavedPlanRealAdmission$', '-count=1', '.'],
                            cwd=REPO / 'automation/launcher', capture_output=True, text=True,
                            env={**os.environ, 'IAAS_TEST_SAVED_BUNDLE': str(plan.parent)})
    assert result.returncode == 0, result.stdout + result.stderr


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
    from iaas.runtime_execution import pve_state
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
    from iaas.runtime_execution.plans import verify_pve
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


def test_unpooled_provider_delete_plan_apply_verify_preserves_frozen_changes(setup_plan, monkeypatch):
    from iaas.runtime_execution import plans, pve_state
    from iaas.runtime_execution.pve_state import StateObservation
    selected, backend, tofu, execution = setup_plan
    selected.documents['vms']['vms'] = []
    before = {'node_name': 'synthetic-node', 'vm_id': 500, 'pool_id': '',
              'smbios': [{'uuid': 'fixture-vm-uuid'}]}
    native = {'resource_changes': [{'address': 'proxmox_virtual_environment_vm.synthetic',
              'type': 'proxmox_virtual_environment_vm', 'change': {'actions': ['delete'],
              'before': before, 'after': None}}]}
    class API:
        present = True
        def effective_permissions(self, path):
            assert path == '/vms/500'
            return {path: {name: 0 for name in ('VM.Audit', 'VM.Allocate', 'VM.PowerMgmt', 'VM.Config.Options')}}
        def cluster_vm_resources(self):
            return [{'node': 'synthetic-node', 'vmid': 500, 'type': 'qemu'}] if self.present else []
        def node_status(self, node):
            return {'status': 'online'}
        def vm_config(self, node, vmid):
            return {'smbios1': 'uuid=fixture-vm-uuid', 'scsi0': 'local:vm-500-disk-0,size=8G'}
    api = API()
    monkeypatch.setattr(plans, 'api_client', lambda *a: api)
    def observe(*args):
        resources = [{'type': 'proxmox_virtual_environment_vm', 'name': 'synthetic',
                      'instances': [{'attributes': before}]}] if api.present else []
        serial = 1 if api.present else 2
        return StateObservation('present', backend.config['bucket'], backend.state_key(), backend.workspace,
                                None, lineage='synthetic-lineage', serial=serial, empty=not api.present,
                                raw={'version': 4, 'lineage': 'synthetic-lineage', 'serial': serial, 'resources': resources})
    monkeypatch.setattr(pve_state, 'observe_state', observe)
    plan = prepare_plan(selected, execution('prepare', NATIVE_PLAN_JSON=json.dumps(native)), backend,
                        'complete-root', IMAGE, tofu)
    frozen = {p: p.read_bytes() for p in plan.parent.rglob('*') if p.is_file()}
    apply = execution('apply')
    run = apply.run
    def apply_run(phase, *args, **kwargs):
        result = run(phase, *args, **kwargs)
        if phase == 'apply':
            api.present = False
        return result
    monkeypatch.setattr(apply, 'run', apply_run)
    apply_saved_plan(plan, plan.parent, selected, apply, backend, 'complete-root', IMAGE, tofu)
    selected.files['execution_result'] = apply.outputs.root / 'pve-result.json'
    plans.verify_pve(plan, plan.parent, selected, execution('verify'), 'complete-root', IMAGE)
    assert json.loads((plan.parent / 'native-plan.json').read_text()) == native
    assert all(p.read_bytes() == value for p, value in frozen.items())


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
    from iaas.runtime_execution.plans import read_pve
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
    from iaas.runtime_execution.plans import _state_transition
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


@pytest.fixture
def first_use_plan(setup_plan, monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from iaas.runtime_execution import plans, pve_state
    selected, backend, tofu, execution = setup_plan
    empty = pve_state.observe_state(backend, {})
    selected.documents["vms"]["vms"][0]["vmid"] = 799
    selected.documents["vms"]["vms"][0]["pool"] = None
    absent = replace(empty, status="absent", lineage=None, serial=None, empty=None, raw=None)
    values = {"node_name": "synthetic-node", "vm_id": 799, "cpu": [{"cores": 1}],
              "memory": [{"dedicated": 1024}], "started": False, "smbios": [{"uuid": "synthetic-uuid"}],
              "disk": [{"interface": "scsi0", "datastore_id": "synthetic", "size": 8}], "pool_id": None}
    populated = replace(empty, empty=False, serial=2, raw={
        **empty.raw, "serial": 2, "resources": [{"type": "proxmox_virtual_environment_vm", "name": "test",
            "instances": [{"attributes": values}]}]})
    admission = json.loads(selected.files["state_admission"].read_text())
    admission.pop("lineage")
    admission.update(mode="first_use", initialization_ref="synthetic-first-use")
    selected.files["state_admission"].write_text(json.dumps(admission))
    monkeypatch.setattr(pve_state, "observe_state", lambda *a: absent)
    monkeypatch.setattr(plans, "api_client", lambda *a: SimpleNamespace(
        cluster_vm_resources=lambda: [], effective_permissions=lambda path: {path: {
            name: 1 for name in ('VM.Audit', 'VM.Allocate', 'VM.Config.CPU', 'VM.Config.Memory',
                                'VM.Config.Options', 'VM.Config.Disk', 'VM.PowerMgmt')}},
        vm_config=lambda *a: {"cores": 1, "memory": 1024, "smbios1": "uuid=synthetic-uuid",
                              "scsi0": "synthetic:799/vm-799-disk-0.qcow2,size=8G"},
        vm_status=lambda *a: {"status": "stopped"}))
    native = {"resource_changes": [{"address": "proxmox_virtual_environment_vm.test",
        "type": "proxmox_virtual_environment_vm", "change": {"actions": ["create"], "after": values}}]}
    plan = prepare_plan(selected, execution("prepare", NATIVE_PLAN_JSON=json.dumps(native)),
                        backend, "complete-root", IMAGE, tofu)
    return selected, backend, tofu, execution, plan, absent, empty, populated


@pytest.mark.parametrize("outcome", ["present", "absent", "error", "native_failure", "recovery_state"])
def test_first_use_apply_collects_only_after_complete_native_success(first_use_plan, monkeypatch, outcome):
    from dataclasses import replace
    from iaas.runtime_execution import pve_state
    selected, backend, tofu, execution, plan, absent, _, populated = first_use_plan
    observations = iter([absent, absent, populated if outcome == "present" else replace(absent, status=outcome)])
    reads = []

    def observe(*args):
        reads.append(1)
        return next(observations)

    monkeypatch.setattr(pve_state, "observe_state", observe)
    changes = {"APPLY_EXIT": "1"} if outcome == "native_failure" else {"STATE_WRITE_FAIL": "1"} if outcome == "recovery_state" else {}
    apply = execution("apply", **changes)
    if outcome == "present":
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    else:
        with pytest.raises(OperationFailed if outcome == "native_failure" else ValidationError):
            apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    result = json.loads((apply.outputs.root / "pve-result.json").read_text())
    assert result["native_execution"]["status"] == ("failed" if outcome == "native_failure" else "success")
    if outcome == "present":
        assert result["snapshot"] == populated.raw
        assert result["collection"]["status"] == result["verification"]["status"] == "passed"
        assert result["phase"] == "succeeded"
    else:
        assert result["phase"] == "failed"
        assert result["collection"]["status"] != "passed"
        assert "snapshot" not in result
    assert len(reads) == (2 if outcome in {"native_failure", "recovery_state"} else 3)


@pytest.mark.parametrize("stage", ["before_apply", "initialization", "lineage_change"])
def test_first_use_does_not_admit_unexpected_state(first_use_plan, monkeypatch, stage):
    from dataclasses import replace
    from iaas.runtime_execution import pve_state
    selected, backend, tofu, execution, plan, absent, empty, populated = first_use_plan
    observations = iter({
        "before_apply": [populated],
        "initialization": [absent, populated],
        "lineage_change": [absent, empty, replace(populated, lineage="other-lineage")],
    }[stage])
    monkeypatch.setattr(pve_state, "observe_state", lambda *a: next(observations))
    apply = execution("apply")
    with pytest.raises(ValidationError, match="unassociated state|changed lineage"):
        apply_saved_plan(plan, plan.parent, selected, apply, backend, "complete-root", IMAGE, tofu)
    if stage != "lineage_change":
        assert not any(item["phase"] in {"upload-snippets", "apply"} for item in apply.phases)
    else:
        result = json.loads((apply.outputs.root / "pve-result.json").read_text())
        assert result["native_execution"]["status"] == "success"
        assert result["collection"]["status"] == "unknown"


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


def test_private_ca_is_frozen_before_clients_and_restored_cross_directory(setup_plan, api_ca, tmp_path, monkeypatch):
    from iaas.runtime_execution import plans, pve_provider
    from iaas.runtime_execution.plans import verify_pve
    selected, backend, tofu, execution = setup_plan
    selected.files['api_ca'] = api_ca
    original_bytes = api_ca.read_bytes()
    observed = []
    original_client = plans.api_client

    def client(target, environ):
        path = Path(environ['PVE_API_CA'])
        assert path != api_ca and path.read_bytes() == original_bytes
        observed.append(path)
        api_ca.write_text('caller source changed after freeze')
        return original_client(target, environ)

    def provider(_provider, _files, environ):
        assert Path(environ['PVE_API_CA']).read_bytes() == original_bytes

    monkeypatch.setattr(plans, 'api_client', client)
    monkeypatch.setattr(pve_provider, 'prepare_provider_environment', provider)
    plan = prepare_plan(selected, execution('prepare'), backend, 'complete-root', IMAGE, tofu)
    metadata = json.loads((plan.parent / 'summary.json').read_text())
    assert metadata['api_ca'] == {'path': 'trust/api-ca.pem', 'sha256': plans.sha256(plan.parent / 'trust/api-ca.pem')}
    assert 'trust/api-ca.pem' in metadata['companion_files']
    moved = tmp_path / 'another-runner'
    shutil.copytree(plan.parent, moved)
    shutil.rmtree(plan.parent)
    api_ca.unlink()
    selected.files['api_ca'] = tmp_path / 'missing-current-ca'
    apply = execution('apply', PVE_API_CA=str(selected.files['api_ca']))
    apply_saved_plan(moved / 'plan.tfplan', moved, selected, apply, backend, 'complete-root', IMAGE, tofu)
    selected.files['execution_result'] = apply.outputs.root / 'pve-result.json'
    verify = execution('verify', PVE_API_CA=str(selected.files['api_ca']))
    verify_pve(moved / 'plan.tfplan', moved, selected, verify, 'complete-root', IMAGE)
    assert len(observed) == 3
    assert observed[1].is_relative_to(apply.outputs.root)
    assert observed[2] == moved / 'trust/api-ca.pem'
    assert not verify.phases


@pytest.mark.parametrize('damage', ['missing', 'changed', 'escape', 'symlink', 'unlisted'])
@pytest.mark.parametrize('operation', ['apply', 'verify'])
def test_private_ca_damage_rejected_before_effects(setup_plan, api_ca, tmp_path, monkeypatch, damage, operation):
    from iaas.runtime_execution import plans, pve_state
    selected, backend, tofu, execution = setup_plan
    selected.files['api_ca'] = api_ca
    plan = prepare_plan(selected, execution('prepare'), backend, 'complete-root', IMAGE, tofu)
    ca = plan.parent / 'trust/api-ca.pem'
    metadata_path = plan.parent / 'summary.json'
    metadata = json.loads(metadata_path.read_text())
    if damage == 'missing':
        ca.unlink()
    elif damage == 'changed':
        ca.write_text('changed')
    elif damage == 'escape':
        metadata['api_ca']['path'] = '../caller-ca.pem'
        metadata_path.write_text(json.dumps(metadata))
    elif damage == 'symlink':
        ca.unlink()
        ca.symlink_to(api_ca)
    else:
        metadata['companion_files'].remove('trust/api-ca.pem')
        metadata_path.write_text(json.dumps(metadata))
    monkeypatch.setattr(plans, 'api_client', lambda *a: pytest.fail('API before trust admission'))
    monkeypatch.setattr(pve_state, 'observe_state', lambda *a: pytest.fail('state access before trust admission'))
    monkeypatch.setattr(S3Backend, 'initialize', lambda *a, **k: pytest.fail('init before trust admission'))
    run = execution(operation)
    with pytest.raises(ValidationError, match='saved PVE API CA'):
        if operation == 'apply':
            apply_saved_plan(plan, plan.parent, selected, run, backend, 'complete-root', IMAGE, tofu)
        else:
            plans.verify_pve(plan, plan.parent, selected, run, 'complete-root', IMAGE)
    assert run.phases == []


@pytest.mark.parametrize('insecure', [False, True])
def test_no_effective_ca_plan_does_not_restore_current_trust(setup_plan, tmp_path, insecure):
    selected, backend, tofu, execution = setup_plan
    selected.options['pve']['insecure'] = insecure
    if insecure:
        empty = tmp_path / 'unused-ca'
        empty.touch()
        selected.files['api_ca'] = empty
    prepare = execution('prepare', PVE_API_CA='/unselected/host-ca')
    plan = prepare_plan(selected, prepare, backend, 'complete-root', IMAGE, tofu)
    assert 'PVE_API_CA' not in prepare.environ
    metadata = json.loads((plan.parent / 'summary.json').read_text())
    assert 'api_ca' not in metadata and not (plan.parent / 'trust').exists()
    apply = execution('apply', PVE_API_CA='/current/ca-must-not-be-used')
    apply_saved_plan(plan, plan.parent, selected, apply, backend, 'complete-root', IMAGE, tofu)
    assert 'PVE_API_CA' not in apply.environ


def test_read_does_not_report_success_after_tls_failure(setup_plan, monkeypatch):
    from types import SimpleNamespace
    from iaas.pve_inventory.pve_api.errors import PveApiTlsError
    from iaas.runtime_execution import plans, pve_state
    selected, backend, _tofu, execution = setup_plan
    observation = pve_state.observe_state(backend, {})
    observation.raw['resources'] = [{'type': 'proxmox_virtual_environment_vm', 'name': 'test', 'instances': [
        {'attributes': {'node_name': 'node', 'vm_id': 101}}]}]
    monkeypatch.setattr(pve_state, 'observe_state', lambda *a: observation)

    def failed(*_args):
        raise PveApiTlsError('synthetic TLS verification failed')

    monkeypatch.setattr(plans, 'api_client', lambda *a: SimpleNamespace(vm_config=failed))
    run = execution('read')
    with pytest.raises(PveApiTlsError):
        plans.read_pve(selected, run, backend, 'complete-root', IMAGE)
    assert not (run.outputs.root / 'summary.json').exists()


@pytest.mark.parametrize('stage', ['before_init', 'after_init'])
def test_saved_apply_rechecks_vmid_before_any_facility_write(first_use_plan, monkeypatch, stage):
    from iaas.runtime_execution import plans

    selected, backend, tofu, execution, plan, *_ = first_use_plan
    api = plans.api_client({}, {})
    calls = []

    def inventory():
        calls.append('inventory')
        if stage == 'before_init' or len(calls) > 1:
            return [{'vmid': 799, 'node': 'synthetic-node', 'type': 'qemu'}]
        return []

    api.cluster_vm_resources = inventory
    monkeypatch.setattr(plans, 'api_client', lambda *args: api)
    run = execution('occupied')
    with pytest.raises(ValidationError, match='VMID is occupied'):
        apply_saved_plan(plan, plan.parent, selected, run, backend, 'complete-root', IMAGE, tofu)
    assert not any(phase['phase'] in {'upload-snippets', 'apply'} for phase in run.phases)
    assert len(calls) == (1 if stage == 'before_init' else 2)


def test_saved_apply_rejects_changed_current_pool_before_facility_write(setup_plan):
    selected, backend, tofu, execution = setup_plan
    plan = prepare_plan(selected, execution('prepare'), backend, 'complete-root', IMAGE, tofu)
    selected.documents['vms']['vms'][0]['pool'] = 'another-pool'
    run = execution('changed-pool')
    with pytest.raises(ValidationError, match='current pool, VMID or reservation policy'):
        apply_saved_plan(plan, plan.parent, selected, run, backend, 'complete-root', IMAGE, tofu)
    assert run.phases == []
