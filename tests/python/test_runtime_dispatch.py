import json
import hashlib
from pathlib import Path

import yaml

from iaas_automation.runtime_execution.__main__ import main
from iaas_automation.runtime_execution.execution import Execution
from iaas_automation.runtime_execution.operations import operation_for
from iaas_automation.runtime_execution.selection import load_operation
from iaas_automation.runtime_config import InputRequired, SourceReader


REPO = Path(__file__).resolve().parents[2]


def config(tmp_path, component, inputs, files=None):
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({"schema_version": 1, "environment": "synthetic",
                                    "components": {component: {"inputs": inputs, "files": files or {}}}}))
    return entry


def candidate_file(path):
    value = {
        "schema_version": 1,
        "kind": "opnsense-candidate",
        "target": {"host": "firewall", "endpoint": "https://192.0.2.1", "ssl_verify": True},
        "runtime": {"image_digest": "sha256:" + "1" * 64, "platform": "linux/amd64", "interface_version": 1},
        "provider": "oxlorg.opnsense@1423500c29f88da9ba8147a23fc64006cf464159",
        "source": {},
        "request": {"schema_version": 1, "selection": {}},
        "documents": {}, "selected": [], "coverage": [], "before": {},
        "differences": [], "stages": [],
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
                   {"backend": "backend", "ssh_key": "key", "known_hosts": "hosts", "dependencies": "unused"})
    for name in ["backend", "key", "hosts"]:
        (tmp_path / name).write_text("synthetic")
    selected = load_operation(entry, "pve", "apply-saved-plan", None, SourceReader())
    assert not selected.documents and set(selected.files) == {"backend", "ssh_key", "known_hosts"}


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
