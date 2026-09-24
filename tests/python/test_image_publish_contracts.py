from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from iaas.common.errors import ValidationError
from iaas.image.contracts import canonical_digest as image_canonical_digest
from iaas.pve_template.contracts import (
    build_action_preview,
    build_publish_preview,
    canonical_digest,
    validate_cleanup_request,
    validate_publish_preview,
    validate_publish_request,
    validate_retire_request,
    validate_template_record_v2,
)
from iaas.runtime_execution.pve_contracts import validate_execution_admission


def artifact() -> dict:
    return {
        "kind": "image-artifact", "schema_version": 1, "artifact_id": "external-1", "version": "v1",
        "disk": {"path": "disk.qcow2", "format": "qcow2", "sha256": "b" * 64,
                  "size_bytes": 1024, "virtual_size_bytes": 8 * 1024 ** 3, "self_contained": True},
        "guest": {"architecture": "amd64", "firmware": "bios", "cloud_init": "unknown", "guest_agent": "unknown"},
        "build": {"origin": "external"},
        "checks": [{"id": "format", "scope": "static", "status": "passed", "evidence_ref": None}],
    }


def request() -> dict:
    value = {"kind": "pve-template-publish-request", "schema_version": 1, "artifact": artifact(),
             "source": {"object_ref": "https://objects.example.invalid/disk.qcow2", "object_version": "v1"},
             "target": {"api_endpoint": "https://pve.example.invalid:8006", "node": "cohe", "tls_verify": True},
             "vmid": 9001, "version": "v1", "name": "debian-template", "staging_storage": "images",
             "disk_storage": "images", "cloud_init_storage": "images",
             "hardware": {"cpus": 2, "memory_mib": 2048, "machine": "q35", "scsi_controller": "virtio-scsi-single",
                           "boot_disk": "scsi0", "bridge": "vmbr0", "firmware": "bios"},
             "cloud_init_defaults": {"user": "debian"},
             "requirements": {"required": [{"id": "format", "scope": "static"}], "optional": [],
                              "native_template_config_verify": True, "guest_acceptance_scope": "caller"},
             "transport": "controller-upload"}
    value["artifact_digest"] = canonical_digest(value["artifact"])
    return value


def image_test_result(*, disk_sha256: str = "b" * 64, status: str = "passed") -> dict:
    policy = {"required": [{"id": "format", "scope": "static"}], "optional": []}
    return {
        "kind": "image-test-result", "schema_version": 1, "execution_id": "test-1",
        "component": "image", "operation": "test", "runtime_digest": "runtime@sha256:" + "a" * 64,
        "input_digest": "sha256:" + "c" * 64, "phase": "succeeded", "status": "succeeded",
        "effects": {"guest": "known", "source": "none"},
        "verification": [], "collection": {"status": "succeeded"}, "disk_sha256": disk_sha256,
        "test_config_digest": image_canonical_digest(policy),
        "checks": [{"id": "format", "scope": "static", "status": status, "evidence_ref": None}],
        "base_unchanged": True, "cleanup": {"status": "succeeded", "residue": []},
    }


def test_publish_preview_is_canonically_bound() -> None:
    preview = build_publish_preview(request(), runtime={"image_digest": "registry.invalid/runtime@sha256:" + "a" * 64},
                                    observed={"vmid_free": True})
    assert validate_publish_preview(copy.deepcopy(preview))["schema_version"] == 2
    formatted = copy.deepcopy(preview)
    formatted["fixed_input"] = {key: formatted["fixed_input"][key] for key in reversed(formatted["fixed_input"])}
    assert validate_publish_preview(formatted)["preview_digest"] == preview["preview_digest"]


def test_publish_rejects_private_endpoint_and_force_replacement() -> None:
    bad = request()
    bad["target"]["api_endpoint"] = "https://user:secret@pve.example.invalid:8006"
    with pytest.raises(ValidationError):
        validate_publish_request(bad)
    bad = request()
    bad["force"] = True
    with pytest.raises(ValidationError):
        validate_publish_request(bad)


def test_publish_rejects_unsupported_hostname_default() -> None:
    bad = request()
    bad["cloud_init_defaults"]["hostname"] = "template"
    with pytest.raises(ValidationError, match="unsupported fields"):
        validate_publish_request(bad)


def test_template_record_v2_requires_configuration_verification() -> None:
    record = {"kind": "pve-template-record", "schema_version": 2, "record_id": "v1-9001",
              "target": request()["target"], "node": "cohe", "vmid": 9001, "smbios_uuid": "uuid-1",
              "volumes": {"scsi0": "images:vm-9001-disk-0"}, "configuration": {"template": 1},
              "origin": "publication", "execution_id": "publish-1", "artifact_digest": "sha256:" + "b" * 64,
              "verification": {"template_config": "failed"}}
    with pytest.raises(ValidationError):
        validate_template_record_v2(record)


def test_publish_accepts_matching_test_for_unknown_artifact_check() -> None:
    value = request()
    value["artifact"]["checks"][0]["status"] = "unknown"
    value["test_results"] = [image_test_result()]
    value["artifact_digest"] = canonical_digest(value["artifact"])
    normalized = validate_publish_request(value)
    assert normalized["test_results"][0]["disk_sha256"] == "b" * 64


def test_publish_rejects_missing_or_conflicting_required_evidence() -> None:
    value = request()
    value["artifact"]["checks"][0]["status"] = "unknown"
    value["artifact_digest"] = canonical_digest(value["artifact"])
    with pytest.raises(ValidationError, match="lacks passed evidence"):
        validate_publish_request(value)

    value["test_results"] = [image_test_result(status="passed")]
    value["artifact"]["checks"][0]["status"] = "failed"
    value["artifact_digest"] = canonical_digest(value["artifact"])
    with pytest.raises(ValidationError, match="override failed"):
        validate_publish_request(value)


def test_publish_rejects_test_for_another_disk() -> None:
    value = request()
    value["artifact"]["checks"][0]["status"] = "unknown"
    value["test_results"] = [image_test_result(disk_sha256="c" * 64)]
    value["artifact_digest"] = canonical_digest(value["artifact"])
    with pytest.raises(ValidationError, match="different disk"):
        validate_publish_request(value)


def test_cleanup_and_retire_examples_bind_preview_and_admission() -> None:
    root = Path(__file__).parents[2] / "docs" / "examples" / "image-publish"
    runtime = {"image_digest": "runtime@sha256:" + "a" * 64}
    for action, validator in (("cleanup", validate_cleanup_request), ("retire", validate_retire_request)):
        value = json.loads((root / f"pve-template-{action}-request.json").read_text())
        normalized = validator(value)
        preview = build_action_preview(normalized, action=action, runtime=runtime,
                                       observed={"activity": "unobserved"})
        assert validate_publish_preview(copy.deepcopy(preview))["preview_digest"] == preview["preview_digest"]
        admission = {
            "schema_version": 1, "execution_id": f"{action}-example-apply",
            "plan_digest": preview["preview_digest"].removeprefix("sha256:"),
            "target": normalized["target"], "approved": True,
            "consumption": {"reserved": True, "reservation_id": f"{action}-reservation"},
            "pending": {"record_id": f"{action}-pending"},
            "serialization": {"held": True, "context_id": f"{action}-lock"},
        }
        validate_execution_admission(admission, digest=admission["plan_digest"],
                                     execution_id=admission["execution_id"], target=normalized["target"])


def test_cleanup_rejects_duplicate_vm_and_volume_selectors() -> None:
    root = Path(__file__).parents[2] / "docs" / "examples" / "image-publish"
    value = json.loads((root / "pve-template-cleanup-request.json").read_text())
    value["objects"] = [{"vmid": 9001, "smbios_uuid": "uuid-1", "volumes": {}}] * 2
    with pytest.raises(ValidationError, match="duplicate VM selectors"):
        validate_cleanup_request(value)
    value = json.loads((root / "pve-template-cleanup-request.json").read_text())
    volume = {"storage": "images", "volid": "images:import/publish-example-1.qcow2"}
    value["volumes"] = [volume, volume.copy()]
    with pytest.raises(ValidationError, match="duplicate selectors"):
        validate_cleanup_request(value)
