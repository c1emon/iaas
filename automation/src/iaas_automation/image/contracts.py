"""Strict, credential-free contracts for the independent image tool.

The image tool deliberately knows nothing about PVE, OpenTofu or an artifact
registry.  Paths are always interpreted relative to an explicitly supplied
artifact root and all schema versions are fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from iaas_automation.common.errors import require

IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA512 = re.compile(r"^[0-9a-f]{128}$")
RUNTIME_DIGEST = re.compile(r"^(?:[^@/\s]+(?:/[^@\s]+)*)?@?sha256:[0-9a-f]{64}$")
SUPPORTED_PROFILES = {"debian-13-amd64": "1"}
SUPPORTED_CHECKS = {
    "format", "self-contained", "disk-size", "firmware", "identity-cleanup",
    "cloud-init", "guest-agent", "first-boot",
}
RESOURCE_FIELDS = {"cpus", "memory_mib", "work_min_free_bytes", "max_output_bytes", "timeout_seconds"}
BUILD_REQUEST_VERSION = 1
TEST_REQUEST_VERSION = 1
ARTIFACT_VERSION = 1


def _mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, Mapping), f"{label} must be a mapping")
    require(all(isinstance(key, str) for key in value), f"{label} keys must be strings")
    return dict(value)


def _version(value: Any, expected: int, label: str) -> None:
    # bool is an int subclass; schema versions must never accept true/false.
    require(type(value) is int and value == expected, f"{label} is unsupported")


def _text(value: Any, label: str, pattern: re.Pattern[str] | None = None) -> str:
    require(isinstance(value, str) and bool(value) and "\x00" not in value, f"{label} must be a nonempty string")
    if pattern is not None:
        require(pattern.fullmatch(value) is not None, f"{label} has an invalid format")
    return value


def _url(value: Any, label: str) -> str:
    result = _text(value, label)
    parsed = urlsplit(result)
    require(parsed.scheme == "https" and parsed.netloc and not parsed.username and
            not parsed.password and not parsed.fragment and not parsed.query,
            f"{label} must be an HTTPS URL without credentials or query data")
    return result


def _canonical_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise ValueError("floating point values are not supported by the contract")  # noqa: TRY004
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        require(all(isinstance(key, str) for key in value), "canonical object keys must be strings")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    raise ValueError("unsupported value in canonical JSON")


def canonical_json(value: Any) -> str:
    return json.dumps(_canonical_value(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def canonical_digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def load_strict_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_pairs,
                          parse_float=lambda _: (_ for _ in ()).throw(ValueError()),
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("JSON document is not readable") from None


def _checks(value: Any, label: str) -> dict[str, list[dict[str, Any]]]:
    checks = _mapping(value, label)
    require(set(checks) <= {"required", "optional"}, f"{label} contains unsupported fields")
    result: dict[str, list[dict[str, Any]]] = {}
    for category in ("required", "optional"):
        raw = checks.get(category, [])
        require(isinstance(raw, list), f"{label}.{category} must be a list")
        seen: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                item = {"id": item, "scope": "static"}
            row = _mapping(item, f"{label}.{category} entry")
            require(set(row) <= {"id", "scope"}, f"{label}.{category} entry contains unsupported fields")
            check_id = _text(row.get("id"), "check.id", IDENTIFIER)
            scope = _text(row.get("scope", "static"), "check.scope", IDENTIFIER)
            require(check_id in SUPPORTED_CHECKS, "unsupported image check")
            require(check_id not in seen, "duplicate image check")
            seen.add(check_id)
            normalized.append({"id": check_id, "scope": scope})
        result[category] = normalized
    require({x["id"] for x in result["required"]}.isdisjoint({x["id"] for x in result["optional"]}),
            f"{label} required and optional checks overlap")
    return result


def _resources(value: Any, label: str = "resources") -> dict[str, int]:
    raw = _mapping(value, label)
    require(set(raw) == RESOURCE_FIELDS, f"{label} must specify bounded executor resources")
    result: dict[str, int] = {}
    for key in RESOURCE_FIELDS:
        number = raw[key]
        require(type(number) is int and number > 0, f"{label}.{key} must be a positive integer")
        result[key] = number
    require(result["cpus"] <= 128 and result["memory_mib"] <= 1_048_576 and
            result["timeout_seconds"] <= 86_400 and result["max_output_bytes"] <= 1 << 40,
            f"{label} exceeds supported bounds")
    return result


def _checksum(value: Any, label: str = "base.checksum") -> dict[str, str]:
    raw = _mapping(value, label)
    require(set(raw) == {"algorithm", "value"}, f"{label} must contain algorithm and value")
    algorithm = _text(raw["algorithm"], f"{label}.algorithm").lower()
    pattern = SHA256 if algorithm == "sha256" else SHA512 if algorithm == "sha512" else None
    require(pattern is not None and isinstance(raw["value"], str) and
            pattern.fullmatch(raw["value"].lower()) is not None,
            f"{label} is invalid")
    return {"algorithm": algorithm, "value": raw["value"].lower()}


def validate_build_request(value: Any) -> dict[str, Any]:
    request = _mapping(value, "image build request")
    require(set(request) == {"kind", "schema_version", "profile", "version", "base", "guest",
                             "customization", "resources", "checks"},
            "image build request contains unsupported or missing fields")
    require(request.get("kind") == "image-build-request", "unsupported image build request")
    _version(request.get("schema_version"), BUILD_REQUEST_VERSION, "image build request schema_version")
    profile = _mapping(request["profile"], "profile")
    require(set(profile) == {"id", "version"}, "profile must contain id and version")
    profile_id = _text(profile["id"], "profile.id", IDENTIFIER)
    profile_version = _text(profile["version"], "profile.version", IDENTIFIER)
    require(SUPPORTED_PROFILES.get(profile_id) == profile_version, "unsupported image profile")
    base = _mapping(request["base"], "base")
    require(set(base) == {"object_ref", "checksum"}, "base must contain object_ref and checksum")
    object_ref = _url(base["object_ref"], "base.object_ref")
    guest = _mapping(request["guest"], "guest")
    require(set(guest) == {"architecture", "firmware"}, "guest must contain architecture and firmware")
    architecture = _text(guest["architecture"], "guest.architecture", IDENTIFIER)
    require(architecture == "amd64", "only amd64 image builds are supported")
    firmware = _text(guest["firmware"], "guest.firmware", IDENTIFIER)
    require(firmware in {"bios", "uefi"}, "guest.firmware must be bios or uefi")
    customization = _mapping(request["customization"], "customization")
    allowed = {"apt_mirror", "apt_security_mirror", "packages", "timezone", "locale", "cloud_init", "guest_agent"}
    require(set(customization) <= allowed, "customization contains unsupported fields")
    mirrors = {key: _url(customization[key], f"customization.{key}") for key in ("apt_mirror", "apt_security_mirror")
               if key in customization}
    packages = customization.get("packages", [])
    require(isinstance(packages, list) and all(isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9+_.:-]+", item)
                                               for item in packages),
            "customization.packages must contain package names")
    result = {
        "kind": "image-build-request", "schema_version": BUILD_REQUEST_VERSION,
        "profile": {"id": profile_id, "version": profile_version},
        "version": _text(request["version"], "version", IDENTIFIER),
        "base": {"object_ref": object_ref, "checksum": _checksum(base["checksum"])},
        "guest": {"architecture": architecture, "firmware": firmware},
        "customization": {**mirrors, "packages": list(packages),
                           **({key: _text(customization[key], f"customization.{key}")
                               for key in ("timezone", "locale") if key in customization}),
                           "cloud_init": customization.get("cloud_init", "installed"),
                           "guest_agent": customization.get("guest_agent", "installed")},
        "resources": _resources(request["resources"]),
        "checks": _checks(request["checks"], "checks"),
    }
    require(result["customization"]["cloud_init"] in {"installed", "absent"}, "invalid cloud_init setting")
    require(result["customization"]["guest_agent"] in {"installed", "absent"}, "invalid guest_agent setting")
    return result


def _safe_relative_path(value: Any, label: str, *, allow_null: bool = False) -> str | None:
    if allow_null and value is None:
        return None
    path = _text(value, label)
    parsed = Path(path)
    require(not parsed.is_absolute() and ".." not in parsed.parts, f"{label} must stay inside artifact root")
    return path


def validate_artifact(value: Any, *, artifact_root: Path | None = None,
                      require_disk: bool = False) -> dict[str, Any]:
    artifact = _mapping(value, "image artifact")
    allowed = {"kind", "schema_version", "artifact_id", "version", "disk", "guest", "build", "checks"}
    require(set(artifact) == allowed, "image artifact contains unsupported or missing fields")
    require(artifact.get("kind") == "image-artifact", "unsupported image artifact")
    _version(artifact.get("schema_version"), ARTIFACT_VERSION, "image artifact schema_version")
    disk = _mapping(artifact["disk"], "disk")
    require(set(disk) == {"path", "format", "sha256", "size_bytes", "virtual_size_bytes", "self_contained"},
            "disk descriptor is incomplete")
    path = _safe_relative_path(disk["path"], "disk.path")
    digest = _text(disk["sha256"], "disk.sha256").lower()
    require(SHA256.fullmatch(digest) is not None, "disk.sha256 must be lowercase SHA-256")
    require(disk["format"] == "qcow2" and disk["self_contained"] is True,
            "only self-contained qcow2 images are supported")
    require(type(disk["size_bytes"]) is int and disk["size_bytes"] > 0 and
            type(disk["virtual_size_bytes"]) is int and disk["virtual_size_bytes"] > 0,
            "disk sizes must be positive integers")
    guest = _mapping(artifact["guest"], "artifact.guest")
    require(set(guest) == {"architecture", "firmware", "cloud_init", "guest_agent"},
            "artifact guest descriptor is incomplete")
    require(guest["architecture"] == "amd64" and guest["firmware"] in {"bios", "uefi"},
            "artifact guest architecture or firmware is unsupported")
    require(guest["cloud_init"] in {"installed", "absent", "unknown"} and
            guest["guest_agent"] in {"installed", "absent", "unknown"},
            "artifact guest capability is invalid")
    build = _mapping(artifact["build"], "artifact.build")
    require(set(build) <= {"origin", "recipe_id", "recipe_version", "runtime_digest", "config_digest", "execution_id"},
            "artifact build contains unsupported fields")
    origin = build.get("origin", "iaas")
    require(origin in {"iaas", "external"}, "artifact build origin is invalid")
    if origin == "iaas":
        for field in ("recipe_id", "recipe_version", "runtime_digest", "config_digest", "execution_id"):
            _text(build.get(field), f"artifact.build.{field}")
        require(RUNTIME_DIGEST.fullmatch(build["runtime_digest"]) is not None, "artifact runtime digest is invalid")
        require(SHA256.fullmatch(build["config_digest"].removeprefix("sha256:")) is not None,
                "artifact config digest is invalid")
    checks = artifact["checks"]
    require(isinstance(checks, list), "artifact.checks must be a list")
    normalized_checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in checks:
        row = _mapping(item, "artifact check")
        require(set(row) == {"id", "scope", "status", "evidence_ref"}, "artifact check is incomplete")
        check_id = _text(row["id"], "artifact check.id", IDENTIFIER)
        require(check_id in SUPPORTED_CHECKS and check_id not in seen, "artifact check id is invalid or duplicated")
        seen.add(check_id)
        status = _text(row["status"], "artifact check.status", IDENTIFIER)
        require(status in {"passed", "failed", "not_performed", "unknown"}, "artifact check status is invalid")
        normalized_checks.append({"id": check_id, "scope": _text(row["scope"], "artifact check.scope", IDENTIFIER),
                                  "status": status, "evidence_ref": _safe_relative_path(row["evidence_ref"], "artifact check.evidence_ref", allow_null=True)})
    result = {"kind": "image-artifact", "schema_version": 1,
              "artifact_id": _text(artifact["artifact_id"], "artifact_id", IDENTIFIER),
              "version": _text(artifact["version"], "artifact.version", IDENTIFIER),
              "disk": {"path": path, "format": "qcow2", "sha256": digest,
                       "size_bytes": disk["size_bytes"], "virtual_size_bytes": disk["virtual_size_bytes"],
                       "self_contained": True},
              "guest": dict(guest), "build": dict(build), "checks": normalized_checks}
    if artifact_root is not None:
        root = artifact_root.resolve()
        require(path is not None, "artifact disk path is missing")
        assert path is not None
        disk_path = (root / path)
        require(not disk_path.is_symlink() and disk_path.resolve().is_relative_to(root),
                "artifact disk path escapes artifact root")
        if require_disk:
            require(disk_path.is_file(), "artifact disk is missing")
            require(disk_path.stat().st_size == disk["size_bytes"], "artifact disk size does not match descriptor")
            actual = _file_sha256(disk_path)
            require(actual == digest, "artifact disk SHA-256 does not match descriptor")
    return result


def validate_test_request(value: Any) -> dict[str, Any]:
    request = _mapping(value, "image test request")
    require(set(request) == {"kind", "schema_version", "artifact", "artifact_root", "checks", "resources"},
            "image test request contains unsupported or missing fields")
    require(request["kind"] == "image-test-request", "unsupported image test request")
    _version(request.get("schema_version"), TEST_REQUEST_VERSION, "image test request schema_version")
    artifact = _mapping(request["artifact"], "test artifact")
    return {"kind": request["kind"], "schema_version": 1,
            "artifact": validate_artifact(artifact),
            "artifact_root": _text(request["artifact_root"], "artifact_root"),
            "checks": _checks(request["checks"], "test checks"),
            "resources": _resources(request["resources"], "test resources")}


def validate_test_result(value: Any) -> dict[str, Any]:
    result = _mapping(value, "image test result")
    require(set(result) == {"kind", "schema_version", "execution_id", "component", "operation", "runtime_digest", "input_digest",
                            "phase", "status", "effects", "verification", "collection", "disk_sha256",
                            "test_config_digest", "checks", "base_unchanged", "cleanup"},
            "image test result contains unsupported or missing fields")
    require(result["kind"] == "image-test-result", "unsupported image test result")
    _version(result.get("schema_version"), 1, "image test result schema_version")
    require(result["component"] == "image" and result["operation"] == "test" and
            result["phase"] in {"running", "succeeded", "failed", "interrupted", "unknown"},
            "image test result component or phase is invalid")
    require(result["status"] in {"succeeded", "failed", "interrupted", "unknown"}, "image test result status is invalid")
    effects = _mapping(result["effects"], "image test effects")
    require(all(value in {"none", "known", "unknown"} for value in effects.values()),
            "image test effects contain an invalid status")
    verification = result["verification"]
    require(isinstance(verification, list), "image test verification must be a list")
    for observation in verification:
        row = _mapping(observation, "image test verification")
        require(set(row) == {"id", "scope", "status", "evidence_ref"},
                "image test verification observation is incomplete")
        _text(row["id"], "image test verification.id", IDENTIFIER)
        _text(row["scope"], "image test verification.scope", IDENTIFIER)
        require(row["status"] in {"passed", "failed", "not_performed", "unknown"},
                "image test verification status is invalid")
        _safe_relative_path(row["evidence_ref"], "image test verification.evidence_ref", allow_null=True)
    collection = _mapping(result["collection"], "image test collection")
    require(collection.get("status") in {"succeeded", "failed", "unknown", "not_performed"},
            "image test collection status is invalid")
    digest = _text(result["disk_sha256"], "disk_sha256").lower()
    require(SHA256.fullmatch(digest) is not None, "image test disk digest is invalid")
    input_digest = _text(result["input_digest"], "input_digest")
    require(SHA256.fullmatch(input_digest.removeprefix("sha256:")) is not None,
            "image test input digest is invalid")
    runtime_digest = _text(result["runtime_digest"], "runtime_digest")
    require(RUNTIME_DIGEST.fullmatch(runtime_digest) is not None, "image test runtime digest is invalid")
    checks = result["checks"]
    require(isinstance(checks, list), "image test result checks must be a list")
    seen: set[str] = set()
    for item in checks:
        row = _mapping(item, "image test result check")
        require(set(row) <= {"id", "scope", "status", "evidence_ref"}, "image test result check is invalid")
        check_id = _text(row.get("id"), "image test result check.id", IDENTIFIER)
        require(check_id in SUPPORTED_CHECKS and check_id not in seen,
                "image test result check id is invalid or duplicated")
        seen.add(check_id)
        _text(row.get("scope"), "image test result check.scope", IDENTIFIER)
        require(row.get("status") in {"passed", "failed", "not_performed", "unknown"}, "image test result status is invalid")
        require("evidence_ref" in row, "image test result check.evidence_ref is required")
        _safe_relative_path(row["evidence_ref"], "image test result check.evidence_ref", allow_null=True)
    require(result["base_unchanged"] is None or type(result["base_unchanged"]) is bool,
            "image test base_unchanged must be a boolean or null")
    cleanup = _mapping(result["cleanup"], "image test cleanup")
    require(set(cleanup) == {"status", "residue"}, "image test cleanup is incomplete")
    require(cleanup["status"] in {"succeeded", "failed", "unknown", "not_required"}, "image test cleanup status is invalid")
    require(isinstance(cleanup["residue"], list) and all(isinstance(item, str) for item in cleanup["residue"]),
            "image test cleanup residue is invalid")
    return dict(result)


def resolve_artifact_path(root: Path, artifact: Mapping[str, Any]) -> Path:
    validated = validate_artifact(artifact)
    path = (root / validated["disk"]["path"]).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file() and not (root / validated["disk"]["path"]).is_symlink(),
            "artifact path is missing or escapes artifact root")
    return path
