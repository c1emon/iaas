"""Focused offline contracts for PVE lifecycle admission and state reads."""

from __future__ import annotations

import json

import pytest

from iaas.common.errors import ValidationError
from iaas.runtime_execution.pve_contracts import (
    validate_execution_admission,
    validate_plan_metadata,
    validate_result,
)
from iaas.runtime_execution.pve_state import S3StateObserver, admit_state, extract_state_vmids
from iaas.runtime_execution.state import S3Backend


DIGEST = "a" * 64
TARGET = {
    "api_endpoint": "https://pve.example.invalid:8006",
    "insecure": False,
    "storage_id": "images",
    "ssh_host": "node.example.invalid",
    "ssh_user": "pve-ops",
    "ssh_port": 2222,
}
BACKEND = {
    "bucket": "state",
    "key": "root.tfstate",
    "region": "us-east-1",
    "endpoint": "https://s3.example.invalid",
    "tls_verify": True,
    "path_style": True,
    "use_lockfile": True,
}


def _verification() -> dict:
    return {"requirements": [
        {"category": "configuration", "scope": "changed_objects", "required": True, "responsibility": "iaas"},
        {"category": "guest", "scope": "caller", "required": False, "responsibility": "caller"},
    ]}


def _admission() -> dict:
    return {
        "schema_version": 1,
        "execution_id": "exec-1",
        "plan_digest": DIGEST,
        "target": TARGET,
        "approved": True,
        "consumption": {"reserved": True, "reservation_id": "consume-1"},
        "pending": {"record_id": "pending-1"},
        "serialization": {"held": True, "context_id": "lock-1"},
    }


def _metadata() -> dict:
    return {
        "schema_version": 2,
        "plan_digest": DIGEST,
        "target": TARGET,
        "root_id": "root-1",
        "backend": BACKEND,
        "workspace": "default",
        "runtime": "linux/arm64",
        "state_admission": {"schema_version": 1, "root_id": "root-1", "backend": BACKEND,
                             "workspace": "default", "mode": "first_use", "initialization_ref": "init-1"},
        "verification_requirements": _verification(),
    }


def test_contracts_reject_old_metadata_missing_consumption_and_missing_verification() -> None:
    with pytest.raises(ValidationError, match="unsupported PVE plan metadata"):
        validate_plan_metadata({**_metadata(), "schema_version": 1})
    with pytest.raises(ValidationError, match="durable consumption"):
        validate_execution_admission({**_admission(), "consumption": {"reserved": False, "reservation_id": "x"}})
    with pytest.raises(ValidationError, match="configuration"):
        validate_result({
            "schema_version": 1, "target": TARGET, "plan_digest": DIGEST, "execution_id": "exec-1", "runtime": "local",
            "phase": "succeeded", "effects": {"facility": "none", "state": "none", "collection": "known"},
            "native_execution": {"status": "passed"}, "state_persistence": {"status": "passed"},
            "verification": {"status": "passed"}, "collection": {"status": "passed"},
            "verification_requirements": {"requirements": []},
        })


def test_execution_admission_binds_identity() -> None:
    checked = validate_execution_admission(_admission(), digest=DIGEST, target=TARGET, execution_id="exec-1")
    assert checked["execution_id"] == "exec-1"
    with pytest.raises(ValidationError, match="identity"):
        validate_execution_admission(_admission(), execution_id="other")


class _GetOnlyS3:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict] = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps(self.payload).encode()


class _S3Error(RuntimeError):
    def __init__(self, code: str):
        self.code = code


def test_state_observer_uses_workspace_key_without_writes_and_extracts_native_vm_ids() -> None:
    backend = S3Backend({**BACKEND, "workspace_key_prefix": "env:"}, "review")
    transport = _GetOnlyS3({
        "version": 4, "terraform_version": "1.12.6", "serial": 4, "lineage": "native-lineage",
        "resources": [{"instances": [{"attributes": {"vm_id": 500}}]}],
    })
    observation = S3StateObserver(transport).observe(backend)
    assert observation.status == "present"
    assert observation.key == "env:/review/root.tfstate"
    assert extract_state_vmids(observation) == {500}
    assert transport.calls[0]["key"] == observation.key
    assert set(transport.calls[0]) == {"bucket", "key", "region", "endpoint", "config"}


@pytest.mark.parametrize(("code", "status", "reason"), [("NoSuchKey", "absent", "missing_object"),
                                                              ("NoSuchBucket", "error", "observation_error"),
                                                              ("AccessDenied", "error", "access_denied")])
def test_state_observer_distinguishes_confirmed_missing_object_from_backend_errors(code: str, status: str, reason: str) -> None:
    class ErrorTransport:
        def get_object(self, **_kwargs):
            raise _S3Error(code)

    backend = S3Backend(BACKEND, "default")
    observation = S3StateObserver(ErrorTransport()).observe(backend)
    assert observation.status == status
    assert observation.reason == reason


def test_existing_state_requires_lineage_and_full_backend_identity() -> None:
    backend = S3Backend(BACKEND, "default")
    transport = _GetOnlyS3({"version": 4, "serial": 1, "lineage": "lineage-1", "resources": []})
    observation = S3StateObserver(transport).observe(backend)
    admission = {"schema_version": 1, "root_id": "root-1", "backend": backend.identity(), "workspace": "default",
                 "mode": "existing", "lineage": "lineage-1"}
    assert admit_state(backend, admission, observation)["lineage"] == "lineage-1"
    with pytest.raises(ValidationError, match="lineage"):
        admit_state(backend, {**admission, "lineage": "other"}, observation)
