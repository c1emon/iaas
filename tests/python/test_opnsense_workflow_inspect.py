from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_workflow.confirmation import response_warnings
from iaas_automation.opnsense_workflow.inspect import inspect_candidate, main


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
