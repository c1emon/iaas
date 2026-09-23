"""Controller-upload PVE template publisher.

The publisher consumes an already-built image and talks to the PVE HTTPS API
directly. There is deliberately no SSH, node CLI, storage helper or legacy
``action=build`` fallback in this module.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import time
import uuid
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import load_json, write_text
from iaas_automation.runtime_execution.execution import Execution, OperationFailed
from iaas_automation.runtime_execution.pve_contracts import validate_execution_admission
from iaas_automation.runtime_execution.pve_results import template_identity

from .contracts import (
    PUBLISH_PREVIEW_VERSION,
    build_action_preview,
    build_publish_preview,
    canonical_digest,
    validate_cleanup_request,
    validate_publish_preview,
    validate_publish_request,
    validate_retire_request,
    validate_template_record_v2,
)


_UPID_PARTS = 8
_DISK_SLOT = re.compile(r"(?:scsi|virtio|sata|ide)\d+")
_NATIVE_PHASES = frozenset({"upload", "create", "import-config", "template", "remote-cleanup",
                            "cleanup-vm", "cleanup-volume", "retire-template"})


def _disk_slots(config: Mapping[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in config.items()
            if _DISK_SLOT.fullmatch(key)
            and "media=cdrom" not in str(value)
            and "cloudinit" not in str(value)}


_AUX_VOLUME_SLOT = re.compile(r"(?:efidisk|tpmstate|unused)\d+")


def _volume_attachments(config: Mapping[str, Any]) -> dict[str, str]:
    """Return every volume reference attached or retained by a VM config."""
    result: dict[str, str] = {}
    for key, value in config.items():
        if not (_DISK_SLOT.fullmatch(key) or _AUX_VOLUME_SLOT.fullmatch(key)):
            continue
        text = str(value)
        if "media=cdrom" in text:
            continue
        result[key] = _volume_id(text)
    return result


def _volume_id(value: Any) -> str:
    return str(value).split(",", 1)[0]


def _config_uuid(config: Mapping[str, Any]) -> str:
    raw = config.get("smbios1")
    if not isinstance(raw, str) or "uuid=" not in raw:
        return ""
    return raw.split("uuid=", 1)[1].split(",", 1)[0]


def _normalize_upid(value: Any, node: str) -> str:
    require(isinstance(value, str) and value, "PVE task response did not include a UPID")
    prefix = f"/nodes/{quote(node, safe='')}/tasks/"
    if value.startswith("/"):
        require(value.startswith(prefix), "PVE task UPID is bound to another node")
        value = value[len(prefix):]
    parts = value.split(":")
    require(parts[0] == "UPID" and len(parts) >= _UPID_PARTS and parts[1] == node
            and all(parts[index] for index in range(1, min(_UPID_PARTS, len(parts)))),
            "PVE task response did not include a valid UPID")
    return value


def _options(selected: Any) -> dict[str, Any]:
    options = getattr(selected, "options", {})
    require(isinstance(options, Mapping), "pve-template options must be a mapping")
    return dict(options)


def _document(selected: Any, operation: str = "publish") -> dict[str, Any]:
    docs = getattr(selected, "documents", {})
    require(isinstance(docs, Mapping), "pve-template documents must be a mapping")
    names = ("cleanup",) if operation == "cleanup" else ("retire",) if operation == "retire" else ("request", "publish", "recipe")
    for name in names:
        if isinstance(docs.get(name), Mapping):
            value = dict(docs[name])
            if operation in {"cleanup", "retire"}:
                return value
            require(value.get("kind") == "pve-template-publish-request",
                    "legacy combined template build inputs are unsupported; use publish request")
            return value
    raise ValidationError("pve-template requires a pve-template-publish-request input")


def _path(selected: Any, *names: str) -> Path | None:
    files = getattr(selected, "files", {})
    if not isinstance(files, Mapping):
        return None
    for name in names:
        value = files.get(name)
        if value is not None:
            return Path(value)
    return None


def _file_mapping(selected: Any, *names: str) -> dict[str, Any] | None:
    path = _path(selected, *names)
    if path is None:
        return None
    value = load_json(path)
    require(isinstance(value, Mapping), f"{names[0]} must contain a mapping")
    return dict(value)


def _runtime(image_digest: str) -> dict[str, str]:
    require(isinstance(image_digest, str) and image_digest, "pve-template requires a resolved runtime image digest")
    return {"image_digest": image_digest}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise OperationFailed("source locator redirect is not permitted")


class PveHttpsClient:
    """Small API client with a testable request boundary and redacted errors."""

    def __init__(self, endpoint: str, token: str, *, ca_file: str | None = None,
                 tls_verify: bool = True, timeout: float = 30) -> None:
        parsed = urlsplit(endpoint)
        require(parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password,
                "PVE API endpoint must be HTTPS without credentials")
        require(tls_verify is True, "PVE publisher refuses tls_verify=false")
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.context = ssl.create_default_context(cafile=ca_file)
        self.opener = build_opener(_NoRedirect(), ProxyHandler({}), HTTPSHandler(context=self.context))

    def request(self, method: str, path: str, *, fields: Mapping[str, Any] | None = None,
                body: bytes | None = None, content_type: str | None = None) -> Any:
        require(path.startswith("/") and ".." not in path.split("/"), "invalid PVE API path")
        url = self.endpoint + path
        encoded_fields = None
        if fields:
            encoded = urlencode({k: str(v) for k, v in fields.items()}).encode("ascii")
            if method in {"GET", "DELETE"}:
                url += ("&" if "?" in url else "?") + encoded.decode("ascii")
            else:
                encoded_fields = encoded
        headers = {"Authorization": f"PVEAPIToken={self.token}", "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if encoded_fields is not None:
            body = encoded_fields if body is None else body
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self.opener.open(Request(url, data=body, method=method, headers=headers), timeout=self.timeout) as response:
                value = json.loads(response.read().decode("utf-8"))
                return value.get("data", value) if isinstance(value, Mapping) else value
        except HTTPError as exc:
            raise OperationFailed(f"PVE API {method} request failed (HTTP {exc.code})") from None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError):
            raise OperationFailed(f"PVE API {method} request failed; inspect protected recovery material") from None

    def upload_file(self, upload_path: str, path: Path, filename: str, checksum: str) -> Any:
        parsed = urlsplit(self.endpoint)
        if parsed.hostname is None:
            raise ValidationError("PVE API endpoint requires a hostname")
        require(upload_path.startswith("/") and ".." not in upload_path.split("/"), "invalid PVE upload path")
        boundary = "iaas-" + hashlib.sha256(filename.encode()).hexdigest()[:24]
        def field(name: str, value: str) -> bytes:
            return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode()
        prefix = field("content", "import") + field("checksum-algorithm", "sha256") + field("checksum", checksum)
        prefix += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"filename\"; filename=\"{filename}\"\r\n"
                   "Content-Type: application/octet-stream\r\n\r\n").encode()
        suffix = f"\r\n--{boundary}--\r\n".encode()
        target = upload_path
        connection: http.client.HTTPSConnection | None = None
        try:
            connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443,
                                                      context=self.context, timeout=self.timeout)
            connection.putrequest("POST", target, skip_accept_encoding=True)
            connection.putheader("Authorization", f"PVEAPIToken={self.token}")
            connection.putheader("Accept", "application/json")
            connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            connection.putheader("Content-Length", str(len(prefix) + path.stat().st_size + len(suffix)))
            connection.endheaders()
            connection.send(prefix)
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    connection.send(chunk)
            connection.send(suffix)
            response = connection.getresponse()
            if response.status >= 300:
                raise OperationFailed(f"PVE API upload request failed (HTTP {response.status})")
            value = json.loads(response.read().decode("utf-8"))
            return value.get("data", value) if isinstance(value, Mapping) else value
        except OperationFailed:
            raise
        except TimeoutError:
            raise OperationFailed("PVE API upload request failed (timeout)") from None
        except OSError as exc:
            category = f"os-error-{exc.errno}" if exc.errno is not None else "os-error"
            raise OperationFailed(f"PVE API upload request failed ({category})") from None
        except http.client.HTTPException:
            raise OperationFailed("PVE API upload request failed (http-error)") from None
        except json.JSONDecodeError:
            raise OperationFailed("PVE API upload request failed (invalid-response)") from None
        finally:
            if connection is not None:
                connection.close()


def _client(selected: Any, execution: Execution, target: Mapping[str, Any]) -> PveHttpsClient:
    token = execution.environ.get("PVE_API_TOKEN", "")
    require(token and "!" in token, "pve-template requires operation-scoped PVE_API_TOKEN")
    return PveHttpsClient(target["api_endpoint"], token, ca_file=execution.environ.get("PVE_API_CA") or None,
                          tls_verify=bool(target["tls_verify"]))


def _observed(selected: Any, client: PveHttpsClient | None, target: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    if client is None:
        raise ValidationError("PVE observation requires an HTTPS client")
    node = quote(str(target["node"]), safe="")
    _assert_vmid_visibility(client, request["vmid"])
    storage_permissions: dict[str, set[str]] = {}
    storage_permissions.setdefault(request["staging_storage"], set()).update(
        {"Datastore.Audit", "Datastore.AllocateTemplate"})
    storage_permissions.setdefault(request["disk_storage"], set()).add("Datastore.AllocateSpace")
    for storage, permissions in storage_permissions.items():
        _assert_storage_permissions(client, storage, permissions)
    resources = client.request("GET", "/api2/json/cluster/resources", fields={"type": "vm"})
    storages = client.request("GET", f"/api2/json/nodes/{node}/storage")
    require(isinstance(resources, list) and all(isinstance(item, Mapping) for item in resources)
            and isinstance(storages, list), "PVE observation response is invalid")
    require(not any(isinstance(item, Mapping) and item.get("vmid") == request["vmid"] for item in resources),
            "selected template VMID is occupied; force replacement is unsupported")
    needed = {request["staging_storage"], request["disk_storage"], request["cloud_init_storage"]}
    if request["hardware"]["firmware"] == "uefi":
        needed.add(request["efi_storage"])
    by_name = {str(item.get("storage")): item for item in storages if isinstance(item, Mapping)}
    capacities: dict[str, Any] = {}
    for name in needed:
        row = by_name.get(name)
        if not isinstance(row, Mapping):
            raise ValidationError(f"PVE storage {name} is not visible")
        require(row.get("enabled") in (1, True, "1") and row.get("active") in (1, True, "1"),
                f"PVE storage {name} is not active")
        available = row.get("avail")
        needed_bytes = 0
        if name == request["staging_storage"]:
            needed_bytes += request["artifact"]["disk"]["size_bytes"]
        if name == request["disk_storage"]:
            needed_bytes += request["artifact"]["disk"]["virtual_size_bytes"]
        if type(available) is int:
            # EFI/cloud-init allocation is not the artifact's download size.
            # Check known capacity only, leaving unreported allocation details
            # to the native storage operation.
            needed_bytes = max(1, needed_bytes)
            require(available >= needed_bytes, f"PVE storage {name} has insufficient known capacity")
        content = [item for item in str(row.get("content", "")).split(",") if item]
        required_content = {"import"} if name == request["staging_storage"] else set()
        if name in {request["disk_storage"], request["cloud_init_storage"]}:
            required_content.add("images")
        if request["hardware"]["firmware"] == "uefi" and name == request.get("efi_storage"):
            required_content.add("images")
        if not required_content <= set(content):
            missing = ", ".join(sorted(required_content - set(content)))
            raise ValidationError(f"PVE storage {name} does not support {missing} content")
        capacities[name] = {"content": content, "avail": available, "known_required_bytes": needed_bytes,
                            "required_content": sorted(required_content)}
    return {"vmid_free": True, "storages": capacities, "receiving_temp": "unobserved", "proxy_limits": "unobserved"}


def _source_locator(execution: Execution, request: Mapping[str, Any]) -> str:
    value = execution.environ.get("PVE_ARTIFACT_URL", "")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password,
            "PVE_ARTIFACT_URL must be a protected HTTPS locator")
    source_ref = request["source"]["object_ref"]
    # A stable HTTPS object reference is itself the locator.  An S3 reference
    # is deliberately kept separate from the short-lived HTTPS locator; the
    # caller's admission binds that reissued locator to the selected object.
    if source_ref.startswith("https://"):
        require(value.rstrip("/") == source_ref.rstrip("/"),
                "PVE_ARTIFACT_URL does not match the fixed publication source")
    return value


def _download(locator: str, destination: Path, expected_digest: str, expected_size: int) -> None:
    digest = hashlib.sha256()
    try:
        opener = build_opener(_NoRedirect(), ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()))
        total = 0
        with opener.open(Request(locator, headers={"Accept": "application/octet-stream"}), timeout=120) as source, destination.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > expected_size:
                    raise OperationFailed("artifact exceeds the selected byte bound")
                digest.update(chunk)
                output.write(chunk)
    except HTTPError as exc:
        destination.unlink(missing_ok=True)
        raise OperationFailed(f"artifact download failed (HTTP {exc.code})") from None
    except URLError:
        destination.unlink(missing_ok=True)
        raise OperationFailed("artifact download failed (url-error)") from None
    except TimeoutError:
        destination.unlink(missing_ok=True)
        raise OperationFailed("artifact download failed (timeout)") from None
    except OSError as exc:
        destination.unlink(missing_ok=True)
        category = f"os-error-{exc.errno}" if exc.errno is not None else "os-error"
        raise OperationFailed(f"artifact download failed ({category})") from None
    except OperationFailed:
        destination.unlink(missing_ok=True)
        raise OperationFailed("artifact download failed; inspect protected recovery material") from None
    if destination.stat().st_size != expected_size or digest.hexdigest() != expected_digest:
        destination.unlink(missing_ok=True)
        raise OperationFailed("downloaded artifact does not match selected digest or size")


def _verify_qcow2(path: Path, artifact: Mapping[str, Any]) -> None:
    qemu_img = shutil.which("qemu-img")
    if qemu_img is None:
        raise OperationFailed("qemu-img is unavailable for artifact format verification")
    try:
        completed = subprocess.run([qemu_img, "info", "--output=json", str(path)],
                                   capture_output=True, text=True, check=False, timeout=30)
        info = json.loads(completed.stdout) if completed.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        raise OperationFailed("artifact format verification failed; inspect protected recovery material") from None
    require(isinstance(info, Mapping) and info.get("format") == "qcow2" and
            info.get("backing-filename") in (None, "") and
            info.get("virtual-size") == artifact["disk"]["virtual_size_bytes"],
            "artifact is not a self-contained qcow2 with the selected virtual size")


def _phase_failure_reason(phase: str, error: Exception) -> str:
    """Return a bounded diagnostic category without copying exception text."""
    if phase == "artifact-verify":
        if isinstance(error, OperationFailed) and "unavailable" in str(error):
            return "qemu-img-unavailable"
        return "artifact-format-verification-failed"
    if phase == "upload-target":
        if isinstance(error, ValidationError):
            return "upload-target-rejected"
        return "upload-target-observation-failed"
    if phase == "upload":
        message = str(error)
        http_status = re.search(r"\bHTTP ([1-5][0-9]{2})\b", message)
        if http_status is not None:
            return f"upload-http-{http_status.group(1)}"
        os_error = re.search(r"\bos-error-([0-9]+)\b", message)
        if os_error is not None:
            return f"upload-os-error-{os_error.group(1)}"
        if "timeout" in message.lower():
            return "upload-timeout"
        return "upload-request-failed"
    return "publication-phase-failed"


def _upid(client: PveHttpsClient, value: Any, phase: str, *, node: str = "localhost", timeout: float = 300) -> dict[str, Any]:
    upid = _normalize_upid(value, node)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        path = f"/api2/json/nodes/{quote(node, safe='')}/tasks/{quote(upid, safe='')}/status"
        row = client.request("GET", path)
        if isinstance(row, Mapping) and row.get("status") == "stopped":
            require(row.get("exitstatus") == "OK", f"PVE {phase} task did not finish successfully")
            return {"phase": phase, "status": "succeeded", "upid": upid}
        time.sleep(0.2)
    raise OperationFailed(f"PVE {phase} task observation timed out; execution remains unknown")


def _record_from_config(request: Mapping[str, Any], config: Mapping[str, Any], execution_id: str,
                        *, complete: bool = True) -> dict[str, Any]:
    identity = template_identity(dict(config)) if complete else None
    disks = identity["disks"] if identity is not None else _disk_slots(config)
    uuid = identity["smbios_uuid"] if identity is not None else _config_uuid(config)
    record = {"kind": "pve-template-record", "schema_version": 2,
              "record_id": f"{request['version']}-{request['vmid']}", "target": request["target"],
              "node": request["target"]["node"], "vmid": request["vmid"], "smbios_uuid": uuid,
              "volumes": disks, "configuration": dict(config), "origin": "publication",
              "execution_id": execution_id, "artifact_digest": request["artifact_digest"],
              "verification": {"template_config": "passed", "guest_acceptance": "not_performed",
                                "caller_promotion": "caller_owned"}}
    return validate_template_record_v2(record, complete=complete)


def _write_intent(path: Path, intent: Mapping[str, Any]) -> None:
    write_text(path, json.dumps(intent, sort_keys=True, indent=2) + "\n", secure=True)
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _failure_result(intent: Mapping[str, Any], execution_id: str, preview_digest: str,
                    artifact_digest: str) -> dict[str, Any]:
    events = intent.get("events", [])
    # A download intent is local preparation only; it cannot imply a remote
    # effect.  Only native upload/create/config/template/cleanup phases can
    # make the publication outcome unknown.
    submitted = any(isinstance(event, Mapping) and event.get("phase") in _NATIVE_PHASES
                    and event.get("status") in {"intent", "submitted", "unknown"} for event in events)
    residue = [str(item) for item in intent.get("residue", []) if isinstance(item, str)]
    action = intent.get("action", "publish")
    result = {"kind": "pve-template-result", "schema_version": 2, "execution_id": execution_id,
            "component": "pve-template", "operation": "apply", "action": action,
            "runtime_digest": intent.get("runtime_digest", "unknown"), "phase": "unknown" if submitted else "failed",
            "status": "unknown" if submitted else "failed", "effects": {"pve": "unknown" if submitted else "none",
            "staging": "unknown" if submitted else "none"}, "preview_digest": preview_digest,
            "publication": "unknown" if action == "publish" and submitted else
            "failed" if action == "publish" else "not_applicable",
            "verification": [{"id": "native-task", "scope": "pve-api", "status": "unknown" if submitted else "not_performed",
                              "evidence_ref": None}], "collection": {"status": "succeeded"},
            "native_execution": events, "cleanup": {"status": "unknown" if submitted else "not_required",
            "residue": residue}}
    if action in {"cleanup", "retire"} and isinstance(intent.get("original_execution_id"), str):
        result["recovery_of"] = intent["original_execution_id"]
    if action == "publish":
        result["artifact_digest"] = artifact_digest
    return result


def _storage_content(client: PveHttpsClient, node: str, storage: str) -> list[Mapping[str, Any]]:
    # PVE accepts one content enum value per request; an apparently natural
    # comma-separated filter is rejected with HTTP 400.  The unfiltered
    # listing is bounded to this storage path, and callers select the exact
    # volid they own locally.
    value = client.request("GET", f"/api2/json/nodes/{quote(node, safe='')}/storage/{quote(storage, safe='')}/content")
    require(isinstance(value, list) and all(isinstance(item, Mapping) for item in value),
            "PVE storage content observation is incomplete")
    return list(value)


def _assert_upload_target_free(client: PveHttpsClient, node: str, storage: str, volid: str) -> None:
    content = _storage_content(client, node, storage)
    require(not any(item.get("volid") == volid for item in content),
            "publisher upload volume identity is already present")


def _assert_vmid_free(client: PveHttpsClient, vmid: int) -> None:
    _assert_vmid_visibility(client, vmid)
    resources = client.request("GET", "/api2/json/cluster/resources", fields={"type": "vm"})
    require(isinstance(resources, list) and all(isinstance(item, Mapping) for item in resources),
            "PVE VMID observation is incomplete")
    require(not any(item.get("vmid") == vmid for item in resources),
            "selected template VMID is occupied; force replacement is unsupported")


def _assert_vmid_visibility(client: PveHttpsClient, vmid: int) -> None:
    permissions = client.request("GET", "/api2/json/access/permissions",
                                 fields={"path": f"/vms/{vmid}"})
    grants = permissions.get(f"/vms/{vmid}") if isinstance(permissions, Mapping) else None
    require(isinstance(grants, Mapping) and type(grants.get("VM.Audit")) in {int, bool}
            and grants["VM.Audit"] in (0, 1),
            "PVE VMID observation requires effective VM.Audit on the selected VMID")


def _assert_storage_permissions(client: PveHttpsClient, storage: str, required: set[str]) -> None:
    path = f"/storage/{quote(storage, safe='')}"
    permissions = client.request("GET", "/api2/json/access/permissions", fields={"path": path})
    grants = permissions.get(path) if isinstance(permissions, Mapping) else None
    if not isinstance(grants, Mapping):
        raise ValidationError(f"PVE storage permissions are missing for {storage}")
    for permission in sorted(required):
        value = grants.get(permission)
        require(type(value) in {int, bool} and value in (0, 1),
                f"PVE storage permission {permission} has invalid value")
        require(value == 1, f"PVE storage permission {permission} is not granted")


def _assert_upload_absent(client: PveHttpsClient, node: str, storage: str, volid: str) -> None:
    content = _storage_content(client, node, storage)
    require(not any(item.get("volid") == volid for item in content),
            "PVE staging deletion was not confirmed")


def _final_disk(config: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[str, str]:
    candidates = {slot: _volume_id(value) for slot, value in _disk_slots(config).items()
                  if _volume_id(value).startswith(request["disk_storage"] + ":")
                  and "import-from=" not in str(value)
                  and "cloudinit" not in str(value)}
    boot_disk = request["hardware"]["boot_disk"]
    require(boot_disk in candidates, "PVE imported VM has no completed volume in the requested boot slot")
    return boot_disk, candidates[boot_disk]


def _verify_requested_config(config: Mapping[str, Any], request: Mapping[str, Any]) -> None:
    hardware, defaults = request["hardware"], request["cloud_init_defaults"]
    expected = {"name": request["name"], "cores": hardware["cpus"], "memory": hardware["memory_mib"],
                "machine": hardware["machine"], "scsihw": hardware["scsi_controller"],
                "boot": f"order={hardware['boot_disk']}"}
    require(all(str(config.get(key)) == str(value) for key, value in expected.items()),
            "PVE template configuration does not match the fixed publication request")
    network = str(config.get("net0", "")).split(",")
    require(network[0].split("=", 1)[0] == "virtio" and f"bridge={hardware['bridge']}" in network,
            "PVE template network does not match the fixed publication request")
    agent = str(config.get("agent", "")).split(",")
    require("1" in agent or "enabled=1" in agent, "PVE template guest agent configuration is missing")
    require(config.get("bios", "seabios") == ("ovmf" if hardware["firmware"] == "uefi" else "seabios"),
            "PVE template firmware does not match the fixed publication request")
    if hardware["firmware"] == "uefi":
        require(str(config.get("efidisk0", "")).startswith(request["efi_storage"] + ":"),
                "PVE template EFI disk does not match the fixed publication request")
    if "user" in defaults:
        require(config.get("ciuser") == defaults["user"], "PVE cloud-init user does not match the fixed request")
    if "ip_config" in defaults:
        require(set(str(config.get("ipconfig0", "")).split(",")) == set(defaults["ip_config"].split(",")),
                "PVE cloud-init network defaults do not match the fixed request")
    if "ssh_keys" in defaults:
        actual_keys = [line.strip() for line in unquote(str(config.get("sshkeys", ""))).splitlines() if line.strip()]
        require(actual_keys == [line.strip() for line in defaults["ssh_keys"]],
                "PVE cloud-init SSH keys do not match the fixed request")


def _admitted_object_volumes(item: Mapping[str, Any]) -> dict[str, str]:
    raw = item.get("volumes", item.get("disks"))
    require(isinstance(raw, Mapping), "cleanup object volume ownership is missing")
    result = {str(slot): _volume_id(value) for slot, value in raw.items()
              if isinstance(slot, str) and isinstance(value, str)}
    require(len(result) == len(raw), "cleanup object volume ownership is invalid")
    return result


def _cleanup_volume_identity(value: Any) -> tuple[str, str]:
    if isinstance(value, str):
        storage, separator, _ = value.partition(":")
        volid = value
    else:
        require(isinstance(value, Mapping), "cleanup volume identity is invalid")
        volid = value.get("volid", value.get("volume"))
        storage = value.get("storage")
        require(isinstance(volid, str) and isinstance(storage, str),
                "cleanup volume identity is incomplete")
        separator = ":" if ":" in volid else ""
    require(isinstance(storage, str) and storage and separator and volid.startswith(storage + ":"),
            "cleanup volume storage does not match volid")
    return storage, volid


def _original_publish_evidence(selected: Any, fixed: Mapping[str, Any]) -> dict[str, Any]:
    directory = _path(selected, "original_execution_dir")
    if directory is None or not directory.is_dir():
        raise ValidationError("cleanup requires the original execution directory")
    journal_path = directory / "diagnostics" / "publish-intent.json"
    require(journal_path.is_file(), "cleanup requires the original publish journal")
    journal = load_json(journal_path)
    if not isinstance(journal, Mapping) or journal.get("kind") != "pve-template-publish-intent":
        raise ValidationError("original publish journal is invalid")
    require(journal.get("execution_id") == fixed["original_execution_id"] and
            journal.get("preview_digest") == fixed["original_preview_digest"],
            "cleanup does not match the original execution or preview")
    require(journal.get("target") == fixed["target"],
            "cleanup target does not match the original publish journal")
    result: Mapping[str, Any] | None = None
    result_path = directory / "diagnostics" / "result.json"
    if result_path.is_file():
        value = load_json(result_path)
        if not isinstance(value, Mapping):
            raise ValidationError("original publish result is invalid")
        result = value
        require(result.get("execution_id") == fixed["original_execution_id"] and
                result.get("preview_digest") == fixed["original_preview_digest"],
                "cleanup does not match the original publish result")
        record = result.get("template_record")
        if isinstance(record, Mapping) and isinstance(record.get("target"), Mapping):
            require(record["target"] == fixed["target"],
                    "cleanup target does not match the original template record")

    record = result.get("template_record") if isinstance(result, Mapping) else None
    events_value = journal.get("events")
    if not isinstance(events_value, list):
        raise ValidationError("original publish journal events are missing")
    events = events_value
    created = next((event for event in reversed(events)
                    if isinstance(event, Mapping) and event.get("phase") == "create"
                    and event.get("status") == "succeeded"), None)
    templated = next((event for event in reversed(events)
                      if isinstance(event, Mapping) and event.get("phase") == "template"
                      and event.get("status") in {"succeeded", "submitted", "failed", "unknown"}), None)
    journal_objects: list[dict[str, Any]] = []
    if isinstance(created, Mapping):
        volumes: dict[str, str] = {}
        attachment_event = templated if isinstance(templated, Mapping) else created
        if isinstance(attachment_event, Mapping):
            attachments = attachment_event.get("attachments")
            if isinstance(attachments, Mapping):
                for slot, value in attachments.items():
                    if not isinstance(slot, str) or not isinstance(value, str):
                        raise ValidationError("original publish journal volume attachments are invalid")
                    volumes[slot] = _volume_id(value)
            elif isinstance(templated, Mapping):
                slot = templated.get("disk_slot", journal.get("boot_disk"))
                volume = templated.get("final_volume", templated.get("imported_volume"))
                require(isinstance(slot, str) and isinstance(volume, str),
                        "original publish journal lacks complete VM volume identity")
                volumes = {slot: volume}
        require(type(journal.get("vmid")) is int and isinstance(created.get("smbios_uuid"), str),
                "original publish journal lacks complete VM identity")
        journal_objects.append({"vmid": journal["vmid"], "smbios_uuid": created["smbios_uuid"],
                                "volumes": volumes})
    if isinstance(record, Mapping):
        validate_template_record_v2(record, complete=False)
        record_object = {"vmid": record["vmid"], "smbios_uuid": record["smbios_uuid"],
                         "volumes": _admitted_object_volumes(record)}
        journal_object = journal_objects[0] if journal_objects else None
        require(journal_object is not None and record_object["vmid"] == journal_object["vmid"] and
                record_object["smbios_uuid"] == journal_object["smbios_uuid"] and
                all(journal_object["volumes"].get(slot) == volume
                    for slot, volume in record_object["volumes"].items()),
                "original template result is not bound to the publish journal")

    upload_volid = journal.get("upload_volid")
    require(isinstance(upload_volid, str), "original publish journal lacks upload volume identity")
    journal_volumes = {upload_volid}
    for item in journal_objects:
        journal_volumes.update(item["volumes"].values())
    return {"journal": dict(journal), "result": result, "objects": journal_objects,
            "volumes": journal_volumes, "upload_volid": upload_volid, "completed": False}


def _observe_original_tasks(client: PveHttpsClient, journal: Mapping[str, Any], node: str) -> dict[str, str]:
    events_value = journal.get("events")
    if not isinstance(events_value, list) or not events_value:
        raise ValidationError("original publish journal task history is missing")
    events = events_value
    history: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        require(isinstance(event, Mapping) and isinstance(event.get("phase"), str),
                "original publish journal event is invalid")
        history.setdefault(event["phase"], []).append(event)
    outcomes: dict[str, str] = {}
    local_phases = {"download", "artifact-verify", "upload-target", "local-cleanup"}
    for phase, entries in history.items():
        if phase in local_phases:
            continue
        event = entries[-1]
        status = event.get("status")
        if status == "intent":
            raise ValidationError(f"original PVE {phase} task activity is unknown")
        if status not in {"submitted", "unknown", "succeeded", "failed"}:
            raise ValidationError(f"original PVE {phase} task status is invalid")
        known_upids = [item["upid"] for item in entries if isinstance(item.get("upid"), str)]
        upid = known_upids[-1] if known_upids else None
        if status in {"submitted", "succeeded"}:
            require(isinstance(upid, str), f"original PVE {phase} task UPID is missing")
        if status == "unknown" and upid is None and any(item.get("status") == "intent" for item in entries):
            raise ValidationError(f"original PVE {phase} task activity is unknown")
        if not isinstance(upid, str):
            continue
        normalized = _normalize_upid(upid, node)
        path = f"/api2/json/nodes/{quote(node, safe='')}/tasks/{quote(normalized, safe='')}/status"
        observed = client.request("GET", path)
        require(isinstance(observed, Mapping) and observed.get("status") == "stopped",
                f"original PVE {phase} task is still active or unknown")
        exitstatus = observed.get("exitstatus")
        if not isinstance(exitstatus, str) or not exitstatus:
            raise ValidationError(f"original PVE {phase} task exit status is unknown")
        outcomes[phase] = exitstatus
    return outcomes


def _publish(selected: Any, execution: Execution, request: Mapping[str, Any], preview: Mapping[str, Any], execution_id: str) -> dict[str, Any]:
    client = _client(selected, execution, request["target"])
    artifact = request["artifact"]
    work = execution.outputs.path("work") / "publisher"
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    disk = work / f"{execution_id}-{artifact['disk']['sha256']}.qcow2"
    upload_volid = f"{request['staging_storage']}:import/{disk.name}"
    node_name = request["target"]["node"]
    node = quote(node_name, safe="")
    boot_disk = request["hardware"]["boot_disk"]
    intent_path = execution.outputs.path("diagnostics") / "publish-intent.json"
    intent: dict[str, Any] = {
        "kind": "pve-template-publish-intent", "schema_version": 1,
        "execution_id": execution_id, "preview_digest": preview["preview_digest"],
        "target": dict(request["target"]),
        "runtime_digest": preview["runtime"]["image_digest"],
        "artifact_digest": request["artifact_digest"], "vmid": request["vmid"],
        "upload_volid": upload_volid, "boot_disk": boot_disk, "events": [], "residue": [],
    }
    _write_intent(intent_path, intent)

    def journal(phase: str, status: str, **values: Any) -> None:
        event = {"phase": phase, "status": status, **values}
        intent["events"].append(event)
        _write_intent(intent_path, intent)

    try:
        intent["observed"] = _observed(selected, client, request["target"], request)
        try:
            local_available = shutil.disk_usage(work).free
        except OSError:
            local_available = None
        intent["local_available_bytes"] = local_available
        _write_intent(intent_path, intent)
        require(local_available is None or local_available >= artifact["disk"]["size_bytes"],
                "publisher workspace has insufficient known capacity")
        journal("download", "intent", expected_bytes=artifact["disk"]["size_bytes"])
        try:
            _download(_source_locator(execution, request), disk, artifact["disk"]["sha256"], artifact["disk"]["size_bytes"])
        except OperationFailed as exc:
            # Keep only the bounded category/status in the protected journal;
            # never persist the locator, credentials, or native URL text.
            journal("download", "failed", reason=str(exc))
            raise
        journal("download", "succeeded", bytes=artifact["disk"]["size_bytes"])
        journal("artifact-verify", "intent")
        try:
            _verify_qcow2(disk, artifact)
        except Exception as exc:
            journal("artifact-verify", "failed", reason=_phase_failure_reason("artifact-verify", exc))
            raise
        journal("artifact-verify", "succeeded")
        journal("upload-target", "intent", volid=upload_volid)
        try:
            _assert_upload_target_free(client, node_name, request["staging_storage"], upload_volid)
        except Exception as exc:
            journal("upload-target", "failed", reason=_phase_failure_reason("upload-target", exc))
            raise
        journal("upload-target", "succeeded", volid=upload_volid)
        journal("upload", "intent", volid=upload_volid)
        try:
            upload = client.upload_file(
                f"/api2/json/nodes/{node}/storage/{quote(request['staging_storage'], safe='')}/upload",
                disk, disk.name, artifact["disk"]["sha256"])
        except Exception as exc:
            journal("upload", "failed", reason=_phase_failure_reason("upload", exc), volid=upload_volid)
            raise
        journal("upload", "submitted", upid=upload, volid=upload_volid)
        upload_result = _upid(client, upload, "upload", node=node_name)
        journal("upload", "succeeded", upid=upload_result.get("upid"), volid=upload_volid)

        vmid = request["vmid"]
        created_uuid = str(uuid.uuid4())
        _assert_vmid_free(client, vmid)
        create_fields: dict[str, Any] = {"vmid": vmid, "name": request["name"],
            "cores": request["hardware"]["cpus"], "memory": request["hardware"]["memory_mib"],
            "machine": request["hardware"]["machine"], "scsihw": request["hardware"]["scsi_controller"],
            "net0": f"virtio,bridge={request['hardware']['bridge']}",
            "smbios1": f"uuid={created_uuid}"}
        if request["hardware"]["firmware"] == "uefi":
            create_fields.update(bios="ovmf", efidisk0=f"{request['efi_storage']}:0,efitype=4m,format=raw")
        journal("create", "intent", vmid=vmid, smbios_uuid=created_uuid)
        create = client.request("POST", f"/api2/json/nodes/{node}/qemu", fields=create_fields)
        journal("create", "submitted", upid=create)
        create_result = _upid(client, create, "create", node=node_name)
        created_config = client.request("GET", f"/api2/json/nodes/{node}/qemu/{vmid}/config")
        require(isinstance(created_config, Mapping), "PVE created VM configuration is invalid")
        observed_uuid = _config_uuid(created_config)
        require(observed_uuid == created_uuid, "PVE created VM UUID does not match the fixed identity")
        journal("create", "succeeded", upid=create_result.get("upid"), smbios_uuid=created_uuid,
                attachments=_volume_attachments(created_config))

        config_fields: dict[str, Any] = {
            boot_disk: f"{request['disk_storage']}:0,import-from={upload_volid}",
            "boot": f"order={boot_disk}", "agent": 1,
            "machine": request["hardware"]["machine"],
            "ide2": f"{request['cloud_init_storage']}:cloudinit",
        }
        defaults = request["cloud_init_defaults"]
        if isinstance(defaults.get("user"), str):
            config_fields["ciuser"] = defaults["user"]
        if isinstance(defaults.get("ip_config"), str):
            config_fields["ipconfig0"] = defaults["ip_config"]
        if isinstance(defaults.get("ssh_keys"), list):
            config_fields["sshkeys"] = quote("\n".join(defaults["ssh_keys"]), safe="")
        journal("import-config", "intent", vmid=vmid, source=upload_volid)
        configured = client.request("POST", f"/api2/json/nodes/{node}/qemu/{vmid}/config", fields=config_fields)
        journal("import-config", "submitted", upid=configured, source=upload_volid)
        config_result = _upid(client, configured, "import-config", node=node_name)
        journal("import-config", "succeeded", upid=config_result.get("upid"), source=upload_volid)

        imported_config = client.request("GET", f"/api2/json/nodes/{node}/qemu/{vmid}/config")
        require(isinstance(imported_config, Mapping), "PVE imported VM configuration is invalid")
        require(_config_uuid(imported_config) == created_uuid,
                "PVE imported VM UUID differs from the created VM identity")
        imported_disk, imported_volume = _final_disk(imported_config, request)

        imported_attachments = _volume_attachments(imported_config)
        journal("template", "intent", vmid=vmid, imported_volume=imported_volume,
                disk_slot=imported_disk, attachments=imported_attachments)
        templated = client.request("POST", f"/api2/json/nodes/{node}/qemu/{vmid}/template")
        journal("template", "submitted", upid=templated, imported_volume=imported_volume,
                disk_slot=imported_disk, attachments=imported_attachments)
        template_result = _upid(client, templated, "template", node=node_name)
        current = client.request("GET", f"/api2/json/nodes/{node}/qemu/{vmid}/config")
        require(isinstance(current, Mapping) and _config_uuid(current) == created_uuid and
                current.get("template") in (1, True, "1") and
                isinstance(current.get("ide2"), str) and current["ide2"].startswith(request["cloud_init_storage"] + ":"),
                "PVE template flag/configuration verification failed")
        final_disk, final_volume = _final_disk(current, request)
        _verify_requested_config(current, request)
        journal("template", "succeeded", upid=template_result.get("upid"), imported_volume=imported_volume,
                final_volume=final_volume, disk_slot=final_disk, smbios_uuid=created_uuid,
                attachments=_volume_attachments(current))
        record = _record_from_config(request, current, execution_id)

        cleanup_status = "succeeded"
        cleanup_residue: list[str] = []
        try:
            content = _storage_content(client, node_name, request["staging_storage"])
            present = any(item.get("volid") == upload_volid for item in content)
            if present:
                journal("remote-cleanup", "intent", volid=upload_volid)
                deleted = client.request("DELETE", f"/api2/json/nodes/{node}/storage/{quote(request['staging_storage'], safe='')}/content/{quote(upload_volid, safe='')}")
                journal("remote-cleanup", "submitted", upid=deleted, volid=upload_volid)
                deleted_result = _upid(client, deleted, "remote-cleanup", node=node_name)
                _assert_upload_absent(client, node_name, request["staging_storage"], upload_volid)
                journal("remote-cleanup", "succeeded", upid=deleted_result.get("upid"), volid=upload_volid,
                        verified_absent=True)
        except (OperationFailed, ValidationError):
            cleanup_status = "unknown"
            cleanup_residue.append(upload_volid)
            intent["residue"] = cleanup_residue
            journal("remote-cleanup", "unknown", volid=upload_volid)
        try:
            journal("local-cleanup", "intent", path=disk.name)
            disk.unlink()
            journal("local-cleanup", "succeeded", path=disk.name)
        except FileNotFoundError:
            journal("local-cleanup", "succeeded", path=disk.name, already_absent=True)
        except OSError:
            if cleanup_status != "unknown":
                cleanup_status = "failed"
            cleanup_residue.append(disk.name)
        if cleanup_residue:
            intent["residue"] = cleanup_residue
            _write_intent(intent_path, intent)
        cleanup: dict[str, Any] = {"status": cleanup_status, "residue": cleanup_residue}
        if cleanup_status != "succeeded":
            cleanup.update(scope="staging-only", inactive=cleanup_status == "failed", objects=[],
                           todo={"original_execution_id": execution_id, "resources": cleanup_residue},
                           warning="publisher-owned staging residue requires a new cleanup action")
        verification = [
            {"id": "template-config", "scope": "pve-api-config", "status": "passed", "evidence_ref": None},
            {"id": "guest-acceptance", "scope": "caller", "status": "not_performed", "evidence_ref": None},
        ]
        # The template conversion and its configuration are already confirmed.
        # An unresolved cleanup must keep the execution pending without erasing
        # that known publication result.
        outcome = "unknown" if cleanup_status == "unknown" else "succeeded"
        intent["status"] = outcome
        _write_intent(intent_path, intent)
        return {"kind": "pve-template-result", "schema_version": 2, "execution_id": execution_id,
                "component": "pve-template", "operation": "apply", "action": "publish",
                "runtime_digest": preview["runtime"]["image_digest"],
                "phase": outcome, "status": outcome,
                "effects": {"pve": "known", "staging": "unknown" if cleanup_status == "unknown" else "known"},
                "preview_digest": preview["preview_digest"], "artifact_digest": request["artifact_digest"],
                "publication": "succeeded", "verification": verification, "collection": {"status": "succeeded"},
                "native_execution": {"upload": upload_result, "create": create_result,
                                      "import_config": config_result, "template": template_result},
                "template_record": record, "cleanup": cleanup}
    except Exception:
        intent["status"] = "unknown" if any(event.get("phase") in _NATIVE_PHASES
                                              and event.get("status") in {"intent", "submitted", "unknown"}
                                              for event in intent["events"]) else "failed"
        _write_intent(intent_path, intent)
        raise


def _delete_action(selected: Any, execution: Execution, request: Mapping[str, Any],
                  preview: Mapping[str, Any], execution_id: str) -> dict[str, Any]:
    """Delete only the exact publisher-owned resources in an admitted action."""
    fixed = preview["fixed_input"]
    target = fixed["target"]
    client = _client(selected, execution, target)
    owner = fixed["ownership_admission"]["owner"]
    require(owner == "publisher", "publisher cleanup cannot delete resources owned by another root")
    intent_path = execution.outputs.path("diagnostics") / "delete-intent.json"
    intent: dict[str, Any] = {"kind": "pve-template-delete-intent", "schema_version": 1,
                              "execution_id": execution_id, "action": preview["action"],
                              "preview_digest": preview["preview_digest"],
                              "runtime_digest": preview["runtime"]["image_digest"],
                              "events": [], "residue": []}
    if isinstance(fixed.get("original_execution_id"), str):
        intent["original_execution_id"] = fixed["original_execution_id"]
    elif isinstance(fixed.get("template_record"), Mapping) and isinstance(fixed["template_record"].get("execution_id"), str):
        intent["original_execution_id"] = fixed["template_record"]["execution_id"]
    _write_intent(intent_path, intent)

    def journal(phase: str, status: str, **values: Any) -> None:
        intent["events"].append({"phase": phase, "status": status, **values})
        _write_intent(intent_path, intent)

    if preview["action"] == "cleanup":
        require(fixed["ownership_admission"].get("activity") in {"stopped", "inactive"},
                "cleanup requires confirmed inactive native tasks")
        evidence = _original_publish_evidence(selected, fixed)
        node = quote(target["node"], safe="")
        task_outcomes = _observe_original_tasks(client, evidence["journal"], target["node"])
        evidence["completed"] = task_outcomes.get("template") == "OK"
        phases: list[dict[str, Any]] = []
        admitted_volumes: set[str] = set()
        observed_objects: list[tuple[int, str]] = []
        journal_objects = {(item["vmid"], item["smbios_uuid"]): item for item in evidence["objects"]}
        for item in fixed["objects"]:
            if not isinstance(item, Mapping):
                continue
            vmid = item.get("vmid")
            if type(vmid) is not int:
                raise ValidationError("cleanup object VMID is invalid")
            expected_uuid = item.get("smbios_uuid")
            if (not isinstance(expected_uuid, str) or not expected_uuid or
                    (vmid, expected_uuid) not in journal_objects):
                raise ValidationError("cleanup VM identity is not bound to the original publish journal")
            expected_volumes = _admitted_object_volumes(item)
            journal_volume_map = journal_objects[(vmid, expected_uuid)]["volumes"]
            require(expected_volumes == journal_volume_map,
                    "cleanup VM volumes are not bound to the original publish journal")
            config = client.request("GET", f"/api2/json/nodes/{node}/qemu/{vmid}/config")
            require(isinstance(config, Mapping), "cleanup VM configuration observation is incomplete")
            require(not config.get("lock"), "cleanup VM configuration is locked")
            require(_config_uuid(config) == expected_uuid,
                    "cleanup VM UUID does not match admitted ownership")
            admitted_volumes.update(expected_volumes.values())
            actual_attachments = _volume_attachments(config)
            require(actual_attachments == expected_volumes,
                    "cleanup VM volumes do not exactly match admitted ownership")
            require(not evidence["completed"],
                    "completed templates must be retired, not cleaned up")
            observed_objects.append((vmid, expected_uuid))
            journal("cleanup-vm", "observed", vmid=vmid, smbios_uuid=expected_uuid,
                    volumes=sorted(expected_volumes.values()))
        volume_specs: list[tuple[str, str]] = []
        for item in fixed["volumes"]:
            storage, volid = _cleanup_volume_identity(item)
            require(volid in evidence["volumes"],
                    "cleanup volume is not bound to the original publish journal")
            require(volid == evidence["upload_volid"] or volid in admitted_volumes,
                    "cleanup volume is not bound to an admitted VM record")
            _storage_content(client, target["node"], storage)
            volume_specs.append((storage, volid))
        if evidence["completed"]:
            require(all(volid == evidence["upload_volid"] for _, volid in volume_specs),
                    "completed publication cleanup may only remove its staging upload")
        for vmid, expected_uuid in observed_objects:
            journal("cleanup-vm", "intent", vmid=vmid, smbios_uuid=expected_uuid)
            value = client.request("DELETE", f"/api2/json/nodes/{node}/qemu/{vmid}", fields={"purge": 1})
            journal("cleanup-vm", "submitted", vmid=vmid, upid=value)
            phase = _upid(client, value, "cleanup-vm", node=target["node"])
            phases.append(phase)
            journal("cleanup-vm", "succeeded", vmid=vmid, upid=phase["upid"])
        for storage, volid in volume_specs:
            content = _storage_content(client, target["node"], storage)
            if not any(row.get("volid") == volid for row in content):
                journal("cleanup-volume", "succeeded", volid=volid, already_absent=True)
                continue
            journal("cleanup-volume", "intent", volid=volid)
            value = client.request("DELETE", f"/api2/json/nodes/{node}/storage/{quote(storage, safe='')}/content/{quote(volid, safe='')}")
            journal("cleanup-volume", "submitted", volid=volid, upid=value)
            phase = _upid(client, value, "cleanup-volume", node=target["node"])
            _assert_upload_absent(client, target["node"], storage, volid)
            phases.append(phase)
            journal("cleanup-volume", "succeeded", volid=volid, upid=phase["upid"])
        intent["status"] = "succeeded"
        _write_intent(intent_path, intent)
        return {"kind": "pve-template-result", "schema_version": 2, "execution_id": execution_id,
                "component": "pve-template", "operation": "apply", "action": "cleanup",
                "runtime_digest": preview["runtime"]["image_digest"],
                "phase": "succeeded", "status": "succeeded", "effects": {"pve": "known"},
                "preview_digest": preview["preview_digest"], "recovery_of": fixed["original_execution_id"],
                "publication": "not_applicable",
                "verification": [], "collection": {"status": "succeeded"},
                "native_execution": phases, "cleanup": {"status": "succeeded", "residue": []}}
    retirement = fixed["retirement_admission"]
    require(retirement.get("authorized") is True and retirement.get("dependencies_resolved") is True,
            "retire admission is incomplete")
    require(fixed["ownership_admission"].get("owner") == "publisher" and
            fixed["ownership_admission"].get("activity") in {"stopped", "inactive"},
            "retire requires confirmed publisher ownership and inactivity")
    node = quote(target["node"], safe="")
    record = fixed["template_record"]
    require(record.get("target") == target and record.get("node") == target["node"],
            "retire template record target does not match current target")
    vmid = record["vmid"]
    config = client.request("GET", f"/api2/json/nodes/{node}/qemu/{vmid}/config")
    require(isinstance(config, Mapping), "retire VM configuration observation is incomplete")
    require(not config.get("lock"), "retire VM configuration is locked")
    require(config.get("template") in (1, True, "1"), "retire requires a completed template VM")
    require(_config_uuid(config) == record["smbios_uuid"],
            "retire VM UUID does not match admitted template record")
    record_configuration = record.get("configuration")
    require(isinstance(record_configuration, Mapping), "retire template configuration is missing")
    expected_attachments = _volume_attachments(record_configuration)
    actual_attachments = _volume_attachments(config)
    require(actual_attachments == expected_attachments,
            "retire VM volumes do not exactly match admitted template configuration")
    expected_volumes = {slot: _volume_id(value) for slot, value in record["volumes"].items()}
    require(set(actual_attachments) >= set(expected_volumes) and
            all(actual_attachments[slot] == volume for slot, volume in expected_volumes.items()),
            "retire VM volumes do not exactly match admitted template record")
    journal("retire-template", "observed", vmid=vmid, smbios_uuid=record["smbios_uuid"],
            volumes=sorted(expected_volumes.values()))
    journal("retire-template", "intent", vmid=vmid, smbios_uuid=record["smbios_uuid"])
    value = client.request("DELETE", f"/api2/json/nodes/{node}/qemu/{vmid}", fields={"purge": 1})
    journal("retire-template", "submitted", vmid=vmid, upid=value)
    phase = _upid(client, value, "retire-template", node=target["node"])
    journal("retire-template", "succeeded", vmid=vmid, upid=phase["upid"])
    intent["status"] = "succeeded"
    _write_intent(intent_path, intent)
    return {"kind": "pve-template-result", "schema_version": 2, "execution_id": execution_id,
            "component": "pve-template", "operation": "apply", "action": "retire",
            "runtime_digest": preview["runtime"]["image_digest"],
            "phase": "succeeded", "status": "succeeded", "effects": {"pve": "known"},
            "preview_digest": preview["preview_digest"], "publication": "not_applicable",
            "verification": [], "collection": {"status": "succeeded"},
            "native_execution": [phase], "cleanup": {"status": "succeeded", "residue": []}}


def run(selected: Any, operation: str, scope: str, execution: Execution,
        image_digest: str, execution_id: str = "") -> None:
    require(operation in {"check", "read", "plan", "apply", "verify"}, "unsupported pve-template operation")
    options = _options(selected)
    require(not set(options) - {"action", "preview_digest", "execution_id", "admission", "retirement_admission",
                                "ownership_admission", "runtime_digest", "template"},
            "unknown pve-template operation option")
    selected_action = options.get("action")
    action = selected_action or "publish"
    if operation == "check":
        request = validate_publish_request(_document(selected))
        execution.finish({"component": "pve-template", "operation": operation, "schema_version": 1,
                          "request_digest": canonical_digest(request), "network": False, "state": False})
        return
    if operation == "verify":
        value = _file_mapping(selected, "result", "template_result")
        if not isinstance(value, Mapping) or value.get("kind") != "pve-template-result" or value.get("schema_version") != 2:
            raise ValidationError("pve-template verify requires pve-template-result/v2")
        bound_preview = validate_publish_preview(_file_mapping(selected, "preview", "template_preview"))
        require(bound_preview["action"] == value.get("action")
                and value.get("preview_digest") == bound_preview["preview_digest"]
                and value.get("runtime_digest") == bound_preview["runtime"]["image_digest"],
                "template result is not bound to the selected publication preview")
        fixed_request = bound_preview["fixed_input"]
        if bound_preview["action"] != "publish":
            require(value.get("status") == "succeeded" and value.get("publication") == "not_applicable"
                    and value.get("cleanup", {}).get("status") == "succeeded"
                    and not value.get("cleanup", {}).get("residue"),
                    "template deletion result is not confirmed successful")
            require(not scope or scope == fixed_request["target"]["node"],
                    "template verification scope does not match the target node")
            execution.finish({"component": "pve-template", "operation": operation, "status": "verified",
                              "action": bound_preview["action"], "execution_id": value.get("execution_id"),
                              "preview_digest": value["preview_digest"], "publication": "not_applicable"})
            return
        record = validate_template_record_v2(value.get("template_record"))
        require(value.get("publication") == "succeeded"
                and record["target"] == fixed_request["target"] and record["vmid"] == fixed_request["vmid"]
                and record["execution_id"] == value.get("execution_id")
                and record["artifact_digest"] == value.get("artifact_digest") == fixed_request["artifact_digest"],
                "template result identity does not match the selected publication")
        require(not scope or scope == record["node"], "template verification scope does not match the target node")
        _verify_requested_config(record["configuration"], fixed_request)
        execution.finish({"component": "pve-template", "operation": operation, "status": "verified",
                          "execution_id": value.get("execution_id"), "preview_digest": value.get("preview_digest"),
                          "publication": value["publication"], "cleanup": value.get("cleanup")})
        return
    if operation == "read":
        journal = _file_mapping(selected, "journal")
        if journal is not None:
            require("template" not in options, "template read selectors are mutually exclusive")
            require(journal.get("kind") == "pve-template-publish-intent" and journal.get("schema_version") == 1,
                    "template read requires an original publish journal")
            require(not scope or journal.get("target", {}).get("node") == scope,
                    "template journal scope does not match the target node")
            write_text(execution.outputs.path("generated") / "publish-journal.json",
                       json.dumps(journal, sort_keys=True, indent=2) + "\n", secure=True)
            execution.finish({"component": "pve-template", "operation": operation, "status": "recorded",
                              "origin": "journal", "execution_id": journal.get("execution_id"),
                              "native_status": journal.get("status", "unknown")})
            return
        template = options.get("template")
        if not isinstance(template, Mapping) or set(template) != {"target", "vmid"}:
            raise ValidationError("pve-template read requires target and vmid")
        target = template["target"]
        require(isinstance(target, Mapping) and set(target) == {"api_endpoint", "node", "tls_verify"}
                and target.get("tls_verify") is True, "template read requires a verified HTTPS target")
        require(isinstance(target["node"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", target["node"]),
                "template read node is invalid")
        require(type(template["vmid"]) is int and template["vmid"] > 0, "template read VMID is invalid")
        require(not scope or scope == target["node"], "pve-template scope must select the target node")
        config = _client(selected, execution, target).request(
            "GET", f"/api2/json/nodes/{quote(target['node'], safe='')}/qemu/{template['vmid']}/config")
        require(isinstance(config, Mapping), "PVE template observation is invalid")
        require(config.get("template") in {1, "1"}, "selected PVE object is not a template")
        observation_request = {"target": target, "vmid": template["vmid"],
                               "version": "observation", "artifact_digest": "unknown"}
        record = _record_from_config(observation_request, config, "unknown", complete=False)
        record.update(origin="observation", execution_id="unknown", artifact_digest="unknown")
        write_text(execution.outputs.path("generated") / "template-record.json", json.dumps(record, sort_keys=True, indent=2) + "\n", secure=True)
        execution.finish({"component": "pve-template", "operation": operation, "status": "observed", "origin": "observation"})
        return
    preview: dict[str, Any] | None = None
    if operation == "apply":
        source = _path(selected, "preview", "template_preview")
        if source is None:
            raise ValidationError("pve-template apply requires a selected publication preview")
        preview = validate_publish_preview(load_json(source))
        if selected_action is not None:
            require(selected_action == preview["action"], "pve-template apply action does not match preview")
        action = preview["action"]
        fixed = preview["fixed_input"]
        request = (validate_cleanup_request(fixed) if action == "cleanup" else
                   validate_retire_request(fixed) if action == "retire" else
                   validate_publish_request(fixed))
    else:
        request = (validate_cleanup_request(_document(selected, "cleanup")) if action == "cleanup" else
                   validate_retire_request(_document(selected, "retire")) if action == "retire" else
                   validate_publish_request(_document(selected)))
    require(not scope or scope == request["target"]["node"], "pve-template scope must select the request target node")
    if operation == "plan":
        require(action in {"publish", "cleanup", "retire"}, "pve-template plan action must be publish, cleanup or retire")
        if action == "publish":
            client = _client(selected, execution, request["target"])
            observed = _observed(selected, client, request["target"], request)
            preview = build_publish_preview(request, runtime=_runtime(image_digest), observed=observed)
        else:
            preview = build_action_preview(request, action=action, runtime=_runtime(image_digest), observed={"activity": "unobserved"})
        write_text(execution.outputs.path("plan") / "template-preview.json", json.dumps(preview, sort_keys=True, indent=2) + "\n", secure=True)
        execution.finish({"component": "pve-template", "operation": operation, "action": action,
                          "preview_digest": preview["preview_digest"], "schema_version": PUBLISH_PREVIEW_VERSION})
        return
    if preview is None:
        raise ValidationError("pve-template apply preview was not loaded")
    require(preview["preview_digest"] == options.get("preview_digest"), "pve-template apply preview digest is stale")
    require(preview["runtime"]["image_digest"] == image_digest, "pve-template apply runtime does not match preview")
    require(execution_id and isinstance(options.get("admission"), Mapping),
            "pve-template apply requires execution_id and current execution admission")
    validate_execution_admission(options["admission"],
                                             digest=preview["preview_digest"].removeprefix("sha256:"),
                                             execution_id=execution_id, target=request["target"])
    try:
        result = (_publish(selected, execution, request, preview, execution_id) if preview["action"] == "publish"
                  else _delete_action(selected, execution, request, preview, execution_id))
    except Exception:
        intent_name = "publish-intent.json" if preview["action"] == "publish" else "delete-intent.json"
        intent_path = execution.outputs.path("diagnostics") / intent_name
        if intent_path.is_file():
            intent = load_json(intent_path)
            if isinstance(intent, Mapping):
                artifact_digest = request.get("artifact_digest", "unknown") if isinstance(request, Mapping) else "unknown"
                failure = _failure_result(intent, execution_id, preview["preview_digest"], artifact_digest)
                write_text(execution.outputs.path("diagnostics") / "result.json",
                           json.dumps(failure, sort_keys=True, indent=2) + "\n", secure=True)
        raise
    if "template_record" in result:
        write_text(execution.outputs.path("generated") / "template-record.json", json.dumps(result["template_record"], sort_keys=True, indent=2) + "\n", secure=True)
    write_text(execution.outputs.path("diagnostics") / "result.json", json.dumps(result, sort_keys=True, indent=2) + "\n", secure=True)
    if result.get("status") != "succeeded":
        raise OperationFailed("PVE publication remains unresolved; inspect protected result and publish intent")
    execution.finish({"component": "pve-template", "operation": operation, "action": preview["action"],
                      "execution_id": execution_id, "preview_digest": preview["preview_digest"],
                      "status": result.get("status"), "publication": result.get("publication"),
                      "cleanup": result.get("cleanup", {}).get("status")})
