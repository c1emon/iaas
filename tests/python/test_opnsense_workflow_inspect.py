from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests
import yaml

from iaas.common.errors import ValidationError
from iaas.opnsense_workflow.confirmation import response_warnings
from iaas.opnsense_workflow.contracts import save as save_candidate
from iaas.opnsense_workflow.inspect import inspect_candidate, main
from iaas.opnsense_workflow.reader import FixedCollectionTransport, Reader
from test_opnsense_workflow import Appliance, TARGET, alias, candidate, documents


ROOT = Path(__file__).parents[2]
CANDIDATE = ROOT / "docs/examples/opnsense-workflow/candidate.json"


class FakeReader:
    instances: list["FakeReader"] = []

    def __init__(self, target, credentials):
        self.target = target
        self.credentials = credentials
        self.calls = []
        self.closed = False
        self.__class__.instances.append(self)

    def active_check(self, resource, identity, desired):
        self.calls.append((resource, identity, desired))
        return RESULTS[resource]

    def close(self):
        self.closed = True


RESULTS = {
    "aliases": {"status": "verified", "reason": "current"},
    "dnat": {"status": "not_applicable", "reason": "no_consumer"},
}


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    candidate = tmp_path / "candidate.json"
    candidate_value = json.loads(CANDIDATE.read_text())
    for stage in candidate_value["stages"]:
        confirmation = stage["confirmation"]
        confirmation["rule"] = f"opnsense-provider-response-{stage['resource']}-v2"
        confirmation["required_evidence"] = ["native_response", "configuration_readback"]
        confirmation["supplementary_checks"] = []
        confirmation["warnings"] = response_warnings(stage["resource"])
        confirmation.pop("wait", None)
    candidate.write_text(json.dumps(candidate_value, indent=2) + "\n")
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({
        "all": {"children": {"opnsense": {"hosts": {
            "firewall": {"opnsense_api_host": "https://192.0.2.1", "opnsense_ssl_verify": True},
        }}}},
    }))
    return inventory, candidate, tmp_path / "inspection.json"


def test_inspection_writes_current_state_report_without_credentials(tmp_path):
    FakeReader.instances.clear()
    inventory, candidate, output = _inputs(tmp_path)

    report, exit_code = inspect_candidate(
        inventory, candidate, output, reader_factory=FakeReader,
        environment={"OPNSENSE_API_KEY": "secret-key", "OPNSENSE_API_SECRET": "secret-secret"},
    )

    assert exit_code == 0
    assert report["scope"] == "advanced_current_state"
    assert report["action_proof"] == "not_proven"
    assert report["business_proof"] == "not_proven"
    assert report["status"] == "matched"
    assert output.stat().st_mode & 0o777 == 0o600
    text = output.read_text()
    assert "secret-key" not in text and "secret-secret" not in text
    assert len(FakeReader.instances) == 1
    assert len(FakeReader.instances[0].calls) == 2
    assert FakeReader.instances[0].closed


@pytest.mark.parametrize(
    ("status", "expected_exit", "expected_report"),
    [("failed", 1, "failed"), ("unknown", 2, "unknown"),
     ("unsupported", 2, "unknown"), ("incomplete", 2, "unknown")],
)
def test_inspection_exit_codes_keep_non_success_observation(status, expected_exit, expected_report, tmp_path):
    inventory, candidate, output = _inputs(tmp_path)
    RESULTS["aliases"] = {"status": status, "reason": "test"}

    report, exit_code = inspect_candidate(inventory, candidate, output, reader_factory=FakeReader)

    assert exit_code == expected_exit
    assert report["status"] == expected_report
    assert report["objects"][0]["observation"]["status"] == status


def test_inspection_rejects_existing_output_before_reading(tmp_path):
    inventory, candidate, output = _inputs(tmp_path)
    output.write_text("keep")

    with pytest.raises(ValidationError, match="already exists"):
        inspect_candidate(inventory, candidate, output, reader_factory=FakeReader)
    assert output.read_text() == "keep"


def test_inspection_preserves_existing_output_parent_mode(tmp_path):
    inventory, candidate, _ = _inputs(tmp_path)
    RESULTS["aliases"] = {"status": "verified", "reason": "current"}
    parent = tmp_path / "existing-output"
    parent.mkdir()
    parent.chmod(0o755)

    inspect_candidate(inventory, candidate, parent / "inspection.json", reader_factory=FakeReader)

    assert parent.stat().st_mode & 0o777 == 0o755


def test_inspection_normalizes_bad_status_and_ignores_close_error(tmp_path):
    inventory, candidate, output = _inputs(tmp_path)

    class BrokenClose(FakeReader):
        def active_check(self, resource, identity, desired):
            return {"status": 123, "reason": "bad fake status"}

        def close(self):
            raise RuntimeError("close failed")

    report, exit_code = inspect_candidate(inventory, candidate, output, reader_factory=BrokenClose)

    assert exit_code == 2
    assert report["status"] == "unknown"
    assert report["objects"][0]["observation"]["status"] == "unknown"
    assert report["objects"][0]["observation"]["reason"] == "malformed_active_observation_status"


def test_cli_only_prints_non_secret_summary(tmp_path, capsys):
    inventory, candidate, output = _inputs(tmp_path)
    RESULTS["aliases"] = {"status": "verified", "reason": "current"}

    assert main(["--inventory", str(inventory), "--candidate", str(candidate), "--output", str(output)],
                reader_factory=FakeReader,
                environment={"OPNSENSE_API_KEY": "secret-key", "OPNSENSE_API_SECRET": "secret-secret"}) == 0
    stdout = capsys.readouterr().out
    assert "secret-key" not in stdout and "secret-secret" not in stdout
    assert json.loads(stdout)["status"] == "matched"


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.content = json.dumps(payload or {}).encode()

    def iter_content(self, chunk_size):
        return [self.content]

    def close(self):
        pass


class _HttpSession:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        path = url.split("/api/", 1)[-1]
        self.calls.append((method, path))
        if self.behavior == "timeout":
            raise requests.Timeout("synthetic timeout")
        if self.behavior == "forbidden":
            return _Response(403)
        if callable(self.behavior):
            return self.behavior(method, path)
        raise AssertionError(f"unknown synthetic behavior: {self.behavior}")

    def close(self):
        self.closed = True


GATEWAY = {
    "name": "WAN", "interface": "wan", "ip_protocol": "inet", "gateway": "192.0.2.1",
    "default_gw": False, "far_gw": False, "monitor_disable": False, "monitor_noroute": False,
    "monitor": "192.0.2.1", "force_down": False, "latency_low": 200, "latency_high": 500,
    "loss_low": 10, "loss_high": 20, "interval": 1, "time_period": 60, "loss_interval": 4,
    "data_length": 1, "priority": 255, "weight": 1, "description": "synthetic",
    "state": "present",
}


def _real_inputs(tmp_path, docs):
    candidate_path = tmp_path / "candidate.json"
    save_candidate(candidate_path, candidate(Appliance(), docs))
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({
        "all": {"children": {"opnsense": {"hosts": {
            TARGET["host"]: {"opnsense_api_host": TARGET["endpoint"],
                              "opnsense_ssl_verify": TARGET["ssl_verify"]},
        }}}},
    }))
    return inventory, candidate_path, tmp_path / "inspection.json"


def _real_reader_factory(session):
    def factory(target, credentials):
        transport = FixedCollectionTransport(target, credentials, session=session)
        return Reader(target, credentials, transport=transport)
    return factory


@pytest.mark.parametrize("behavior", ["timeout", "forbidden"])
def test_real_reader_transport_unavailable_is_unknown(tmp_path, behavior):
    inventory, candidate_path, output = _real_inputs(
        tmp_path, documents(aliases=[alias("A")], gateways=[GATEWAY])
    )
    session = _HttpSession(behavior)

    report, exit_code = inspect_candidate(
        inventory, candidate_path, output,
        reader_factory=_real_reader_factory(session),
        environment={"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"},
    )

    assert exit_code == 2
    assert report["status"] == "unknown"
    assert [row["observation"]["status"] for row in report["objects"]] == ["unknown", "unknown"]
    assert session.closed


def test_real_reader_alias_membership_mismatch_is_failed(tmp_path):
    def mismatch(method, path):
        assert method == "POST"
        assert path == "firewall/alias_util/list/A"
        return _Response(200, {"rows": [{"ip": "192.0.2.2"}], "total": 1})

    inventory, candidate_path, output = _real_inputs(tmp_path, documents(aliases=[alias("A")]))
    report, exit_code = inspect_candidate(
        inventory, candidate_path, output,
        reader_factory=_real_reader_factory(_HttpSession(mismatch)),
        environment={"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"},
    )

    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["objects"][0]["observation"]["status"] == "failed"
    assert report["objects"][0]["observation"]["reason"] == "alias_table_membership_mismatch"


def test_real_reader_mismatch_and_unknown_preserve_each_fact(tmp_path):
    def mixed(method, path):
        if path == "firewall/alias_util/list/A":
            return _Response(200, {"rows": [{"ip": "192.0.2.2"}], "total": 1})
        if path == "core/firmware/status":
            raise requests.Timeout("synthetic gateway timeout")
        raise AssertionError(path)

    inventory, candidate_path, output = _real_inputs(
        tmp_path, documents(aliases=[alias("A")], gateways=[GATEWAY])
    )
    report, exit_code = inspect_candidate(
        inventory, candidate_path, output,
        reader_factory=_real_reader_factory(_HttpSession(mixed)),
        environment={"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"},
    )

    assert exit_code == 1
    assert report["status"] == "failed"
    assert [row["observation"]["status"] for row in report["objects"]] == ["failed", "unknown"]
    assert report["objects"][0]["observation"]["reason"] == "alias_table_membership_mismatch"
    assert report["objects"][1]["observation"]["reason"] == "timeout"


@pytest.mark.parametrize(
    ("desired", "first_path"),
    [
        pytest.param(alias("PORTS", ["443"], type="port"), "core/firmware/status", id="port-alias"),
        pytest.param(alias("OLD", state="absent"), "firewall/alias_util/aliases", id="absent-alias"),
    ],
)
def test_real_reader_unsupported_endpoint_is_preserved_for_port_and_absent_alias(
    tmp_path, desired, first_path
):
    def firmware_then_unavailable(method, path):
        if path == "core/firmware/status":
            return _Response(200, {"product": {"product_version": "26.7.3"}})
        return _Response(404)

    inventory, candidate_path, output = _real_inputs(
        tmp_path, documents(aliases=[desired])
    )
    session = _HttpSession(firmware_then_unavailable)

    report, exit_code = inspect_candidate(
        inventory, candidate_path, output,
        reader_factory=_real_reader_factory(session),
        environment={"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"},
    )

    assert exit_code == 2
    assert report["status"] == "unknown"
    observation = report["objects"][0]["observation"]
    assert observation["status"] == "unsupported"
    assert observation["reason"] == "endpoint_unavailable"
    assert session.calls[0] == ("GET", first_path)
    assert session.closed
