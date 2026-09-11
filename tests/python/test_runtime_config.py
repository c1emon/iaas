from pathlib import Path

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_config import InputRequired, SourceReader, load_environment
from iaas_automation.runtime_config.compile import compile_documents, export_generated
from iaas_automation.runtime_config.selection import RuntimeSelection


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value))
    return path


def entry(tmp_path, **extra):
    return write(tmp_path / "environment.yml", {
        "schema_version": 1, "environment": "lab",
        "facts": {"network": "facts.yml", "unused": "missing-facts.yml"},
        "components": {"opnsense": {"inputs": {"aliases": "aliases.yml"}}},
        "scenarios": {"unused": {"pve": {"inputs": {"cluster": "absent.yml"}}}},
        **extra,
    })


def test_selected_refs_and_unused_inputs(tmp_path):
    config = entry(tmp_path)
    write(tmp_path / "facts.yml", {"address": "192.0.2.1", "unused": {"$ref": "facts.network.unused"}})
    write(tmp_path / "aliases.yml", {"opnsense_aliases": [] , "test": {"$ref": "facts.network.address"}})
    selected = load_environment(config, "opnsense")
    assert selected.documents["aliases"]["test"] == "192.0.2.1"
    assert {p.name for p in selected.reader.sources} == {"environment.yml", "aliases.yml", "facts.yml"}


@pytest.mark.parametrize("facts", [{"address": {"$ref": "facts.network.address"}}, {"other": 1}])
def test_invalid_reachable_refs(tmp_path, facts):
    config = entry(tmp_path)
    write(tmp_path / "facts.yml", facts)
    write(tmp_path / "aliases.yml", {"value": {"$ref": "facts.network.address"}})
    with pytest.raises(ValidationError):
        load_environment(config, "opnsense")


def test_scenario_replaces_component_and_unknown_does_not_fallback(tmp_path):
    config = entry(tmp_path, scenarios={"test": {"opnsense": {"inputs": {"aliases": "test.yml"}}}})
    write(tmp_path / "test.yml", {"opnsense_aliases": []})
    assert load_environment(config, "opnsense", "test").documents == {"aliases": {"opnsense_aliases": []}}
    with pytest.raises(ValidationError, match="unknown scenario"):
        load_environment(config, "opnsense", "typo")


@pytest.mark.parametrize("version", [None, 2, True, "1"])
def test_reject_unknown_version(tmp_path, version):
    with pytest.raises(ValidationError, match="schema_version"):
        load_environment(entry(tmp_path, schema_version=version), "opnsense")


def test_discovery_requires_each_file_and_rejects_mapped_symlink(tmp_path):
    config = entry(tmp_path)
    reader = SourceReader(mapping={})
    with pytest.raises(InputRequired) as error:
        load_environment(config, "opnsense", reader=reader)
    assert error.value.path == config
    reader.mapping[str(config)] = str(config)
    with pytest.raises(InputRequired) as error:
        load_environment(config, "opnsense", reader=reader)
    assert error.value.path == tmp_path / "aliases.yml"
    alias = write(tmp_path / "actual.yml", {"opnsense_aliases": []})
    link = tmp_path / "aliases.yml"
    link.symlink_to(alias)
    reader.mapping[str(link)] = str(link)
    with pytest.raises(ValidationError, match="symlink"):
        load_environment(config, "opnsense", reader=reader)


def test_two_layouts_domain_output_and_safe_export(tmp_path, monkeypatch):
    outputs = []
    for layout in ["flat", "facilities/router"]:
        directory = tmp_path / layout
        config = entry(directory, components={"foundation": {"inputs": {
            "inventory": str(FIXTURES / "runtime/foundation.yml")}}})
        monkeypatch.chdir(tmp_path)
        selected = load_environment(config, "foundation")
        outputs.append(compile_documents(selected))
        destination = directory / "generated"
        export_generated(selected, tmp_path / "implementation", destination)
        assert (destination / "foundation.md").read_text() == outputs[-1]["foundation.md"]
        with pytest.raises(ValidationError, match="already exist"):
            export_generated(selected, tmp_path / "implementation", destination)
        with pytest.raises(ValueError, match="overlaps"):
            export_generated(selected, tmp_path / "implementation", config)
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("component,inputs", [
    ("pve", {"cluster": "runtime/pve-cluster.yml", "vms": "runtime/vms.yml"}),
    ("services", {"services": "runtime/services.yml", "vms": "runtime/vms.yml"}),
    ("k3s", {"intent": "k3s/intent.yml", "inventory": "k3s/generated-pve.yml"}),
    ("opnsense", {"aliases": "opnsense-capabilities/aliases.yml"}),
    ("switch", {"config": "environment/ansible/vars/switches/sw-core-vlans.yml"}),
])
def test_existing_domain_compilers(tmp_path, component, inputs):
    config = entry(tmp_path, components={component: {"inputs": {k: str(FIXTURES/v) for k, v in inputs.items()}}})
    assert compile_documents(load_environment(config, component))


def test_resolved_type_rejected_by_domain_without_value_leak(tmp_path):
    config = entry(tmp_path)
    write(tmp_path / "facts.yml", {"bad": "sensitive-value"})
    write(tmp_path / "aliases.yml", {"opnsense_aliases": {"$ref": "facts.network.bad"}})
    with pytest.raises(ValidationError, match="domain validation") as error:
        compile_documents(load_environment(config, "opnsense"))
    assert "sensitive-value" not in str(error.value)


def test_runtime_selection_is_explicit():
    valid = {"interface_version": 1, "image": "example/iaas:v1.2.3", "platform": "linux/amd64"}
    assert RuntimeSelection.from_document(valid).image == valid["image"]
    for changed in [{"image": "example/iaas"}, {"image": "example/iaas:latest"},
                    {"interface_version": True}, {"platform": "linux/arm64"}]:
        with pytest.raises(ValidationError):
            RuntimeSelection.from_document({**valid, **changed})


def test_documented_layouts_are_equivalent():
    examples = FIXTURES.parents[1] / "docs/examples/runtime"
    flat = load_environment(examples / "flat/environment.yml", "opnsense")
    facility = load_environment(examples / "facility/environment.yml", "opnsense")
    assert compile_documents(flat) == compile_documents(facility)
    empty = load_environment(examples / "flat/environment.yml", "opnsense", "empty")
    assert yaml.safe_load(compile_documents(empty)["aliases.yml"]) == {"opnsense_aliases": []}


def test_switch_check_reuses_role_input_rejection(tmp_path):
    config = entry(tmp_path, components={"switch": {"inputs": {"config": "switch.yml"}}})
    write(tmp_path / "switch.yml", {"switch_config_resources": {"vlans": [{"state": "deleted", "config": []}]}})
    with pytest.raises(ValidationError, match="domain validation"):
        compile_documents(load_environment(config, "switch"))


def test_operation_input_closure_skips_unneeded_protected_files(tmp_path):
    config = entry(tmp_path, components={"pve": {
        "inputs": {"cluster": "missing-current-cluster.yml", "vms": "missing-current-vms.yml"},
        "files": {"backend": "backend.json", "guest-secret": "unavailable-secret"},
    }})
    write(tmp_path / "backend.json", {"selected": "backend"})
    selected = load_environment(config, "pve", input_names=set(), file_names={"backend"})
    assert selected.documents == {}
    assert set(selected.files) == {"backend"}
