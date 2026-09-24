"""Versioned, value-only contracts used by the PVE runtime.

The runtime deliberately keeps these contracts independent from the native
OpenTofu and PVE result formats.  Callers can therefore retain the original
materials while public summaries only contain the small, reviewed projection.
All validators return a detached copy so callers cannot accidentally mutate a
validated input while it is being bound to an execution.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping, cast

from iaas.common.errors import require


PLAN_METADATA_VERSION = 2
RESULT_VERSION = 1
TEMPLATE_VERSION = 2
EXECUTION_ADMISSION_VERSION = 1

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PHASES = {"planned", "running", "succeeded", "failed", "unknown", "verified"}
_EFFECTS = {"none", "known", "unknown"}
_OUTCOMES = {"not_attempted", "not_performed", "passed", "failed", "unknown", "unconfirmed"}
_VERIFICATION_CATEGORIES = {"configuration", "guest", "business"}


def _object(value: Any, name: str) -> dict[str, Any]:
    require(type(value) is dict, f"{name} must be an object")
    require(all(isinstance(key, str) for key in value), f"{name} keys must be strings")
    return value


def _required(document: Mapping[str, Any], names: set[str], name: str) -> None:
    missing = sorted(names - set(document))
    require(not missing, f"{name} is missing required fields: {', '.join(missing)}")


def _identifier(value: Any, name: str) -> str:
    require(isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None, f"{name} must be a bounded identifier")
    return value


def _digest_value(value: Any, name: str) -> str:
    require(isinstance(value, str) and _DIGEST.fullmatch(value) is not None, f"{name} must be a lowercase SHA-256")
    return value


def _digest(document: Mapping[str, Any], name: str) -> str:
    value = document.get("plan_digest", document.get("plan_sha256"))
    return _digest_value(value, f"{name}.plan_digest")


def validate_verification_requirements(value: Any) -> dict[str, Any]:
    """Validate the fixed verification contract carried by a plan/result."""
    document = _object(value, "verification_requirements")
    requirements = document.get("requirements")
    require(isinstance(requirements, list) and requirements, "verification_requirements must include configuration")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(cast(list[Any], requirements)):
        row = _object(item, f"verification_requirements.requirements[{index}]")
        _required(row, {"category", "scope", "required", "responsibility"}, f"verification_requirements.requirements[{index}]")
        category = _identifier(row["category"], f"verification_requirements.requirements[{index}].category")
        require(category in _VERIFICATION_CATEGORIES, f"unsupported verification category {category}")
        require(category not in seen, "verification_requirements contains duplicate categories")
        seen.add(category)
        require(isinstance(row["scope"], str) and row["scope"], f"verification_requirements.requirements[{index}].scope is required")
        require(type(row["required"]) is bool, f"verification_requirements.requirements[{index}].required must be boolean")
        require(isinstance(row["responsibility"], str) and row["responsibility"], f"verification_requirements.requirements[{index}].responsibility is required")
        require(row["responsibility"] == ("iaas" if category == "configuration" else "caller"),
                "unsupported verification responsibility")
        normalized.append(deepcopy(row))
    require("configuration" in seen, "verification_requirements must include configuration")
    configuration = next(item for item in normalized if item["category"] == "configuration")
    require(configuration["required"] is True, "configuration verification must remain required")
    require(configuration["responsibility"] == "iaas", "configuration verification must be owned by iaas")
    require(configuration["scope"] == "changed_objects", "configuration verification scope must be changed_objects")
    digest = document.get("policy_digest")
    if digest is not None:
        _digest_value(digest, "verification_requirements.policy_digest")
    return {**deepcopy(document), "requirements": normalized}


def validate_state_admission_reference(value: Any) -> dict[str, Any]:
    """Validate the caller-owned state admission embedded in plan metadata."""
    document = _object(value, "state_admission")
    _required(document, {"schema_version", "root_id", "backend", "workspace", "mode"}, "state_admission")
    require(type(document["schema_version"]) is int and document["schema_version"] == 1, "unsupported state admission version")
    _identifier(document["root_id"], "state_admission.root_id")
    _identifier(document["workspace"], "state_admission.workspace")
    require(document["mode"] in {"first_use", "existing", "reconciled_empty"}, "unsupported state admission mode")
    backend = _object(document["backend"], "state_admission.backend")
    _required(backend, {"bucket", "key", "region", "endpoint", "tls_verify", "path_style"}, "state_admission.backend")
    for key in ("bucket", "key", "region"):
        require(isinstance(backend[key], str) and backend[key], f"state_admission.backend.{key} is required")
    require(backend["endpoint"] is None or (isinstance(backend["endpoint"], str) and backend["endpoint"]),
            "state_admission.backend.endpoint must be explicit or null")
    require(type(backend["tls_verify"]) is bool and type(backend["path_style"]) is bool,
            "state_admission.backend TLS and path style must be boolean")
    if document["mode"] == "existing":
        _identifier(document.get("lineage"), "state_admission.lineage") if document.get("lineage") else require(False, "existing state admission requires lineage")
    if document["mode"] == "first_use":
        _identifier(document.get("initialization_ref"), "state_admission.initialization_ref")
    if document["mode"] == "reconciled_empty":
        require(isinstance(document.get("reconciliation_ref"), str) and document["reconciliation_ref"],
                "reconciled_empty state admission requires reconciliation_ref")
    return deepcopy(document)


def validate_execution_admission(value: Any, *, digest: str | None = None,
                                 target: Mapping[str, Any] | None = None,
                                 execution_id: str | None = None) -> dict[str, Any]:
    """Validate a one-time caller reservation before a facility write."""
    document = _object(value, "execution_admission")
    _required(document, {"schema_version", "execution_id", "plan_digest", "target", "approved", "consumption", "pending", "serialization"}, "execution_admission")
    require(type(document["schema_version"]) is int and document["schema_version"] == EXECUTION_ADMISSION_VERSION, "unsupported execution admission version")
    actual_execution_id = _identifier(document["execution_id"], "execution_admission.execution_id")
    _digest_value(document["plan_digest"], "execution_admission.plan_digest")
    if digest is not None:
        require(document["plan_digest"] == digest, "execution admission plan digest conflicts with selected plan")
    if execution_id is not None:
        require(actual_execution_id == execution_id, "execution admission identity conflicts with selected execution")
    selected_target = _object(document["target"], "execution_admission.target")
    validate_target(selected_target, "execution_admission.target")
    if target is not None:
        expected = _object(target, "expected target")
        for key, expected_value in expected.items():
            require(selected_target.get(key) == expected_value, f"execution admission target conflicts at {key}")
    require(document["approved"] is True, "execution admission requires caller approval")
    consumption = _object(document["consumption"], "execution_admission.consumption")
    _required(consumption, {"reserved", "reservation_id"}, "execution_admission.consumption")
    require(consumption["reserved"] is True, "execution admission requires a durable consumption reservation")
    _identifier(consumption["reservation_id"], "execution_admission.consumption.reservation_id")
    pending = _object(document["pending"], "execution_admission.pending")
    _required(pending, {"record_id"}, "execution_admission.pending")
    _identifier(pending["record_id"], "execution_admission.pending.record_id")
    serialization = _object(document["serialization"], "execution_admission.serialization")
    _required(serialization, {"held", "context_id"}, "execution_admission.serialization")
    require(serialization["held"] is True, "execution admission requires the complete workflow serialization context")
    _identifier(serialization["context_id"], "execution_admission.serialization.context_id")
    if document.get("recovery_of") is not None:
        _identifier(document["recovery_of"], "execution_admission.recovery_of")
        require(document["recovery_of"] != actual_execution_id, "execution admission recovery_of cannot equal execution_id")
        require(pending.get("execution_id") == document["recovery_of"],
                "recovery admission must retain the original pending execution")
    return {**deepcopy(document), "execution_id": actual_execution_id}


def validate_target(value: Any, name: str = "target") -> dict[str, Any]:
    """Validate a fixed, single PVE target without accepting provider aliases."""
    target = _object(value, name)
    endpoint = target.get("api_endpoint", target.get("endpoint"))
    require(isinstance(endpoint, str) and endpoint, f"{name}.api_endpoint is required")
    endpoint = cast(str, endpoint)
    require("@" not in endpoint and "?" not in endpoint and "#" not in endpoint, f"{name}.api_endpoint must not contain credentials or query data")
    if "root_id" in target:
        require(isinstance(target["root_id"], str) and target["root_id"], f"{name}.root_id must be nonempty")
    if "insecure" in target:
        require(type(target["insecure"]) is bool, f"{name}.insecure must be boolean")
    if "tls_verify" in target or "api_tls_verify" in target:
        tls = target.get("tls_verify", target.get("api_tls_verify"))
        require(type(tls) is bool, f"{name}.tls_verify must be boolean")
        if "insecure" in target:
            require(tls is (not target["insecure"]), f"{name}.insecure and tls_verify conflict")
    provider = target.get("provider", "proxmox")
    require(provider == "proxmox", f"{name}.provider must be proxmox")
    aliases = target.get("provider_aliases", [])
    require(isinstance(aliases, list) and not aliases, f"{name} does not support provider aliases")
    return deepcopy(target)


def validate_plan_metadata(value: Any) -> dict[str, Any]:
    """Validate v2 PVE saved-plan metadata and its admission references."""
    document = _object(value, "PVE plan metadata")
    _required(document, {"schema_version", "plan_digest", "target", "backend", "workspace", "runtime", "state_admission", "verification_requirements"}, "PVE plan metadata")
    require(type(document["schema_version"]) is int and document["schema_version"] == PLAN_METADATA_VERSION, "unsupported PVE plan metadata; prepare a new plan")
    _digest_value(document["plan_digest"], "PVE plan metadata.plan_digest")
    target = validate_target(document["target"], "PVE plan metadata.target")
    _identifier(document["workspace"], "PVE plan metadata.workspace")
    if "root_id" in document and "root_id" in target:
        require(target["root_id"] == document["root_id"], "PVE plan metadata root identity conflicts with target")
    backend = _object(document["backend"], "PVE plan metadata.backend")
    _required(backend, {"bucket", "key", "region", "use_lockfile", "endpoint", "tls_verify", "path_style"}, "PVE plan metadata.backend")
    require(backend["use_lockfile"] is True, "PVE plan metadata requires native S3 lockfile")
    require(type(backend["tls_verify"]) is bool and type(backend["path_style"]) is bool,
            "PVE plan metadata backend TLS and path style must be boolean")
    require(document["workspace"] == document.get("state_admission", {}).get("workspace"), "plan and state workspace conflict")
    state = validate_state_admission_reference(document["state_admission"])
    if "root_id" in document:
        require(state["root_id"] == document["root_id"], "plan and state root identity conflict")
    verification = validate_verification_requirements(document["verification_requirements"])
    require(isinstance(document["runtime"], str) and document["runtime"], "PVE plan metadata.runtime is required")
    if "execution_admission" in document:
        admission = validate_execution_admission(document["execution_admission"])
        require(admission["plan_digest"] == document["plan_digest"], "plan and execution admission digest conflict")
    if "template_admission" in document and document["template_admission"] is not None:
        validate_template_admission(document["template_admission"])
    normalized = deepcopy(document)
    normalized.update(target=target, state_admission=state, verification_requirements=verification)
    return normalized


def validate_template_admission(value: Any) -> dict[str, Any]:
    document = _object(value, "template_admission")
    _required(document, {"schema_version", "execution_id", "plan_digest", "record_id", "purpose", "status"}, "template_admission")
    require(type(document["schema_version"]) is int and document["schema_version"] == TEMPLATE_VERSION, "unsupported template admission version")
    _identifier(document["execution_id"], "template_admission.execution_id")
    _digest_value(document["plan_digest"], "template_admission.plan_digest")
    _identifier(document["record_id"], "template_admission.record_id")
    require(isinstance(document["purpose"], str) and document["purpose"], "template_admission.purpose is required")
    require(document["status"] in {"available", "pending_validation", "revoked"}, "invalid template admission status")
    require("template_record" in document and "object" not in document,
            "template admission requires pve-template-record/v2")
    from iaas.pve_template.contracts import validate_template_record_v2
    validate_template_record_v2(document["template_record"], complete=False)
    require(document["status"] != "revoked", "template admission is revoked")
    return deepcopy(document)


def _validate_effects(value: Any, name: str) -> dict[str, Any]:
    effects = _object(value, name)
    _required(effects, {"facility", "state", "collection"}, name)
    for key in ("facility", "state", "collection"):
        require(effects[key] in _EFFECTS, f"{name}.{key} has an invalid effect status")
    return deepcopy(effects)


def _validate_outcome(value: Any, name: str) -> dict[str, Any]:
    result = _object(value, name)
    _required(result, {"status"}, name)
    require(result["status"] in _OUTCOMES | {"success"}, f"{name}.status is invalid")
    return deepcopy(result)


def validate_result(value: Any) -> dict[str, Any]:
    """Validate the multidimensional v1 PVE execution result."""
    document = _object(value, "PVE result")
    required = {"schema_version", "target", "execution_id", "runtime", "phase", "effects", "native_execution", "state_persistence", "verification", "collection", "verification_requirements"}
    _required(document, required, "PVE result")
    require(type(document["schema_version"]) is int and document["schema_version"] == RESULT_VERSION, "unsupported PVE result version")
    require("plan_digest" in document or "preview_digest" in document,
            "PVE result requires plan_digest or preview_digest")
    if "plan_digest" in document:
        _digest_value(document["plan_digest"], "PVE result.plan_digest")
    if "preview_digest" in document:
        _digest_value(document["preview_digest"], "PVE result.preview_digest")
    target = validate_target(document["target"], "PVE result.target")
    execution_id = _identifier(document["execution_id"], "PVE result.execution_id")
    require(isinstance(document["runtime"], str) and document["runtime"], "PVE result.runtime is required")
    require(document["phase"] in _PHASES, "PVE result.phase is invalid")
    effects = _validate_effects(document["effects"], "PVE result.effects")
    native = _validate_outcome(document["native_execution"], "PVE result.native_execution")
    persistence = _validate_outcome(document["state_persistence"], "PVE result.state_persistence")
    verification = _validate_outcome(document["verification"], "PVE result.verification")
    collection = _validate_outcome(document["collection"], "PVE result.collection")
    requirements = validate_verification_requirements(document["verification_requirements"])
    recovery_of = document.get("recovery_of")
    if recovery_of is not None:
        _identifier(recovery_of, "PVE result.recovery_of")
        require(recovery_of != execution_id, "PVE result.recovery_of cannot equal execution_id")
    normalized = deepcopy(document)
    normalized.update(target=target, effects=effects, native_execution=native,
                     state_persistence=persistence, verification=verification,
                     collection=collection, verification_requirements=requirements)
    return normalized
