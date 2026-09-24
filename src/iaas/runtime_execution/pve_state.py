"""Read-only S3 state observation and caller-owned admission.

The observer uses only object reads supplied by the selected backend.  It does
not call OpenTofu, create a lock, initialise a workspace, or interpret an
ambiguous failure as an absent object.  Tests and callers provide a small GET
transport, which keeps this module free of an SDK that could silently choose a
different endpoint or credential source.
"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import json
import os
import posixpath
import re
from typing import Any, Mapping, Protocol, TYPE_CHECKING, cast
from urllib.parse import urlsplit

from iaas.common.errors import ValidationError, require

if TYPE_CHECKING:
    from .state import S3Backend


class S3ReadTransport(Protocol):
    """Minimal transport contract; implementations must not expose writes."""

    def get_object(self, *, bucket: str, key: str, region: str, endpoint: str | None = None,
                   config: Mapping[str, Any] | None = None) -> Any: ...


@contextmanager
def _selected_environment(environ: Mapping[str, str]):
    # Runtime operations are sequential. Scope the SDK's standard credential
    # chain to the same mapped environment used by the native backend, then
    # restore the controller environment even if credential resolution fails.
    original = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(environ)
        os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


class BotoS3ReadTransport:
    """Explicit boto3 GET adapter used when the runtime image supplies boto3.

    Importing boto3 lazily keeps offline checks independent of an SDK.  Every
    client option comes from the selected backend; ambient endpoint or profile
    defaults are not consulted by this adapter.
    """

    def __init__(self, environ: Mapping[str, str] | None = None):
        try:
            import boto3.session
            from botocore.config import Config  # type: ignore[import-not-found]
        except ImportError:
            raise ValidationError("read-only S3 observation requires the runtime S3 transport") from None
        self._boto3 = boto3
        self._config_type = Config
        self._environ = dict(environ or {})
        if self._environ.get("AWS_ACCESS_KEY_ID") or self._environ.get("AWS_SECRET_ACCESS_KEY"):
            require(self._environ.get("AWS_ACCESS_KEY_ID") and self._environ.get("AWS_SECRET_ACCESS_KEY"),
                    "S3 observation requires both explicit access key and secret")
        if self._environ.get("AWS_WEB_IDENTITY_TOKEN_FILE") or self._environ.get("AWS_ROLE_ARN"):
            require(self._environ.get("AWS_WEB_IDENTITY_TOKEN_FILE") and self._environ.get("AWS_ROLE_ARN"),
                    "S3 web identity credentials are incomplete")
        require(any(self._environ.get(name) for name in (
            "AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_SHARED_CREDENTIALS_FILE",
            "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN")),
                "S3 observation requires an explicit credential channel")

    def get_object(self, *, bucket: str, key: str, region: str, endpoint: str | None = None,
                   config: Mapping[str, Any] | None = None) -> Any:
        selected = dict(config or {})
        require(not set(selected) & {"assume_role", "assume_role_with_web_identity", "profile", "shared_credentials_files",
                                     "shared_config_files", "custom_ca_bundle", "sse_customer_key"},
                "backend credential or encryption override is unsupported; use mapped AWS inputs")
        path_style = bool(selected.get("use_path_style", selected.get("force_path_style", False)))
        client_config = self._config_type(
            region_name=region,
            signature_version="s3v4", ignore_configured_endpoint_urls=True,
            s3={"addressing_style": "path" if path_style else "auto"},
        )
        with _selected_environment(self._environ):
            session = self._boto3.session.Session(region_name=region)
            ca_bundle = self._environ.get("AWS_CA_BUNDLE")
            client = session.client("s3", endpoint_url=endpoint, config=client_config,
                                    verify=False if selected.get("insecure") is True else ca_bundle or True)
            response = client.get_object(Bucket=bucket, Key=key)
            try:
                return response["Body"].read()
            finally:
                response["Body"].close()


@dataclass(frozen=True)
class StateObservation:
    status: str
    bucket: str
    key: str
    workspace: str
    endpoint: str | None
    lineage: str | None = None
    serial: int | None = None
    empty: bool | None = None
    encrypted: bool = False
    raw: dict[str, Any] | None = None
    reason: str | None = None

    @property
    def present(self) -> bool:
        return self.status == "present"

    def identity(self) -> dict[str, Any]:
        result: dict[str, Any] = {"bucket": self.bucket, "key": self.key, "workspace": self.workspace}
        if self.endpoint:
            result["endpoint"] = self.endpoint
        if self.lineage:
            result["lineage"] = self.lineage
        if self.serial is not None:
            result["serial"] = self.serial
        return result

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        result = {
            "status": self.status,
            "bucket": self.bucket,
            "key": self.key,
            "workspace": self.workspace,
            "endpoint": self.endpoint,
            "lineage": self.lineage,
            "serial": self.serial,
            "empty": self.empty,
            "encrypted": self.encrypted,
            "reason": self.reason,
        }
        if include_raw:
            result["raw"] = self.raw
        return result


def workspace_state_key(config: Mapping[str, Any], workspace: str) -> str:
    """Apply the OpenTofu S3 workspace key rule to a selected backend."""
    require(isinstance(config.get("key"), str) and config["key"], "S3 backend key is required")
    require(isinstance(workspace, str) and re.fullmatch(r"[A-Za-z0-9_-]+", workspace), "invalid workspace")
    if workspace == "default":
        return str(config["key"])
    prefix = config.get("workspace_key_prefix", "env:")
    require(isinstance(prefix, str), "non-default workspace requires workspace_key_prefix")
    return posixpath.normpath("/".join(part for part in (prefix, workspace, config["key"]) if part))


def _backend_values(backend: S3Backend) -> tuple[str, str, str, str | None]:
    config = backend.config
    bucket = config.get("bucket")
    region = config.get("region")
    require(isinstance(bucket, str) and bucket, "S3 bucket is required")
    require(isinstance(region, str) and region, "S3 region is required")
    endpoint = config.get("endpoint")
    endpoints = config.get("endpoints")
    if endpoint is None and isinstance(endpoints, Mapping):
        endpoint = endpoints.get("s3") or endpoints.get("S3")
    if endpoint is not None:
        require(isinstance(endpoint, str) and endpoint, "S3 endpoint must be a nonempty string")
        parsed = urlsplit(endpoint)
        require(parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password,
                "S3 endpoint must be an explicit HTTP(S) URL")
    return cast(str, bucket), workspace_state_key(config, backend.workspace), cast(str, region), cast(str | None, endpoint)


def _error_details(exc: BaseException) -> tuple[int | None, str | None]:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "code", None)
    if not isinstance(status, int):
        response = getattr(exc, "response", None)
        candidate = getattr(response, "status_code", None)
        if candidate is None and isinstance(response, Mapping):
            metadata = response.get("ResponseMetadata", {})
            candidate = metadata.get("HTTPStatusCode") if isinstance(metadata, Mapping) else None
        status = candidate if isinstance(candidate, int) else None
    code = getattr(exc, "error_code", None) or getattr(exc, "code", None)
    response = getattr(exc, "response", None)
    if code is None and isinstance(response, Mapping):
        error = response.get("Error", {})
        candidate = error.get("Code") if isinstance(error, Mapping) else None
        code = candidate if isinstance(candidate, str) else None
    return status, str(code) if isinstance(code, str) else None


def _body(response: Any) -> bytes:
    if isinstance(response, bytes):
        return response
    if isinstance(response, bytearray):
        return bytes(response)
    if isinstance(response, str):
        return response.encode()
    if isinstance(response, Mapping):
        if "Body" in response:
            return _body(response["Body"])
        if "body" in response:
            return _body(response["body"])
        if "lineage" in response and "resources" in response:
            return json.dumps(response).encode()
    reader = getattr(response, "read", None)
    if callable(reader):
        return _body(reader())
    raise ValidationError("S3 state response body is not readable")


class S3StateObserver:
    """Observe one exact S3 object with a caller-selected GET transport."""

    def __init__(self, transport: S3ReadTransport | None = None,
                 *, environ: Mapping[str, str] | None = None):
        self.transport = transport or BotoS3ReadTransport(environ)

    def observe(self, backend: S3Backend) -> StateObservation:
        bucket, key, region, endpoint = _backend_values(backend)
        try:
            response = self.transport.get_object(bucket=bucket, key=key, region=region,
                                                 endpoint=endpoint, config=backend.config)
        except Exception as exc:  # transport adapters classify only known missing-object errors
            status, code = _error_details(exc)
            if code == "NoSuchKey":
                return StateObservation("absent", bucket, key, backend.workspace, endpoint, reason="missing_object")
            reason = "access_denied" if status in {401, 403} or code in {"AccessDenied", "Forbidden"} else "observation_error"
            return StateObservation("error", bucket, key, backend.workspace, endpoint, reason=reason)
        try:
            raw_bytes = _body(response)
            parsed = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            return StateObservation("error", bucket, key, backend.workspace, endpoint, reason="undecodable_state")
        if not isinstance(parsed, dict):
            return StateObservation("error", bucket, key, backend.workspace, endpoint, reason="undecodable_state")
        if parsed.get("encrypted") is True or parsed.get("encryption") not in (None, "none", False):
            return StateObservation("error", bucket, key, backend.workspace, endpoint, encrypted=True,
                                     reason="unsupported_application_encryption")
        lineage = parsed.get("lineage")
        serial = parsed.get("serial")
        resources = parsed.get("resources")
        if parsed.get("version") != 4:
            return StateObservation("error", bucket, key, backend.workspace, endpoint, reason="unsupported_state_format")
        if not isinstance(lineage, str) or not lineage:
            return StateObservation("error", bucket, key, backend.workspace, endpoint, reason="missing_lineage", raw=parsed)
        if type(serial) is not int or serial < 0:
            return StateObservation("error", bucket, key, backend.workspace, endpoint, reason="invalid_serial", raw=parsed)
        if not isinstance(resources, list):
            return StateObservation("error", bucket, key, backend.workspace, endpoint, lineage=lineage, serial=serial,
                                     reason="invalid_resources", raw=parsed)
        return StateObservation("present", bucket, key, backend.workspace, endpoint, lineage=lineage, serial=serial,
                                empty=not resources, raw=parsed)


def validate_state_admission(value: Any) -> dict[str, Any]:
    from .pve_contracts import validate_state_admission_reference

    return validate_state_admission_reference(value)


def _state_resource_vmids(observation: StateObservation) -> set[int]:
    if not observation.raw:
        return set()
    found: set[int] = set()
    for item in observation.raw.get("resources", []):
        if not isinstance(item, Mapping):
            continue
        for instance in item.get("instances", []):
            if not isinstance(instance, Mapping):
                continue
            attributes = instance.get("attributes")
            if isinstance(attributes, Mapping) and type(attributes.get("vm_id")) is int:
                found.add(attributes["vm_id"])
    return found


def admit_state(backend: S3Backend, admission: Mapping[str, Any], observation: StateObservation,
                *, planned_vmids: set[int] | None = None) -> dict[str, Any]:
    """Admit first-use/existing/reconciled-empty without initializing state."""
    checked = validate_state_admission(admission)
    selected_identity = backend.identity()
    declared_identity = checked["backend"]
    for key in ("bucket", "key", "region", "endpoint", "tls_verify", "path_style", "workspace_key_prefix", "use_lockfile"):
        require(declared_identity.get(key) == selected_identity.get(key),
                "state admission backend does not match selected S3 backend")
    require(checked["workspace"] == backend.workspace, "state admission workspace does not match selected S3 backend")
    require(observation.bucket == backend.config["bucket"] and observation.key == workspace_state_key(backend.config, backend.workspace),
            "state observation target does not match selected S3 backend")
    mode = checked["mode"]
    if observation.status == "error":
        raise ValidationError(f"state admission blocked by {observation.reason or 'observation_error'}")
    if mode == "first_use":
        require(observation.status == "absent" or observation.empty is True,
                "first_use requires an absent or confirmed empty state")
        if planned_vmids:
            require(not (_state_resource_vmids(observation) & planned_vmids),
                    "first_use plan conflicts with observed state resources")
    elif mode == "existing":
        require(observation.status == "present", "existing state is missing or unreadable")
        require(observation.lineage == checked.get("lineage"), "existing state lineage conflicts with admission")
    else:
        require(observation.status == "present" and observation.empty is True,
                "reconciled_empty requires a confirmed empty state")
        expected = checked.get("lineage")
        require(observation.lineage == expected, "reconciled_empty state lineage conflicts with reconciliation")
    return {
        "mode": mode,
        "status": observation.status,
        "workspace": backend.workspace,
        "key": observation.key,
        "lineage": observation.lineage,
        "serial": observation.serial,
        "empty": observation.empty,
        "observation": observation.to_dict(),
    }


def extract_state_vmids(observation: StateObservation) -> set[int]:
    """Return only VMIDs explicitly represented by a captured native state."""
    return _state_resource_vmids(observation)


def observe_state(backend: S3Backend, environ: Mapping[str, str] | None = None,
                  transport: S3ReadTransport | None = None) -> StateObservation:
    """Compatibility entrypoint used by the PVE saved-plan lifecycle."""
    return S3StateObserver(transport, environ=environ).observe(backend)
