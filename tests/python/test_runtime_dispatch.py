import json
from pathlib import Path

import yaml

from iaas_automation.runtime_execution.__main__ import main
from iaas_automation.runtime_execution.execution import Execution
from iaas_automation.runtime_execution.selection import load_operation
from iaas_automation.runtime_config import SourceReader


REPO = Path(__file__).resolve().parents[2]


def config(tmp_path, component, inputs, files=None):
    entry = tmp_path / "environment.yml"
    entry.write_text(yaml.safe_dump({"schema_version": 1, "environment": "synthetic",
                                    "components": {component: {"inputs": inputs, "files": files or {}}}}))
    return entry


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
