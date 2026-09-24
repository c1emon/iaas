from types import SimpleNamespace

import pytest

from iaas.common.errors import ValidationError
from iaas.pve_template import runtime

from test_image_publish_contracts import request as publish_request
from test_pve_template_publisher import API, Outputs


def test_read_does_not_report_an_ordinary_vm_as_verified_template(tmp_path, monkeypatch):
    api = API()
    api.config["scsi0"] = "images:vm-9001-disk-0,size=8G"
    selected = SimpleNamespace(
        options={"template": {"target": publish_request()["target"], "vmid": 9001}}, documents={}
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
    api.config.update(template=1, scsi0="images:base-9001-disk-0,size=8G")
    selected = SimpleNamespace(options={"template": {"target": publish_request()["target"], "vmid": 9001}})
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
