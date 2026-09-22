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

from iaas_automation.common.errors import require


HELPER_PROTOCOL_VERSION = 2
PREVIEW_VERSION = 1
RECEIPT_VERSION = 1
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SHA512 = re.compile(r"^[0-9a-fA-F]{128}$")
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
RECIPE_FIELDS = {"name", "version", "image", "customization"}


def _mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, Mapping), f"{label} must be a mapping")
    require(all(isinstance(key, str) for key in value), f"{label} keys must be strings")
    return dict(value)


def _text(value: Any, label: str, *, pattern: re.Pattern[str] | None = None) -> str:
    require(isinstance(value, str) and bool(value) and "\x00" not in value, f"{label} must be a nonempty string")
    if pattern is not None:
        require(pattern.fullmatch(value) is not None, f"{label} has an invalid format")
    return value


def canonical_digest(value: Mapping[str, Any]) -> str:
    """Return the digest used to bind a preview, request, and receipt."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_target(value: Any) -> dict[str, Any]:
    target = _mapping(value, "target")
    require(not set(target) - TARGET_FIELDS, "target contains unsupported fields")
    node = _text(target.get("node"), "target.node", pattern=IDENTIFIER)
    host = _text(target.get("host", node), "target.host")
    require(not host.startswith("-") and all(char.isprintable() and not char.isspace() for char in host),
            "target.host contains unsafe characters")
    require("insecure" in target, "target.insecure must be explicit")
    require("ssh_user" in target and "ssh_port" in target, "target SSH identity must be explicit")
    endpoint = target.get("api_endpoint", target.get("endpoint"))
    endpoint = _text(endpoint, "target.api_endpoint")
    parsed = urlsplit(endpoint)
    require(parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and
            not parsed.password and not parsed.query and not parsed.fragment,
            "target.api_endpoint must be a fixed URL without credentials or query data")
    result = {"node": node, "host": host, "api_endpoint": endpoint.rstrip("/")}
    require(type(target["insecure"]) is bool, "target.insecure must be boolean")
    result["insecure"] = target["insecure"]
    if "tls_verify" in target:
        require(type(target["tls_verify"]) is bool, "target.tls_verify must be boolean")
        result["tls_verify"] = target["tls_verify"]
    if "insecure" in result and "tls_verify" in result:
        require(result["tls_verify"] is (not result["insecure"]),
                "target.insecure and target.tls_verify conflict")
    value = _text(target["ssh_user"], "target.ssh_user")
    require(not value.startswith("-") and all(char.isprintable() and not char.isspace() for char in value),
            "target.ssh_user contains unsafe characters")
    result["ssh_user"] = value
    require(type(target["ssh_port"]) is int and 1 <= target["ssh_port"] <= 65535,
            "target.ssh_port must be a valid port")
    result["ssh_port"] = target["ssh_port"]
    return result


def _validate_admission_target(value: Any) -> dict[str, Any]:
    """Accept the common PVE target envelope while comparing canonical fields."""
    target = _mapping(value, "admission.target")
    if "host" not in target and "ssh_host" in target:
        target["host"] = target["ssh_host"]
    allowed = {key: item for key, item in target.items() if key in TARGET_FIELDS}
    return validate_target(allowed)


def validate_recipe(value: Any) -> dict[str, Any]:
    """Validate the fixed build input independently of VM/S3 declarations."""
    recipe = _mapping(value, "recipe")
    require(not set(recipe) - BUILD_FIELDS, "recipe contains unsupported fields")
    require(recipe.get("schema_version") == 1, "template recipe schema_version must be 1")
    require(recipe.get("action") == "build", "template recipe action must be build")
    target = validate_target(recipe.get("target"))
    vmid = recipe.get("vmid")
    require(type(vmid) is int and 9000 <= vmid <= 9500, "template vmid must be in 9000-9500")
    version = _text(recipe.get("version"), "version", pattern=IDENTIFIER)
    recipe_name = _text(recipe.get("recipe", "debian-13"), "recipe", pattern=IDENTIFIER)
    image_url = _text(recipe.get("image_url"), "image_url")
    image_prefix = _text(recipe.get("image_url_prefix"), "image_url_prefix")
    image_parts = urlsplit(image_url)
    prefix_parts = urlsplit(image_prefix)
    require(image_parts.scheme == "https" and image_parts.netloc and not image_parts.username and
            not image_parts.password and not image_parts.fragment,
            "image_url must be an HTTPS URL without credentials or fragments")
    require(prefix_parts.scheme == "https" and prefix_parts.netloc and not prefix_parts.username and
            not prefix_parts.password and not prefix_parts.fragment,
            "image_url_prefix must be an HTTPS URL without credentials or fragments")
    require(image_url.startswith(image_prefix), "image_url must start with image_url_prefix")
    image_sha512 = _text(recipe.get("image_sha512"), "image_sha512", pattern=SHA512)
    result: dict[str, Any] = {
        "schema_version": 1, "action": "build", "recipe": recipe_name,
        "target": target, "vmid": vmid, "version": version,
        "image_url": image_url, "image_url_prefix": image_prefix,
        "image_sha512": image_sha512.lower(),
    }
    for field in ("import_storage", "disk_storage", "build_bridge", "build_domain",
                  "apt_mirror", "apt_security_mirror", "timezone", "locale",
                  "ciuser", "nameserver"):
        result[field] = _text(recipe.get(field), field)
    for field in ("apt_mirror", "apt_security_mirror"):
        parts = urlsplit(result[field])
        require(parts.scheme == "https" and parts.netloc and not parts.username and
                not parts.password and not parts.fragment, f"{field} must be an HTTPS URL")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+", result["locale"]) is not None,
            "locale has an invalid format")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+", result["ciuser"]) is not None,
            "ciuser has an invalid format")
    require("\n" not in result["timezone"] and "\r" not in result["timezone"],
            "timezone has an invalid format")
    return result


def build_preview(recipe: Mapping[str, Any], *, runtime: Mapping[str, Any] | None = None,
                  helper: Mapping[str, Any] | None = None) -> dict[str, Any]:
    fixed = validate_recipe(recipe)
    runtime_value = _mapping(runtime, "preview.runtime")
    image_digest = _text(runtime_value.get("image_digest"), "preview.runtime.image_digest")
    require(RUNTIME_DIGEST.fullmatch(image_digest) is not None,
            "preview.runtime.image_digest must be a resolved digest")
    helper_value = _mapping(helper if helper is not None else {"protocol_version": HELPER_PROTOCOL_VERSION},
                            "preview.helper")
    require(helper_value.get("protocol_version") == HELPER_PROTOCOL_VERSION,
            "preview.helper protocol is incompatible")
    body: dict[str, Any] = {
        "schema_version": PREVIEW_VERSION, "kind": "pve-template-preview",
        "action": "build", "fixed_input": fixed,
        "runtime": {"image_digest": image_digest},
        "helper": {"protocol_version": HELPER_PROTOCOL_VERSION, **helper_value},
    }
    body["preview_digest"] = canonical_digest(body)
    return body


def validate_preview(value: Any) -> dict[str, Any]:
    preview = _mapping(value, "preview")
    require(preview.get("schema_version") == PREVIEW_VERSION and
            preview.get("kind") == "pve-template-preview" and preview.get("action") == "build",
            "unsupported template preview")
    require(isinstance(preview.get("fixed_input"), Mapping), "template preview fixed_input is missing")
    fixed = validate_recipe(preview["fixed_input"])
    runtime = _mapping(preview.get("runtime"), "template preview runtime")
    image_digest = _text(runtime.get("image_digest"), "template preview runtime.image_digest")
    require(RUNTIME_DIGEST.fullmatch(image_digest) is not None,
            "template preview runtime.image_digest must be a resolved digest")
    helper = _mapping(preview.get("helper"), "template preview helper")
    require(helper.get("protocol_version") == HELPER_PROTOCOL_VERSION,
            "template preview helper protocol is incompatible")
    expected = dict(preview)
    digest = expected.pop("preview_digest", None)
    require(isinstance(digest, str) and digest.startswith("sha256:") and
            SHA256.fullmatch(digest.removeprefix("sha256:")) is not None,
            "template preview digest is invalid")
    require(canonical_digest(expected) == digest, "template preview digest does not match inputs")
    result = dict(preview)
    result["fixed_input"] = fixed
    result["runtime"] = {"image_digest": image_digest}
    result["helper"] = dict(helper)
    return result


def validate_cleanup_preview(value: Any) -> dict[str, Any]:
    preview = _mapping(value, "cleanup preview")
    require(preview.get("schema_version") == PREVIEW_VERSION and
            preview.get("kind") == "pve-template-cleanup-preview" and
            preview.get("action") == "cleanup", "unsupported template cleanup preview")
    require(IDENTIFIER.fullmatch(preview.get("original_execution", "")) is not None,
            "cleanup preview original execution is invalid")
    require(type(preview.get("vmid")) is int and 9000 <= preview["vmid"] <= 9500,
            "cleanup preview vmid is invalid")
    require(preview.get("owner") == "helper" and isinstance(preview.get("volumes"), list),
            "cleanup preview ownership is invalid")
    target = _mapping(preview.get("target"), "cleanup preview target")
    obj = _mapping(preview.get("object"), "cleanup preview object")
    runtime = _mapping(preview.get("runtime"), "cleanup preview runtime")
    image_digest = _text(runtime.get("image_digest"), "cleanup preview runtime.image_digest")
    require(RUNTIME_DIGEST.fullmatch(image_digest) is not None,
            "cleanup preview runtime.image_digest must be a resolved digest")
    helper = _mapping(preview.get("helper"), "cleanup preview helper")
    require(helper.get("protocol_version") == HELPER_PROTOCOL_VERSION,
            "cleanup preview helper protocol is incompatible")
    mode = preview.get("mode", "failed_build")
    require(mode in {"failed_build", "retire"}, "cleanup preview mode is invalid")
    digest = preview.get("preview_digest")
    body = {"original_execution": preview["original_execution"], "vmid": preview["vmid"],
            "volumes": preview["volumes"], "owner": preview["owner"], "mode": mode,
            "target": target, "object": obj,
            "runtime": {"image_digest": image_digest},
            "helper": {"protocol_version": HELPER_PROTOCOL_VERSION}}
    require(isinstance(digest, str) and digest == canonical_digest(body),
            "cleanup preview digest does not match inputs")
    return dict(preview)


def validate_request(value: Any) -> dict[str, Any]:
    """Validate the node helper JSON envelope and reject command injection fields."""
    request = _mapping(value, "helper request")
    require(not set(request) - {"protocol_version", "operation", "execution_id", "preview", "template",
                                "recovery_of", "owner", "cleanup", "admission", "template_admission"},
            "helper request contains unsupported fields")
    require(request.get("protocol_version") == HELPER_PROTOCOL_VERSION,
            "unsupported helper protocol version")
    operation = request.get("operation")
    require(operation in {"capabilities", "check", "observe", "submit", "query", "cleanup_preview", "cleanup"},
            "unsupported helper operation")
    if operation not in {"capabilities", "check", "observe"}:
        execution_id = _text(request.get("execution_id"), "execution_id", pattern=IDENTIFIER)
        request["execution_id"] = execution_id
    if operation == "observe":
        template = _mapping(request.get("template"), "template")
        require(type(template.get("vmid")) is int and 9000 <= template["vmid"] <= 9500,
                "template vmid is invalid")
        request["template"] = template
    if operation == "submit":
        request["preview"] = validate_preview(request.get("preview"))
        admission = _mapping(request.get("admission"), "admission")
        require(admission.get("schema_version") == 1 and admission.get("approved") is True,
                "template execution admission must be v1 and approved")
        require(isinstance(admission.get("execution_id"), str),
                "template execution admission execution_id is required")
        digest = admission.get("preview_digest", admission.get("plan_digest"))
        require(digest == request["preview"]["preview_digest"],
                "template admission does not match preview")
        consumption = _mapping(admission.get("consumption"), "admission.consumption")
        pending = _mapping(admission.get("pending"), "admission.pending")
        serialization = _mapping(admission.get("serialization"), "admission.serialization")
        require(consumption.get("reserved") is True and IDENTIFIER.fullmatch(str(consumption.get("reservation_id", ""))) is not None,
                "template execution admission consumption is incomplete")
        require(IDENTIFIER.fullmatch(str(pending.get("record_id", ""))) is not None,
                "template execution admission pending is incomplete")
        require(serialization.get("held") is True and IDENTIFIER.fullmatch(str(serialization.get("context_id", ""))) is not None,
                "template execution admission serialization is incomplete")
        target = _validate_admission_target(admission.get("target"))
        preview_target = request["preview"]["fixed_input"]["target"]
        require(target == preview_target, "template admission target does not match preview")
        require(admission.get("execution_id") == request["execution_id"],
                "template admission does not match execution")
        request["admission"] = admission
        if "template_admission" in request:
            template_admission = _mapping(request["template_admission"], "template_admission")
            require(template_admission.get("status") in {"available", "pending_validation"},
                    "template admission is revoked or invalid")
            require(template_admission.get("object") is not None,
                    "template admission object is required")
    if operation in {"cleanup_preview", "cleanup"}:
        cleanup = _mapping(request.get("cleanup"), "cleanup")
        require(cleanup.get("vmid") is not None and type(cleanup["vmid"]) is int and
                9000 <= cleanup["vmid"] <= 9500, "cleanup vmid is invalid")
        require(cleanup.get("owner") in {"helper", "opentofu", "unknown"}, "cleanup owner is invalid")
        require(cleanup.get("original_execution"), "cleanup original execution is required")
        require(IDENTIFIER.fullmatch(cleanup["original_execution"]) is not None,
                "cleanup original execution is invalid")
        require(cleanup.get("management_status") in {"active", "stopped", "unknown"},
                "cleanup management status is invalid")
        mode = cleanup.get("mode", "failed_build")
        require(mode in {"failed_build", "retire"}, "cleanup mode is invalid")
        if mode == "retire":
            require(cleanup.get("retirement_authorized") is True and
                    cleanup.get("dependencies_resolved") is True,
                    "cleanup retirement authorization is incomplete")
        if operation == "cleanup":
            admission = _mapping(request.get("admission"), "admission")
            require(admission.get("schema_version") == 1 and admission.get("approved") is True,
                    "cleanup execution admission must be v1 and approved")
            require(admission.get("execution_id") == request["execution_id"],
                    "cleanup admission does not match execution")
            require(admission.get("plan_digest") == request["cleanup"].get("preview_digest"),
                    "cleanup admission does not match preview")
            require(_mapping(admission.get("target"), "admission.target") ==
                    _mapping(request["cleanup"].get("target"), "cleanup.target"),
                    "cleanup admission target does not match preview")
            consumption = _mapping(admission.get("consumption"), "admission.consumption")
            pending = _mapping(admission.get("pending"), "admission.pending")
            serialization = _mapping(admission.get("serialization"), "admission.serialization")
            require(consumption.get("reserved") is True and consumption.get("reservation_id"),
                    "cleanup execution admission consumption is incomplete")
            require(pending.get("record_id") and serialization.get("held") is True and
                    serialization.get("context_id"),
                    "cleanup execution admission context is incomplete")
            require(request.get("recovery_of") == cleanup.get("original_execution"),
                    "cleanup recovery_of must identify the original execution")
            require(request["execution_id"] != cleanup["original_execution"],
                    "cleanup requires a new execution identity")
            request["admission"] = admission
        request["cleanup"] = cleanup
    return request


def receipt(*, execution_id: str, preview: Mapping[str, Any], status: str,
            phases: list[Mapping[str, Any]], effects: str = "unknown",
            recovery_of: str | None = None, record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a versioned, truthful result without implying publication."""
    require(status in {"running", "succeeded", "failed", "unknown"}, "invalid receipt status")
    result = {
        "schema_version": RECEIPT_VERSION, "kind": "pve-template-receipt",
        "execution_id": execution_id, "preview_digest": preview.get("preview_digest"),
        "status": status, "effects": effects, "phases": list(phases),
        "recovery_of": recovery_of, "publication": "caller_owned",
        "clone_verification": "not_performed", "business_acceptance": "not_performed",
    }
    if record is not None:
        result["record_id"] = record.get("record_id")
        result["target"] = record.get("target")
        result["object"] = record.get("object")
        result["configuration"] = record.get("configuration")
    return result


def validate_template_record(value: Any, *, complete: bool = True) -> dict[str, Any]:
    """Validate a caller-transferable template record without facility access."""
    record = _mapping(value, "template record")
    require(record.get("schema_version") == 1, "template record schema_version must be 1")
    require(IDENTIFIER.fullmatch(str(record.get("record_id", ""))) is not None,
            "template record record_id is invalid")
    target_value = _mapping(record.get("target"), "template record target")
    allowed = {key: value for key, value in target_value.items() if key in TARGET_FIELDS}
    target = validate_target(allowed)
    if "storage_id" in target_value:
        target["storage_id"] = _text(target_value["storage_id"], "template record target.storage_id")
    if "ssh_host" in target_value:
        target["ssh_host"] = _text(target_value["ssh_host"], "template record target.ssh_host")
    obj = _mapping(record.get("object"), "template record object")
    require(IDENTIFIER.fullmatch(str(obj.get("node", ""))) is not None,
            "template record object.node is invalid")
    require(type(obj.get("vmid")) is int and 9000 <= obj["vmid"] <= 9500,
            "template record object.vmid is invalid")
    uuid = obj.get("smbios_uuid")
    disks = obj.get("disks")
    complete_identity = isinstance(uuid, str) and bool(uuid) and isinstance(disks, Mapping) and bool(disks)
    if complete:
        require(complete_identity, "template record identity is incomplete")
    configuration = _mapping(record.get("configuration", {}), "template record configuration")
    if complete:
        require(bool(configuration), "template record configuration is missing")
    result = dict(record)
    result.update(schema_version=1, target=target, object=dict(obj), configuration=configuration)
    return result
