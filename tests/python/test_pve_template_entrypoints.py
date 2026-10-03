from types import SimpleNamespace

import pytest

from iaas.common.errors import ValidationError
from iaas.pve_template import runtime

from test_image_publish_contracts import request as publish_request
from test_pve_template_publisher import API, Outputs


@pytest.mark.parametrize("action", [None, "publish", "cleanup", "retire"])
@pytest.mark.parametrize("invalid", [False, True])
def test_check_selects_action_input_and_validator_offline(tmp_path, monkeypatch, action, invalid):
    import json
    from pathlib import Path

    from iaas.runtime_config import SourceReader
    from iaas.runtime_execution.operations import operation_for
    from iaas.runtime_execution.selection import load_operation

    chosen = action or "publish"
    if chosen == "publish":
        request = publish_request()
    else:
        root = Path(__file__).parents[2] / "docs/examples/image-publish"
        request = json.loads((root / f"pve-template-{chosen}-request.json").read_text())
    if invalid:
        request["target"]["tls_verify"] = False
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))
    inputs = {name: str(tmp_path / f"missing-{name}.json") for name in ("publish", "cleanup", "retire")}
    inputs[chosen] = str(request_path)
    entry = tmp_path / "environment.json"
    entry.write_text(json.dumps({"schema_version": 1, "environment": "check-action", "components": {
        "pve-template": {"inputs": inputs, "options": {} if action is None else {"action": action},
                         "files": {"api_ca": str(tmp_path / "missing-ca.pem")}}}}))
    selected = load_operation(entry, "pve-template", "check", None, SourceReader())
    assert set(selected.documents) == {chosen}
    assert not selected.files
    reports = []
    execution = SimpleNamespace(finish=reports.append)
    monkeypatch.setattr(runtime, "_client", lambda *args: pytest.fail("check must remain offline"))
    monkeypatch.setattr(runtime, "_delete_action", lambda *args: pytest.fail("check must not delete resources"))
    if invalid:
        with pytest.raises(ValidationError):
            runtime.run(selected, "check", "cohe", execution, image_digest="")
        assert reports == []
    else:
        runtime.run(selected, "check", "cohe", execution, image_digest="")
        validator = {"publish": runtime.validate_publish_request,
                     "cleanup": runtime.validate_cleanup_request,
                     "retire": runtime.validate_retire_request}[chosen]
        assert reports[0]["action"] == chosen
        assert reports[0]["request_digest"] == runtime.canonical_digest(validator(request))
        assert reports[0]["network"] is False
        assert reports[0]["state"] is False
    effects = operation_for("pve-template", "check")
    assert not effects.network and not effects.infrastructure_write and not effects.state


def test_check_rejects_unknown_action_without_publish_fallback():
    selected = SimpleNamespace(options={"action": "unknown"}, documents={"publish": publish_request()})
    with pytest.raises(ValidationError, match="check action must be publish, cleanup or retire"):
        runtime.run(selected, "check", "cohe", SimpleNamespace(), image_digest="")


@pytest.mark.parametrize("action", ["cleanup", "retire"])
@pytest.mark.parametrize("wrong_kind", [False, True])
def test_check_never_substitutes_publish_for_action_input(action, wrong_kind):
    documents = {"publish": publish_request()}
    if wrong_kind:
        documents[action] = publish_request()
    selected = SimpleNamespace(options={"action": action}, documents=documents)
    with pytest.raises(ValidationError):
        runtime.run(selected, "check", "cohe", SimpleNamespace(), image_digest="")


def test_read_does_not_report_an_ordinary_vm_as_verified_template(tmp_path, monkeypatch):
    api = API()
    api.config["scsi0"] = "images:vm-9001-disk-0,size=8G"
    selected = SimpleNamespace(
        options={"template": {"target": publish_request()["target"], "vmid": 9001, "cluster_scope": "test-cluster"}}, documents={}
    )
    execution = SimpleNamespace(outputs=Outputs(tmp_path / "output"))
    monkeypatch.setattr(runtime, "_client", lambda *args: api)
    with pytest.raises(ValidationError, match="not a template"):
        runtime.run(selected, "read", "cohe", execution,
                    image_digest="registry.invalid/runtime@sha256:" + "a" * 64)
    assert not (execution.outputs.path("generated") / "template-record.json").exists()


def test_read_observes_existing_template_without_build_history(tmp_path, monkeypatch):
    import json

    api = API()
    api.created = True
    api.config.update(template=1, scsi0="images:base-9001-disk-0,size=8G")
    selected = SimpleNamespace(options={"template": {"target": publish_request()["target"], "vmid": 9001, "cluster_scope": "test-cluster"}})
    outputs = Outputs(tmp_path / "output")
    outputs.path("generated").mkdir()
    reports = []
    execution = SimpleNamespace(outputs=outputs, finish=reports.append)
    monkeypatch.setattr(runtime, "_client", lambda *args: api)
    runtime.run(selected, "read", "cohe", execution,
                image_digest="registry.invalid/runtime@sha256:" + "a" * 64)
    record = json.loads((outputs.path("generated") / "template-record.json").read_text())
    assert record["origin"] == "observation"
    assert record["artifact_digest"] == record["execution_id"] == "unknown"
    assert record["vmid"] == 9001
    assert reports[0]["status"] == "observed"
    assert all(method == "GET" for method, *_ in api.calls)


@pytest.mark.parametrize("operation", ["read", "plan"])
def test_observation_inputs_include_explicit_ca_file(tmp_path, operation):
    import json

    from iaas.runtime_config import SourceReader
    from iaas.runtime_execution.selection import load_operation

    ca = tmp_path / "ca.pem"
    ca.write_text("public CA fixture")
    entry = tmp_path / "environment.json"
    entry.write_text(json.dumps({"schema_version": 1, "environment": "ca-check", "components": {
        "pve-template": {"files": {"api_ca": str(ca)}}}}))
    selected = load_operation(entry, "pve-template", operation, None, SourceReader())
    assert selected.files["api_ca"] == ca


@pytest.mark.parametrize("mismatch", [False, True])
def test_verify_consumes_bound_publisher_output_without_network(tmp_path, monkeypatch, mismatch):
    import json

    from test_pve_template_publication_failures import publish_setup

    request, preview, execution = publish_setup(tmp_path, monkeypatch, API())
    result = runtime._publish(SimpleNamespace(), execution, request, preview, "publish-1")
    if mismatch:
        result["preview_digest"] = "sha256:" + "0" * 64
    result_path, preview_path = tmp_path / "result.json", tmp_path / "preview.json"
    result_path.write_text(json.dumps(result))
    preview_path.write_text(json.dumps(preview))
    selected = SimpleNamespace(options={}, files={"result": result_path, "preview": preview_path})
    reports = []
    execution.finish = reports.append
    monkeypatch.setattr(runtime, "_client", lambda *args: pytest.fail("verify must remain offline"))
    if mismatch:
        with pytest.raises(ValidationError, match="not bound"):
            runtime.run(selected, "verify", "cohe", execution, image_digest=preview["runtime"]["image_digest"])
    else:
        runtime.run(selected, "verify", "cohe", execution, image_digest=preview["runtime"]["image_digest"])
        assert reports[0]["status"] == "verified"


def test_read_original_journal_keeps_unknown_history_without_api(tmp_path, monkeypatch):
    import json

    journal = tmp_path / "publish-intent.json"
    journal.write_text(json.dumps({"kind": "pve-template-publish-intent", "schema_version": 1,
                                   "execution_id": "interrupted-1", "status": "unknown",
                                   "target": {"node": "cohe"}, "events": []}))
    selected = SimpleNamespace(options={}, files={"journal": journal})
    outputs = Outputs(tmp_path / "output")
    outputs.path("generated").mkdir()
    reports = []
    execution = SimpleNamespace(outputs=outputs, finish=reports.append)
    monkeypatch.setattr(runtime, "_client", lambda *args: pytest.fail("journal read must not call PVE"))
    runtime.run(selected, "read", "cohe", execution, image_digest="runtime@sha256:" + "a" * 64)
    assert reports[0]["native_status"] == "unknown"
    assert reports[0]["status"] == "recorded"
