"""Pure contracts for the PVE template helper.

The module deliberately contains no SSH, PVE or S3 access.  It is shared by
offline recipe checks and the online runtime so that a plan cannot silently
change the inputs consumed by an apply.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.image.contracts import canonical_digest as image_canonical_digest
from iaas_automation.image.contracts import validate_artifact, validate_test_result


IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

BUILD_FIELDS = {
    "schema_version", "action", "recipe", "target", "vmid", "version",
    "image_url", "image_url_prefix", "image_sha512", "import_storage",
    "disk_storage", "build_bridge", "build_domain", "apt_mirror",
    "apt_security_mirror", "timezone", "locale", "ciuser", "nameserver",
}
TARGET_FIELDS = {"node", "host", "endpoint", "api_endpoint", "insecure", "tls_verify", "ssh_user", "ssh_port"}
RECORD_TARGET_FIELDS = TARGET_FIELDS | {"storage_id", "ssh_host"}
RUNTIME_DIGEST = re.compile(r"^(?:[^@/\s]+(?:/[^@\s]+)*)?@?sha256:[0-9a-fA-F]{64}$")

# v2 publication contracts.  The old node-build constants remain private
# implementation history while the runtime accepts only these new functions.
PUBLISH_PREVIEW_VERSION = 2
TEMPLATE_RECORD_VERSION = 2
PUBLISH_REQUEST_VERSION = 1
PUBLISH_FIELDS = {
    "kind", "schema_version", "artifact", "artifact_digest", "test_results", "source", "target",
    "vmid", "version", "name", "staging_storage", "disk_storage", "cloud_init_storage", "efi_storage",
    "hardware", "cloud_init_defaults", "requirements", "transport",
}
PUBLISH_TARGET_FIELDS = {"api_endpoint", "node", "tls_verify"}
PUBLISH_HARDWARE_FIELDS = {"cpus", "memory_mib", "machine", "scsi_controller", "boot_disk", "bridge", "firmware"}


def _mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, Mapping), f"{label} must be a mapping")
    require(all(isinstance(key, str) for key in value), f"{label} keys must be strings")
    return dict(value)


def _text(value: Any, label: str, *, pattern: re.Pattern[str] | None = None) -> str:
    require(isinstance(value, str) and bool(value) and "\x00" not in value, f"{label} must be a nonempty string")
    if pattern is not None:
        require(pattern.fullmatch(value) is not None, f"{label} has an invalid format")
    return value


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if type(value) is int:
        return value
    if isinstance(value, float):
        raise ValueError("floating point values are not supported by the contract")
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        require(all(isinstance(key, str) for key in value), "canonical object keys must be strings")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    raise ValueError("unsupported value in canonical JSON")


def canonical_digest(value: Mapping[str, Any]) -> str:
    """Return the digest used to bind a preview, request, and receipt."""
    payload = json.dumps(_canonical_value(value), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _publish_url(value: Any, label: str) -> str:
    result = _text(value, label)
    parsed = urlsplit(result)
    require(parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password and
            not parsed.query and not parsed.fragment, f"{label} must be a fixed HTTPS URL without credentials")
    return result.rstrip("/")


def _source_ref(value: Any, label: str) -> str:
    result = _text(value, label)
    parsed = urlsplit(result)
    if parsed.scheme == "s3":
        require(parsed.netloc and parsed.path not in {"", "/"} and
                not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
                f"{label} must be a stable credential-free s3 object reference")
        return result.rstrip("/")
    return _publish_url(result, label)


def _publish_storage(value: Any, label: str) -> str:
    result = _text(value, label, pattern=IDENTIFIER)
    require(":" not in result and "/" not in result, f"{label} must be a storage identifier")
    return result


def validate_publish_request(value: Any) -> dict[str, Any]:
    """Normalize the controller-upload PVE publication request."""
    request = _mapping(value, "pve template publish request")
    require(set(request) <= PUBLISH_FIELDS and request.get("kind") == "pve-template-publish-request" and
            type(request.get("schema_version")) is int and request.get("schema_version") == PUBLISH_REQUEST_VERSION,
            "unsupported pve template publish request")
    required = {"artifact", "artifact_digest", "source", "target", "vmid", "version", "name",
                "staging_storage", "disk_storage", "cloud_init_storage", "hardware", "cloud_init_defaults",
                "requirements", "transport"}
    require(required <= request.keys(), "pve template publish request is incomplete")
    artifact = validate_artifact(_mapping(request["artifact"], "publish artifact"))
    digest = _text(request["artifact_digest"], "artifact_digest")
    require(SHA256.fullmatch(digest.removeprefix("sha256:")) is not None and
            canonical_digest(artifact) == digest, "artifact_digest does not match canonical artifact")
    source = _mapping(request["source"], "publish source")
    require(set(source) <= {"object_ref", "object_version"} and "object_ref" in source,
            "publish source is invalid")
    normalized_source = {"object_ref": _source_ref(source["object_ref"], "source.object_ref")}
    if "object_version" in source:
        normalized_source["object_version"] = _text(source["object_version"], "source.object_version", pattern=IDENTIFIER)
    target = _mapping(request["target"], "publish target")
    require(set(target) == PUBLISH_TARGET_FIELDS, "publish target must contain api_endpoint, node and tls_verify")
    normalized_target = {"api_endpoint": _publish_url(target["api_endpoint"], "target.api_endpoint"),
                         "node": _text(target["node"], "target.node", pattern=IDENTIFIER),
                         "tls_verify": target["tls_verify"]}
    require(target["tls_verify"] is True, "publish target tls_verify must be true")
    vmid = request["vmid"]
    require(type(vmid) is int and 100 <= vmid <= 999_999_999, "publish vmid is invalid")
    version = _text(request["version"], "publish version", pattern=IDENTIFIER)
    name = _text(request["name"], "publish name", pattern=IDENTIFIER)
    hardware = _mapping(request["hardware"], "publish hardware")
    require(set(hardware) == PUBLISH_HARDWARE_FIELDS, "publish hardware is incomplete")
    for field in ("cpus", "memory_mib"):
        require(type(hardware[field]) is int and hardware[field] > 0, f"hardware.{field} must be positive")
    for field in ("machine", "scsi_controller", "boot_disk", "bridge", "firmware"):
        _text(hardware[field], f"hardware.{field}", pattern=IDENTIFIER)
    require(hardware["firmware"] in {"bios", "uefi"}, "hardware.firmware is invalid")
    storages = {"staging_storage": _publish_storage(request["staging_storage"], "staging_storage"),
                "disk_storage": _publish_storage(request["disk_storage"], "disk_storage"),
                "cloud_init_storage": _publish_storage(request["cloud_init_storage"], "cloud_init_storage")}
    if "efi_storage" in request:
        storages["efi_storage"] = _publish_storage(request["efi_storage"], "efi_storage")
    if hardware["firmware"] == "uefi":
        require("efi_storage" in storages, "uefi publication requires efi_storage")
    defaults = _mapping(request["cloud_init_defaults"], "cloud_init_defaults")
    require(not set(defaults) - {"user", "hostname", "ssh_keys", "ip_config"},
            "cloud_init_defaults contains unsupported fields")
    for field in ("user", "hostname", "ip_config"):
        if field in defaults:
            _text(defaults[field], f"cloud_init_defaults.{field}")
    if "ssh_keys" in defaults:
        require(isinstance(defaults["ssh_keys"], list) and
                all(isinstance(item, str) and item for item in defaults["ssh_keys"]),
                "cloud_init_defaults.ssh_keys must contain nonempty strings")
    requirements = _mapping(request["requirements"], "requirements")
    require(set(requirements) <= {"required", "optional", "native_template_config_verify", "guest_acceptance_scope"},
            "requirements contains unsupported fields")
    def normalize_checks(value: Any, label: str) -> list[dict[str, str]]:
        require(isinstance(value, list), f"requirements.{label} must be a list")
        rows = []
        seen: set[str] = set()
        for item in value:
            row = _mapping(item, f"requirements.{label} item")
            require(set(row) == {"id", "scope"}, f"requirements.{label} item must contain id and scope")
            check_id = _text(row["id"], f"requirements.{label}.id", pattern=IDENTIFIER)
            require(check_id not in seen, f"requirements.{label} contains duplicate check id")
            seen.add(check_id)
            rows.append({"id": check_id, "scope": _text(row["scope"], f"requirements.{label}.scope", pattern=IDENTIFIER)})
        return rows
    required_checks = normalize_checks(requirements.get("required", []), "required")
    optional_checks = normalize_checks(requirements.get("optional", []), "optional")
    require({(row["id"], row["scope"]) for row in required_checks}.isdisjoint(
        {(row["id"], row["scope"]) for row in optional_checks}),
        "requirements required and optional selectors overlap")
    require(requirements.get("native_template_config_verify", True) is True,
            "native template configuration verification is mandatory")
    require(requirements.get("guest_acceptance_scope", "caller") == "caller",
            "guest acceptance remains caller-owned")
    normalized_requirements = {"required": required_checks, "optional": optional_checks,
                               "native_template_config_verify": True,
                               "guest_acceptance_scope": "caller"}
    require(request["transport"] == "controller-upload", "only controller-upload transport is supported")
    result = {"kind": "pve-template-publish-request", "schema_version": 1, "artifact": artifact,
              "artifact_digest": digest, "source": normalized_source, "target": normalized_target,
              "vmid": vmid, "version": version, "name": name, **storages, "hardware": dict(hardware),
              "cloud_init_defaults": dict(defaults), "requirements": normalized_requirements,
              "transport": "controller-upload", "test_results": []}
    if "test_results" in request:
        require(isinstance(request["test_results"], list), "test_results must be a list")
        result["test_results"] = [validate_test_result(_mapping(item, "test result"))
                                   for item in request["test_results"]]
    validate_publish_evidence(result)
    return result


def validate_publish_evidence(request: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve every required check before a publication can be planned.

    The artifact remains the authoritative history.  A selected test can add
    evidence for an absent, unknown, or not-performed artifact check, but it
    cannot override a failed observation.  Test results are bound to the
    exact disk and normalized check policy so a caller cannot silently select
    the latest result for a different image or policy.
    """
    artifact = _mapping(request.get("artifact"), "publish artifact")
    required = _mapping(request.get("requirements"), "requirements").get("required", [])
    optional = _mapping(request.get("requirements"), "requirements").get("optional", [])
    policy = {"required": list(required), "optional": list(optional)}
    policy_ids = {(row["id"], row["scope"]) for row in required + optional}
    artifact_rows = {(row["id"], row["scope"]): row for row in artifact["checks"]}
    selected_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in request.get("test_results", []):
        result = validate_test_result(raw)
        require(result["disk_sha256"] == artifact["disk"]["sha256"],
                "selected image test result is for a different disk")
        require(result["test_config_digest"] == image_canonical_digest(policy),
                "selected image test result policy does not match publication requirements")
        require(result["phase"] == "succeeded" and result["status"] == "succeeded" and
                result["base_unchanged"] is True and result["collection"]["status"] == "succeeded" and
                result["cleanup"]["status"] in {"succeeded", "not_required"},
                "selected image test result is not publishable evidence")
        for row in result["checks"]:
            key = (row["id"], row["scope"])
            require(key in policy_ids, "selected image test contains a check outside publication policy")
            selected_rows.setdefault(key, []).append(row)

    for selector in required:
        key = (selector["id"], selector["scope"])
        artifact_row = artifact_rows.get(key)
        artifact_status = artifact_row["status"] if artifact_row is not None else None
        candidates = selected_rows.get(key, [])
        statuses = {row["status"] for row in candidates}
        require(len(statuses) <= 1, "conflicting selected image test evidence cannot be resolved")
        selected_status = next(iter(statuses), None)
        if artifact_status == "failed":
            require(selected_status is None, "selected image test cannot override failed artifact evidence")
            raise ValidationError(f"required artifact check {selector['id']} failed")
        if artifact_status == "passed":
            require(selected_status in {None, "passed"},
                    "selected image test conflicts with passed artifact evidence")
        elif selected_status == "passed":
            artifact_status = "passed"
        require(artifact_status == "passed", f"required image check {selector['id']} lacks passed evidence")
    return {"required": [dict(row) for row in required], "optional": [dict(row) for row in optional]}


def build_publish_preview(request: Mapping[str, Any], *, runtime: Mapping[str, Any],
                          observed: Mapping[str, Any] | None = None) -> dict[str, Any]:
    fixed = validate_publish_request(request)
    runtime_value = _mapping(runtime, "publish runtime")
    image_digest = _text(runtime_value.get("image_digest"), "publish runtime.image_digest")
    require(RUNTIME_DIGEST.fullmatch(image_digest) is not None, "publish runtime image digest is invalid")
    body: dict[str, Any] = {"kind": "pve-template-preview", "schema_version": PUBLISH_PREVIEW_VERSION,
                            "action": "publish", "fixed_input": fixed,
                            "artifact_digest": fixed["artifact_digest"],
                            "disk_sha256": fixed["artifact"]["disk"]["sha256"],
                            "runtime": {"image_digest": image_digest},
                            "requirements": fixed["requirements"], "observed": dict(observed or {})}
    body["preview_digest"] = canonical_digest(body)
    return body


def validate_publish_preview(value: Any) -> dict[str, Any]:
    preview = _mapping(value, "pve template preview")
    require(preview.get("kind") == "pve-template-preview" and preview.get("schema_version") == PUBLISH_PREVIEW_VERSION and
            preview.get("action") in {"publish", "cleanup", "retire"}, "unsupported pve template preview")
    digest = _text(preview.get("preview_digest"), "preview_digest")
    require(SHA256.fullmatch(digest.removeprefix("sha256:")) is not None, "preview_digest is invalid")
    body = dict(preview)
    body.pop("preview_digest", None)
    require(canonical_digest(body) == digest, "preview_digest does not match normalized inputs")
    runtime = _mapping(preview.get("runtime"), "publish preview runtime")
    require(RUNTIME_DIGEST.fullmatch(_text(runtime.get("image_digest"), "runtime.image_digest")) is not None,
            "publish preview runtime is invalid")
    if preview["action"] == "publish":
        fixed = validate_publish_request(preview.get("fixed_input"))
        require(preview.get("artifact_digest") == fixed["artifact_digest"] and
                preview.get("disk_sha256") == fixed["artifact"]["disk"]["sha256"],
                "publish preview artifact binding is invalid")
    elif preview["action"] == "cleanup":
        validate_cleanup_request(preview.get("fixed_input"))
    else:
        validate_retire_request(preview.get("fixed_input"))
    return dict(preview)


def validate_template_record_v2(value: Any, *, complete: bool = True) -> dict[str, Any]:
    record = _mapping(value, "pve template record")
    required = {"kind", "schema_version", "record_id", "target", "node", "vmid", "smbios_uuid",
                "volumes", "configuration", "origin", "execution_id", "artifact_digest", "verification"}
    require(set(record) >= required, "pve-template-record/v2 is incomplete")
    require(record["kind"] == "pve-template-record" and type(record["schema_version"]) is int and
            record["schema_version"] == TEMPLATE_RECORD_VERSION,
            "unsupported pve template record")
    _text(record["record_id"], "record_id", pattern=IDENTIFIER)
    target = _mapping(record["target"], "record.target")
    require(set(target) == PUBLISH_TARGET_FIELDS and target.get("tls_verify") is True,
            "record target must be a fixed verified HTTPS target")
    _publish_url(target["api_endpoint"], "record.target.api_endpoint")
    _text(target["node"], "record.target.node", pattern=IDENTIFIER)
    _text(record["node"], "record.node", pattern=IDENTIFIER)
    require(type(record["vmid"]) is int and record["vmid"] > 0, "record vmid is invalid")
    _text(record["smbios_uuid"], "record.smbios_uuid")
    require(isinstance(record["volumes"], Mapping) and record["volumes"], "record volumes are required")
    require(isinstance(record["configuration"], Mapping), "record configuration must be a mapping")
    require(record["origin"] in {"publication", "observation"}, "record origin is invalid")
    if complete and record["origin"] == "publication":
        _text(record["execution_id"], "record.execution_id", pattern=IDENTIFIER)
        digest = record["artifact_digest"]
        require(isinstance(digest, str) and SHA256.fullmatch(digest.removeprefix("sha256:")),
                "publication record artifact digest is invalid")
    verification = _mapping(record["verification"], "record.verification")
    require(verification.get("template_config") == "passed", "record template configuration is not verified")
    return dict(record)


def validate_cleanup_request(value: Any) -> dict[str, Any]:
    request = _mapping(value, "pve template cleanup request")
    require(set(request) == {"kind", "schema_version", "target", "original_execution_id",
                             "original_execution_dir", "original_preview_digest", "objects", "volumes",
                             "ownership_admission"}, "cleanup request is incomplete")
    require(request["kind"] == "pve-template-cleanup-request" and type(request["schema_version"]) is int and
            request["schema_version"] == 1,
            "unsupported cleanup request")
    target = _mapping(request["target"], "cleanup.target")
    require(set(target) == PUBLISH_TARGET_FIELDS and target.get("tls_verify") is True,
            "cleanup target must be a fixed verified HTTPS target")
    _publish_url(target["api_endpoint"], "cleanup.target.api_endpoint")
    _text(target["node"], "cleanup.target.node", pattern=IDENTIFIER)
    for field in ("original_execution_id", "original_preview_digest"):
        _text(request[field], f"cleanup.{field}", pattern=IDENTIFIER if field.endswith("id") else None)
    _text(request["original_execution_dir"], "cleanup.original_execution_dir")
    require(isinstance(request["objects"], list) and isinstance(request["volumes"], list),
            "cleanup objects and volumes must be lists")
    admission = _mapping(request["ownership_admission"], "cleanup.ownership_admission")
    require(admission.get("owner") == "publisher" and _text(admission.get("reference"), "ownership reference"),
            "cleanup ownership is not publisher-authorized")
    return dict(request)


def validate_retire_request(value: Any) -> dict[str, Any]:
    request = _mapping(value, "pve template retire request")
    require(set(request) == {"kind", "schema_version", "target", "template_record",
                             "ownership_admission", "retirement_admission"}, "retire request is incomplete")
    require(request["kind"] == "pve-template-retire-request" and type(request["schema_version"]) is int and
            request["schema_version"] == 1,
            "unsupported retire request")
    target = _mapping(request["target"], "retire.target")
    require(set(target) == PUBLISH_TARGET_FIELDS and target.get("tls_verify") is True,
            "retire target must be a fixed verified HTTPS target")
    _publish_url(target["api_endpoint"], "retire.target.api_endpoint")
    _text(target["node"], "retire.target.node", pattern=IDENTIFIER)
    validate_template_record_v2(request["template_record"], complete=False)
    ownership = _mapping(request["ownership_admission"], "retire.ownership_admission")
    retirement = _mapping(request["retirement_admission"], "retire.retirement_admission")
    require(ownership.get("owner") == "publisher" and ownership.get("reference"),
            "retire ownership is not publisher-authorized")
    require(retirement.get("authorized") is True and retirement.get("dependencies_resolved") is True and
            retirement.get("reference"), "retire admission is incomplete")
    return dict(request)


def build_action_preview(request: Mapping[str, Any], *, action: str,
                         runtime: Mapping[str, Any], observed: Mapping[str, Any] | None = None) -> dict[str, Any]:
    require(action in {"cleanup", "retire"}, "unsupported pve template action")
    fixed = validate_cleanup_request(request) if action == "cleanup" else validate_retire_request(request)
    body = {"kind": "pve-template-preview", "schema_version": PUBLISH_PREVIEW_VERSION,
            "action": action, "fixed_input": fixed, "runtime": dict(runtime), "observed": dict(observed or {})}
    body["preview_digest"] = canonical_digest(body)
    return body
