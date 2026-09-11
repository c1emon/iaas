"""Formal runtime paths for the post-archive review, without facility access."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from iaas_automation.foundation_inventory.health import ProbeOutcome, run_health_checks
from iaas_automation.foundation_inventory.model import build_model
from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_config import load_environment
from iaas_automation.runtime_execution.__main__ import main
from iaas_automation.runtime_execution.execution import Execution


REPO = Path(__file__).resolve().parents[2]


def write(path, value):
    path.write_text(yaml.safe_dump(value))
    return path


@pytest.mark.parametrize("field", ["whole.selected", "alias.selected", "chain.selected"])
def test_fact_alias_only_reads_selected_field(tmp_path, field):
    entry = write(tmp_path / "environment.yml", {
        "schema_version": 1, "environment": "lab",
        "facts": {"network": "facts.yml", "unrelated": "absent.yml"},
        "components": {"opnsense": {"inputs": {"aliases": "input.yml"}}},
    })
    write(tmp_path / "facts.yml", {
        "whole": {"selected": "192.0.2.1", "unused": {"$ref": "facts.unrelated.value"}},
        "alias": {"$ref": "facts.network.whole"}, "chain": {"$ref": "facts.network.alias"},
    })
    write(tmp_path / "input.yml", {"value": {"$ref": "facts.network." + field}})
    selected = load_environment(entry, "opnsense")
    assert selected.documents["aliases"]["value"] == "192.0.2.1"
    assert {p.name for p in selected.reader.sources} == {"environment.yml", "input.yml", "facts.yml"}


@pytest.mark.parametrize("alias,variable", [
    ("aws_credentials", "AWS_SHARED_CREDENTIALS_FILE"), ("aws_config", "AWS_SHARED_CONFIG_FILE"),
    ("aws_ca", "AWS_CA_BUNDLE"), ("aws_web_identity", "AWS_WEB_IDENTITY_TOKEN_FILE"),
])
def test_discovery_excludes_overridden_host_aws_file(tmp_path, capsys, monkeypatch, alias, variable):
    files = {name: name for name in ("backend", "ssh_key", "known_hosts", alias)}
    for name in files:
        (tmp_path / name).write_text("synthetic")
    entry = write(tmp_path / "environment.yml", {"schema_version": 1, "environment": "lab",
                  "components": {"pve": {"files": files}}})
    monkeypatch.setenv(variable, str(tmp_path / "missing-host-file"))
    args = ["--environment", str(entry), "--component", "pve", "--operation", "apply-saved-plan", "--discover"]
    assert main(args) == 0
    ready = json.loads(capsys.readouterr().out)
    assert variable not in ready["credential_names"]
    assert str(tmp_path / alias) in ready["sources"]
    del files[alias]
    write(entry, {"schema_version": 1, "environment": "lab", "components": {"pve": {"files": files}}})
    assert main(args) == 0
    assert variable in json.loads(capsys.readouterr().out)["credential_names"]


def foundation_entry(tmp_path, *, ca=False):
    inventory = yaml.safe_load((REPO / "tests/fixtures/runtime/foundation.yml").read_text())
    if ca:
        inventory["foundation_services"][0]["health_check"] = {
            "type": "https", "target": "https://example.invalid", "ca_file": "trust.pem"}
    else:
        optional = deepcopy(inventory["foundation_services"][0])
        optional.update(name="optional", tier="optional", required_before_k3s=False, health_check=None)
        optional.pop("restore_order")
        inventory["foundation_services"].insert(0, optional)
    write(tmp_path / "inventory.yml", inventory)
    component = {"inputs": {"inventory": "inventory.yml"}}
    if ca:
        component.update(files={"trust": "trust.pem"}, options={"ca_files": {"trust.pem": "trust"}})
        (tmp_path / "trust.pem").write_text("synthetic CA")
    return write(tmp_path / "environment.yml", {"schema_version": 1, "environment": "lab",
                                                "components": {"foundation": component}})


def test_foundation_null_probe_does_not_block_other_services(tmp_path, monkeypatch):
    entry = foundation_entry(tmp_path)
    results = []
    def health(self, phase, command, cwd):
        document = yaml.safe_load(Path(command[command.index("--inventory") + 1]).read_text())
        results.extend(run_health_checks(build_model(document), {"tcp": lambda _: ProbeOutcome("passed", "synthetic")}))
    monkeypatch.setattr(Execution, "run", health)
    assert main(["--environment", str(entry), "--component", "foundation", "--operation", "health",
                 "--scope", "lab", "--output", str(tmp_path / "out")]) == 0
    assert [result.severity for result in results] == ["SKIP", "PASS"]


@pytest.mark.parametrize("mode,exit_code", [(0o666, 2), (0o644, 0)])
def test_foundation_ca_permissions_checked_before_health(tmp_path, monkeypatch, mode, exit_code):
    entry = foundation_entry(tmp_path, ca=True)
    (tmp_path / "trust.pem").chmod(mode)
    calls = []
    monkeypatch.setattr(Execution, "run", lambda *args: calls.append(args))
    assert main(["--environment", str(entry), "--component", "foundation", "--operation", "health",
                 "--scope", "lab", "--output", str(tmp_path / "out")]) == exit_code
    assert bool(calls) == (exit_code == 0)


@pytest.mark.parametrize("change,extra,reason", [
    ({"schema_version": "synthetic-private-value"}, [], "schema_version: 1"),
    ({}, ["--scenario", "synthetic-private-value"], "unknown scenario"),
    ({"components": []}, [], "components must be a mapping"),
])
def test_runtime_discovery_explains_configuration_without_values(tmp_path, capsys, change, extra, reason):
    entry = write(tmp_path / "environment.yml", {"schema_version": 1, "environment": "lab",
                  "components": {"opnsense": {"inputs": {"aliases": "input.yml"}}}, **change})
    assert main(["--environment", str(entry), "--component", "opnsense", "--operation", "check",
                 "--discover", *extra]) == 2
    report = json.loads(capsys.readouterr().out)
    assert reason in report["reason"]
    assert "synthetic-private-value" not in json.dumps(report)


@pytest.mark.parametrize("facts", [
    {"a": {"$ref": "facts.network.b"}, "b": {"$ref": "facts.network.a"}},
    {"a": {"$ref": "facts.network.a.selected"}},
])
def test_selected_alias_cycles_are_rejected(tmp_path, facts):
    entry = write(tmp_path / "environment.yml", {
        "schema_version": 1, "environment": "lab", "facts": {"network": "facts.yml"},
        "components": {"opnsense": {"inputs": {"aliases": "input.yml"}}},
    })
    write(tmp_path / "facts.yml", facts)
    write(tmp_path / "input.yml", {"value": {"$ref": "facts.network.a.selected"}})
    with pytest.raises(ValidationError, match="cyclic shared-fact"):
        load_environment(entry, "opnsense")


def test_fact_object_can_select_its_own_scalar_through_an_alias(tmp_path):
    entry = write(tmp_path / "environment.yml", {
        "schema_version": 1, "environment": "lab", "facts": {"network": "facts.yml"},
        "components": {"opnsense": {"inputs": {"aliases": "input.yml"}}},
    })
    write(tmp_path / "facts.yml", {"whole": {"selected": 1, "copy": {"$ref": "facts.network.alias.selected"}},
                                    "alias": {"$ref": "facts.network.whole"}})
    write(tmp_path / "input.yml", {"value": {"$ref": "facts.network.whole"}})
    assert load_environment(entry, "opnsense").documents["aliases"]["value"] == {"selected": 1, "copy": 1}


def test_yaml_error_reports_format_without_parser_source(tmp_path, capsys):
    entry = tmp_path / "environment.yml"
    entry.write_text('schema_version: [synthetic-private-value\n')
    assert main(["--environment", str(entry), "--component", "opnsense", "--operation", "check", "--discover"]) == 2
    report = capsys.readouterr().out
    assert "not readable YAML" in report
    assert "synthetic-private-value" not in report
