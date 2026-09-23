import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from iaas_automation.runtime_execution.__main__ import main
from iaas_automation.runtime_execution.execution import Execution
from iaas_automation.runtime_execution.operations import capabilities, operation_for
from iaas_automation.runtime_execution.selection import load_operation
from iaas_automation.runtime_config import InputRequired, SourceReader


REPO = Path(__file__).resolve().parents[2]


def test_capabilities_advertise_lifecycle_contract_versions() -> None:
    assert capabilities()["lifecycle_versions"] == {
        "pve": {"plan": 2, "result": 1},
        "pve-template": {"preview": 2, "result": 2, "record": 2},
        "image": {"artifact": 1, "build_request": 1, "test_request": 1, "test_result": 1},
    }


def test_template_operations_do_not_forward_api_or_state_credentials():
    from iaas_automation.runtime_execution.operations import credential_names, process_environment
    for operation in ('check', 'read', 'plan', 'apply', 'verify'):
        expected = set() if operation in {"check", "verify"} else {'PVE_API_TOKEN', 'PVE_API_CA'}
        if operation == "apply":
            expected.add('PVE_ARTIFACT_URL')
        assert credential_names('pve-template', operation) == expected
        assert process_environment('pve-template', operation, {
            'PVE_API_TOKEN': 'scoped-token', 'PVE_API_CA': '/tmp/ca.pem', 'PVE_ARTIFACT_URL': 'https://objects.invalid/disk',
            'TF_VAR_pve_api_token_secret': 'must-not-pass',
            'AWS_SECRET_ACCESS_KEY': 'must-not-pass',
            'OPNSENSE_API_SECRET': 'must-not-pass'}) == ({
                'PVE_API_TOKEN': 'scoped-token', 'PVE_API_CA': '/tmp/ca.pem', 'PVE_ARTIFACT_URL': 'https://objects.invalid/disk'
            } if operation == "apply" else {
                'PVE_API_TOKEN': 'scoped-token', 'PVE_API_CA': '/tmp/ca.pem'
            } if operation in {"read", "plan"} else {})


def test_image_test_requests_persist_an_external_artifact_directory_mapping(tmp_path):
    request_path = tmp_path / "request.yml"
    artifact_root = tmp_path / "artifact-root"
    artifact_root.mkdir()
    request_path.write_text(yaml.safe_dump({"kind": "image-test-request", "artifact_root": str(artifact_root)}))
    entry = config(tmp_path, "image", {"test": str(request_path)})
    first = SourceReader({str(entry): str(entry), str(request_path): str(request_path)})
    with pytest.raises(InputRequired) as missing:
        load_operation(entry, "image", "test", None, first)
    assert missing.value.path == artifact_root.resolve()
    mapped = tmp_path / "mapped-artifact-root"
    mapped.mkdir()
    second = SourceReader({str(entry): str(entry), str(request_path): str(request_path), str(artifact_root.resolve()): str(mapped)})
    selected = load_operation(entry, "image", "test", None, second)
    assert selected.documents["test"]["artifact_root"] == str(mapped)


def test_image_runtime_receives_launcher_resolved_digest(tmp_path, monkeypatch):
    request = tmp_path / "build.yml"
    request.write_text(yaml.safe_dump({"kind": "image-build-request", "schema_version": 1}))
    entry = config(tmp_path, "image", {"build": str(request)})
    received = {}

    def fake_run(selected, operation, execution, *, execution_id=None, runtime_digest=None):
        received.update(operation=operation, execution_id=execution_id, runtime_digest=runtime_digest)
        execution.finish({"component": "image", "operation": operation, "status": "succeeded"})

    import iaas_automation.image.runtime as image_runtime
    monkeypatch.setattr(image_runtime, "run", fake_run)
    digest = "registry.invalid/runtime@sha256:" + "e" * 64
    assert main(["--environment", str(entry), "--component", "image", "--operation", "build",
                 "--execution-id", "build-1", "--image-digest", digest, "--scope", "image-build",
                 "--output", str(tmp_path / "build-1")]) == 0
    assert received == {"operation": "build", "execution_id": "build-1", "runtime_digest": digest}


def test_pve_cleanup_recovery_directory_is_mapped_read_only_for_plan_and_apply(tmp_path):
    recovery = tmp_path / "publish-evidence"
    recovery.mkdir()
    mapped = tmp_path / "mapped-publish-evidence"
    mapped.mkdir()
    cleanup = tmp_path / "cleanup.json"
    cleanup.write_text(json.dumps({
        "kind": "pve-template-cleanup-request", "schema_version": 1,
        "original_execution_dir": str(recovery),
    }))
    preview = tmp_path / "preview.json"
    preview.write_text(json.dumps({
        "kind": "pve-template-preview", "schema_version": 2, "action": "cleanup",
        "fixed_input": {"original_execution_dir": str(recovery)},
    }))
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({
        "schema_version": 1, "environment": "synthetic",
        "components": {"pve-template": {"inputs": {"cleanup": str(cleanup)},
                                           "files": {"preview": str(preview)},
                                           "options": {"action": "cleanup"}}},
    }))
    for operation in ("plan", "apply"):
        reader = SourceReader({str(entry): str(entry), str(cleanup): str(cleanup),
                               str(preview): str(preview), str(recovery): str(mapped)})
        selected = load_operation(entry, "pve-template", operation, None, reader)
        assert selected.files["original_execution_dir"] == mapped.resolve()
        assert selected.file_paths["original_execution_dir"] == recovery.resolve()


@pytest.mark.parametrize("preview_name", ["template_preview", "preview"])
def test_pve_template_apply_hydrates_preview_and_admission_from_selected_files(tmp_path, monkeypatch, preview_name):
    from iaas_automation.pve_template import contracts, runtime
    from test_image_publish_contracts import request as publish_request
    from test_pve_template_publisher import Outputs

    request = contracts.validate_publish_request(publish_request())
    preview = contracts.build_publish_preview(request, runtime={"image_digest": "runtime@sha256:" + "a" * 64})
    admission = {"schema_version": 1, "execution_id": "apply-1",
                 "plan_digest": preview["preview_digest"].removeprefix("sha256:"),
                 "target": request["target"], "approved": True,
                 "consumption": {"reserved": True, "reservation_id": "reservation-1"},
                 "pending": {"record_id": "pending-1"},
                 "serialization": {"held": True, "context_id": "context-1"}}
    request_path = tmp_path / "request.json"
    preview_path = tmp_path / "template-preview.json"
    admission_path = tmp_path / "execution-admission.json"
    request_path.write_text(json.dumps(request))
    preview_path.write_text(json.dumps(preview))
    admission_path.write_text(json.dumps(admission))
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({"schema_version": 1, "environment": "apply-check",
                                    "components": {"pve-template": {
                                        "inputs": {"request": str(request_path)},
                                        "files": {preview_name: str(preview_path),
                                                  "execution_admission": str(admission_path)}}}}))
    mapping = {str(path): str(path) for path in (entry, request_path, preview_path, admission_path)}
    selected = load_operation(entry, "pve-template", "apply", None, SourceReader(mapping))
    assert selected.options == {"action": "publish", "preview_digest": preview["preview_digest"],
                                "admission": admission}

    class ReachedGuard(Exception):
        pass

    def guard(*args, **kwargs):
        raise ReachedGuard

    monkeypatch.setattr(runtime, "_publish", guard)
    with pytest.raises(ReachedGuard):
        runtime.run(selected, "apply", "cohe", SimpleNamespace(outputs=Outputs(tmp_path / "output")),
                    image_digest=preview["runtime"]["image_digest"], execution_id="apply-1")


def test_launcher_rejects_duplicate_keys_in_image_json_contract(tmp_path, capsys):
    request = tmp_path / "request.json"
    request.write_text('{"kind":"image-test-request","kind":"image-test-request"}\n')
    entry = config(tmp_path, "image", {"test": str(request)})
    assert main(["--environment", str(entry), "--component", "image", "--operation", "check",
                 "--output", str(tmp_path / "check")]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_launcher_keeps_json_strictness_through_extensionless_input_mapping(tmp_path, capsys):
    logical = tmp_path / "request.json"
    physical = tmp_path / "mapped-input"
    physical.write_text('{"kind":"image-test-request","kind":"image-test-request"}\n')
    entry = config(tmp_path, "image", {"test": str(logical)})
    mapping = tmp_path / "input-map.json"
    mapping.write_text(json.dumps({str(entry): str(entry), str(logical): str(physical)}))
    assert main(["--environment", str(entry), "--input-map", str(mapping), "--component", "image",
                 "--operation", "check", "--output", str(tmp_path / "check")]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def config(tmp_path, component, inputs, files=None):
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({"schema_version": 1, "environment": "synthetic",
                                    "components": {component: {"inputs": inputs, "files": files or {}}}}))
    return entry


def candidate_file(path):
    value = {
        "schema_version": 3,
        "kind": "opnsense-candidate",
        "target": {"host": "firewall", "endpoint": "https://192.0.2.1", "ssl_verify": True},
        "runtime": {"image_digest": "sha256:" + "1" * 64, "platform": "linux/amd64", "interface_version": 1},
        "provider": "oxlorg.opnsense@1423500c29f88da9ba8147a23fc64006cf464159",
        "source": {},
        "request": {"schema_version": 1, "selection": {}},
        "documents": {}, "selected": [], "coverage": [], "before": {},
        "differences": [], "stages": [],
        "admission": {"status": "ready", "gaps": [], "recovery": "not_required", "guidance": None},
    }
    encoded = json.dumps(value, sort_keys=True, indent=2) + "\n"
    path.write_text(encoded)
    return hashlib.sha256(encoded.encode()).hexdigest()


def test_offline_dispatch_and_unsupported_operation(tmp_path, capsys):
    args = ["--environment", str(REPO / "docs/examples/runtime/flat/environment.yml"), "--component", "opnsense"]
    assert main([*args, "--operation", "generate", "--output", str(tmp_path / "result")]) == 0
    assert (tmp_path / "result/generated/aliases.yml").is_file()
    assert json.loads(capsys.readouterr().out)["effects"]["network"] is False
    assert main([*args, "--operation", "destroy", "--output", str(tmp_path / "rejected")]) == 2
    assert not (tmp_path / "rejected").exists()


def test_pve_health_needs_no_s3_and_does_not_forward_unrelated_credentials(tmp_path, monkeypatch):
    entry = config(tmp_path, "pve", {"cluster": str(REPO / "tests/fixtures/runtime/pve-cluster.yml"),
                                    "vms": str(REPO / "tests/fixtures/runtime/vms.yml")}, {"backend": "absent.json"})
    calls = []
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-pass")
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "must-not-pass")
    monkeypatch.setattr(Execution, "run", lambda self, phase, command, cwd: calls.append((phase, command, self.environ)))
    assert main(["--environment", str(entry), "--component", "pve", "--operation", "health",
                 "--scope", "synthetic-pve", "--output", str(tmp_path / "health")]) == 0
    assert len(calls) == 1 and calls[0][0] == "health"
    assert "AWS_SECRET_ACCESS_KEY" not in calls[0][2] and "OP_SERVICE_ACCOUNT_TOKEN" not in calls[0][2]


def test_partial_k3s_deploy_is_rejected_before_execution(tmp_path, monkeypatch, capsys):
    entry = config(tmp_path, "k3s", {"intent": str(REPO / "tests/fixtures/k3s/intent.yml"),
                                    "inventory": str(REPO / "tests/fixtures/k3s/generated-pve.yml")},
                   {"ssh_key": "key", "known_hosts": "known_hosts", "runtime_secrets": "runtime.json"})
    for name, data in {"key": "synthetic-key", "known_hosts": "synthetic-host",
                       "runtime.json": '{"op://synthetic/cluster/token":"synthetic-token"}'}.items():
        path = tmp_path / name
        path.write_text(data)
        path.chmod(0o600)
    called = []
    monkeypatch.setattr(Execution, "run", lambda *args: called.append(args))
    assert main(["--environment", str(entry), "--component", "k3s", "--operation", "deploy",
                 "--scope", "synthetic-server-01", "--output", str(tmp_path / "deploy")]) == 2
    assert not called
    assert "whole cluster" in json.loads(capsys.readouterr().out)["reason"]


def test_selected_online_file_closure_does_not_read_current_saved_plan_inputs(tmp_path):
    entry = config(tmp_path, "pve", {"cluster": "missing.yml", "vms": "missing-vms.yml"},
                   {"backend": "backend", "ssh_key": "key", "known_hosts": "hosts",
                    "state_admission": "state", "execution_admission": "execution", "dependencies": "unused"})
    for name in ["backend", "key", "hosts", "state", "execution"]:
        (tmp_path / name).write_text("synthetic")
    selected = load_operation(entry, "pve", "apply", None, SourceReader())
    assert not selected.documents and set(selected.files) == {"backend", "ssh_key", "known_hosts",
                                                               "state_admission", "execution_admission"}


def test_opnsense_workflow_file_and_effect_selection(tmp_path):
    entry = config(tmp_path, "opnsense",
                   {"aliases": "aliases.yml", "dnat": "dnat.yml"},
                   {"inventory": "inventory.yml", "request": "request.yml",
                    "candidate": "candidate.json"})
    (tmp_path / "inventory.yml").write_text("all: {}\n")
    (tmp_path / "request.yml").write_text(
        "schema_version: 1\nselection: {aliases: all, dnat: all}\n")
    candidate_sha256 = candidate_file(tmp_path / "candidate.json")
    (tmp_path / "aliases.yml").write_text("opnsense_aliases: []\n")
    (tmp_path / "dnat.yml").write_text("opnsense_dnat_rules: []\n")
    document = yaml.safe_load(entry.read_text())
    document["components"]["opnsense"]["options"] = {}
    entry.write_text(yaml.safe_dump(document))

    read = load_operation(entry, "opnsense", "read", None, SourceReader())
    assert not read.documents and set(read.files) == {"inventory", "request"}
    plan = load_operation(entry, "opnsense", "plan", None, SourceReader())
    assert set(plan.documents) == {"aliases", "dnat"}
    assert set(plan.files) == {"inventory", "request"}
    selected = load_operation(entry, "opnsense", "verify", None, SourceReader())
    assert not selected.documents and set(selected.files) == {"inventory", "candidate"}
    document["components"]["opnsense"]["options"] = {
        "candidate_sha256": candidate_sha256,
        "execution_id": "run-42",
        "activation_check": {
            "target": {"host": "firewall"}, "candidate_sha256": candidate_sha256,
            "execution_id": "run-42", "checked_no_pending": True, "serialized": True,
        },
    }
    entry.write_text(yaml.safe_dump(document))
    selected = load_operation(entry, "opnsense", "apply", None, SourceReader())
    assert not selected.documents and set(selected.files) == {"inventory", "candidate"}
    document["components"]["opnsense"]["options"]["check_mode"] = True
    entry.write_text(yaml.safe_dump(document))
    selected = load_operation(entry, "opnsense", "apply", None, SourceReader())
    assert selected.options["check_mode"] is True

    assert operation_for("opnsense", "read").state is False
    assert operation_for("opnsense", "plan").infrastructure_write is False
    assert operation_for("opnsense", "apply").infrastructure_write is True
    assert operation_for("opnsense", "verify").infrastructure_write is False


def test_opnsense_recovery_plan_selects_recovery_without_desired_inputs(tmp_path):
    entry = config(tmp_path, "opnsense", {},
                   {"inventory": "inventory.yml", "request": "request.yml", "recovery": "recovery.json"})
    (tmp_path / "inventory.yml").write_text("all: {}\n")
    (tmp_path / "request.yml").write_text("schema_version: 1\nselection: {}\n")
    (tmp_path / "recovery.json").write_text("{}\n")
    selected = load_operation(entry, "opnsense", "plan", None, SourceReader())
    assert not selected.documents and set(selected.files) == {"inventory", "request", "recovery"}


def test_opnsense_plan_discovers_complete_candidate_context(tmp_path):
    entry = config(tmp_path, "opnsense",
                   {"aliases": "aliases.yml", "dnat": "not-selected.yml"},
                   {"inventory": "inventory.yml", "request": "request.yml"})
    (tmp_path / "inventory.yml").write_text("all: {}\n")
    (tmp_path / "request.yml").write_text("schema_version: 1\nselection: {aliases: all}\n")
    (tmp_path / "aliases.yml").write_text("opnsense_aliases: []\n")
    try:
        load_operation(entry, "opnsense", "plan", None, SourceReader())
    except InputRequired as error:
        assert error.path.name == "not-selected.yml"
    except Exception as error:
        assert "readable regular file" in str(error)
    else:
        raise AssertionError("plan must discover every declared candidate input")


def test_launcher_execution_id_is_checked_during_discovery(tmp_path, capsys):
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({
        "schema_version": 1,
        "environment": "synthetic",
        "components": {"opnsense": {
            "inputs": {},
            "files": {"inventory": "inventory.yml", "candidate": "candidate.json"},
            "options": {
                "candidate_sha256": "a" * 64,
                "execution_id": "run-42",
                "activation_check": {
                    "target": {"host": "firewall"}, "candidate_sha256": "a" * 64,
                    "execution_id": "run-42", "checked_no_pending": True, "serialized": True,
                },
            },
        }},
    }))
    (tmp_path / "inventory.yml").write_text("all: {}\n")
    candidate_sha256 = candidate_file(tmp_path / "candidate.json")
    document = yaml.safe_load(entry.read_text())
    document["components"]["opnsense"]["options"]["candidate_sha256"] = candidate_sha256
    document["components"]["opnsense"]["options"]["activation_check"]["candidate_sha256"] = candidate_sha256
    entry.write_text(yaml.safe_dump(document))
    args = ["--environment", str(entry), "--component", "opnsense", "--operation", "apply", "--discover"]
    assert main([*args, "--execution-id", "wrong"]) == 2
    assert "wrong" not in capsys.readouterr().out
    assert main([*args, "--execution-id", "run-42"]) == 0
    assert json.loads(capsys.readouterr().out)["execution_id"] == "run-42"


def test_opnsense_request_is_validated_before_credentials(tmp_path, monkeypatch, capsys):
    entry = config(tmp_path, "opnsense", {}, {"inventory": "inventory.yml", "request": "request.yml"})
    (tmp_path / "inventory.yml").write_text("all: {}\n")
    (tmp_path / "request.yml").write_text("schema_version: 1\nselection: {snat: all}\n")
    import iaas_automation.runtime_execution.__main__ as dispatch
    monkeypatch.setattr(dispatch, "prepare_file_credentials", lambda *args: (_ for _ in ()).throw(
        AssertionError("credentials must not be prepared for an invalid request")))
    output = tmp_path / "result"
    assert main(["--environment", str(entry), "--component", "opnsense", "--operation", "read",
                 "--scope", "firewall", "--output", str(output)]) == 2
    assert not output.exists()
    assert "snat" not in capsys.readouterr().out


def test_setup_failure_reports_created_output_and_redacts_exception(tmp_path, monkeypatch, capsys):
    import iaas_automation.runtime_execution.__main__ as dispatch
    def fail(*args):
        raise yaml.YAMLError("synthetic-private-value")
    monkeypatch.setattr(dispatch, "prepare_file_credentials", fail)
    output = tmp_path / "failed"
    assert main(["--environment", str(REPO / "docs/examples/runtime/flat/environment.yml"),
                 "--component", "opnsense", "--operation", "generate", "--output", str(output)]) == 2
    report = capsys.readouterr().out
    assert "synthetic-private-value" not in report
    assert json.loads(report)["output"] == str(output)
    assert output.is_dir()


def test_opnsense_uses_existing_exact_target_admission(tmp_path, monkeypatch):
    entry = config(tmp_path, "opnsense", {}, {"inventory": "inventory.yml", "request": "request.yml"})
    (tmp_path / "inventory.yml").write_text(yaml.safe_dump({"all": {"children": {"opnsense": {"hosts": {"firewall": {}}}}}}))
    (tmp_path / "request.yml").write_text("include_details: true\n")
    calls = []
    monkeypatch.setattr(Execution, "run", lambda self, phase, command, cwd: calls.append((command, self.environ)))
    assert main(["--environment", str(entry), "--component", "opnsense", "--operation", "diagnose",
                 "--scope", "firewall", "--output", str(tmp_path / "diagnostic")]) == 0
    assert "--limit" not in calls[0][0]
    assert calls[0][1]["OPNSENSE_TARGET"] == "firewall"
    assert calls[0][1]["OPNSENSE_DIAGNOSTICS_OUTPUT"].endswith("/runtime/opnsense-diagnostics/detail.json")
