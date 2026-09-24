import json
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from iaas.common.errors import ValidationError
from iaas.opnsense_workflow import local, runtime
from iaas.opnsense_workflow.presentation import project_observations
from iaas.runtime_execution.execution import Execution
from iaas.runtime_execution import selection as runtime_selection


def observation():
    return {
        "aliases": {
            "status": "complete",
            "observation_scope": "configuration",
            "objects": [
                {"identity": ["SYSTEM"], "configuration": None,
                 "classification": {"origin": "system_builtin", "management": "read_only",
                                     "basis": ["fixed-native"]},
                 "reason": "native_only"},
                {"identity": ["USER"], "configuration": {"type": "host"},
                 "classification": {"origin": "user_config", "management": "independent",
                                     "basis": ["standard-config"]}},
                {"identity": ["UNKNOWN"], "configuration": None,
                 "classification": {"origin": "unknown", "management": "unknown",
                                     "basis": []},
                 "reason": "conversion_failed"},
            ],
            "coverage": {"scope": "selected_resource", "rows": 3, "total": 3, "complete": True},
        }
    }


def test_default_view_hides_only_confirmed_non_independent_system_objects():
    source = observation()
    result = project_observations(source, {"aliases": "all"})
    assert [item["identity"] for item in result["aliases"]["objects"]] == [["USER"], ["UNKNOWN"]]
    assert result["aliases"]["observation_scope"] == "display"
    assert result["aliases"]["summary"]["selection_matched_count"] == 3
    assert result["aliases"]["summary"]["displayed_count"] == 2
    assert result["aliases"]["summary"]["hidden_count"] == 1
    assert result["aliases"]["summary"]["enumerated_total"] == 3
    assert source["aliases"]["objects"][0]["identity"] == ["SYSTEM"]


def test_explicit_identity_keeps_hidden_object_and_include_system_does_not_read_more():
    source = observation()
    result = project_observations(source, {"aliases": [["SYSTEM"]]})
    assert result["aliases"]["objects"][0]["identity"] == ["SYSTEM"]
    assert result["aliases"]["summary"]["hidden_count"] == 0
    included = project_observations(source, {"aliases": "all"}, include_system=True)
    assert len(included["aliases"]["objects"]) == 3
    assert included["aliases"]["observation_scope"] == "display"


@pytest.mark.parametrize("value", [None, 1, "true", [], {}])
def test_include_system_is_strict_boolean(value):
    with pytest.raises(ValidationError, match="include_system"):
        project_observations(observation(), {"aliases": "all"}, include_system=value)


def test_incomplete_observation_preserves_status_and_visible_user_conversion_failure():
    source = observation()
    source["aliases"]["status"] = "incomplete"
    source["aliases"]["objects"] = [source["aliases"]["objects"][2]]
    result = project_observations(source, {"aliases": "all"})["aliases"]
    assert result["status"] == "incomplete"
    assert result["objects"][0]["identity"] == ["UNKNOWN"]
    assert result["summary"]["configuration_counts"]["user_config_failed"] == 0

    failed = observation()
    failed["aliases"]["objects"] = [{
        "identity": ["FAILED"], "configuration": None,
        "classification": {"origin": "user_config", "management": "independent",
                             "basis": ["supported_model"]},
        "reason": "conversion_failed",
    }]
    projected = project_observations(failed, {"aliases": "all"})["aliases"]
    assert projected["objects"][0]["identity"] == ["FAILED"]
    assert projected["summary"]["configuration_counts"]["user_config_failed"] == 1


class _EntryReader:
    def __init__(self, *_args):
        self.closed = False

    def read(self, resources):
        return {resource: {**value, "resource": resource}
                for resource, value in observation().items() if resource in resources}

    def close(self):
        self.closed = True


class _EntryOutputs:
    def __init__(self, root: Path):
        self.root = root
        self.phases = []
        for category in ("diagnostics", "plan", "recovery", "work"):
            (root / category).mkdir(parents=True)

    def path(self, category):
        return self.root / category

    def summary(self, value):
        (self.root / "summary.json").write_text(json.dumps(value))


def _formal_selected(tmp_path, *, include_system=False):
    inventory = tmp_path / "inventory.yml"
    request = tmp_path / "request.yml"
    inventory.write_text(yaml.safe_dump({"all": {"children": {"opnsense": {"hosts": {
        "fw": {"opnsense_api_host": "https://192.0.2.254", "opnsense_ssl_verify": True}
    }}}}}))
    request.write_text(yaml.safe_dump({"schema_version": 1, "selection": {"aliases": "all"}}))

    class Selected:
        files = {"inventory": inventory, "request": request}
        options = {"include_system": include_system} if include_system else {}
        documents = {}
        input_paths = {}
        environment = "synthetic"
        scenario = None
        reader = None

    return Selected()


def test_formal_read_writes_complete_artifact_then_returns_display_result(tmp_path, monkeypatch):
    import iaas.opnsense_workflow.reader as reader_module

    monkeypatch.setattr(reader_module, "Reader", _EntryReader)
    selected = _formal_selected(tmp_path, include_system=True)
    outputs = _EntryOutputs(tmp_path / "formal")
    execution = Execution(outputs, {})
    runtime.run(selected, "read", "fw", execution, "sha256:" + "a" * 64)

    result = json.loads((outputs.path("diagnostics") / "result.json").read_text())
    complete = json.loads((outputs.path("diagnostics") / "observations.json").read_text())
    assert result["schema_version"] == 3 and result["kind"] == "opnsense-result"
    assert result["observation_scope"] == "display"
    assert complete["aliases"]["observation_scope"] == "configuration"
    assert len(result["observations"]["aliases"]["objects"]) == 3


def test_local_read_result_has_same_scope_and_full_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "Reader", _EntryReader)
    monkeypatch.setattr(local, "source_identity", lambda root: {
        "kind": "local-source", "source_sha256": "a" * 64,
    })
    input_path = tmp_path / "input.yml"
    input_path.write_text(yaml.safe_dump({
        "target": {"host": "fw", "endpoint": "https://192.0.2.254", "ssl_verify": True},
        "request": {"schema_version": 1, "selection": {"aliases": "all"}},
        "documents": {},
    }))
    args = Namespace(operation="read", input=input_path, output=tmp_path / "local",
                     candidate=None, candidate_sha256=None, execution_id=None,
                     activation_check=None, recovery=None, allow_test_writes=False,
                     check_mode=False, include_system=False)
    result = local.run_local(args)
    assert result["schema_version"] == 3 and result["kind"] == "opnsense-result"
    assert result["observation_scope"] == "display"
    complete = json.loads((args.output / "diagnostics/observations.json").read_text())
    assert complete["aliases"]["observation_scope"] == "configuration"
    assert len(result["observations"]["aliases"]["objects"]) == 2


def test_runtime_selection_rejects_include_system_for_non_read_and_non_boolean():
    class Selected:
        options = {"include_system": True}

    with pytest.raises(ValidationError, match="read, plan and verify"):
        runtime_selection._validate_opnsense_options(Selected(), "plan")

    Selected.options = {"include_system": "true"}
    with pytest.raises(ValidationError, match="boolean"):
        runtime_selection._validate_opnsense_options(Selected(), "read")
