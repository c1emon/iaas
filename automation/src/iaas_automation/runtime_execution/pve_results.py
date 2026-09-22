"""Private native expectations and read-only PVE verification.

Public summaries contain counts/status only. Resource addresses, state and API
configuration remain in the protected task output, never in CLI diagnostics.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any

from iaas_automation.common.errors import require
from iaas_automation.pve_inventory.pve_api import (
    ReadOnlyPveApi, PveApiRuntimeConfig, PveApiNotConfiguredError,
)

VM_TYPE = "proxmox_virtual_environment_vm"
HA_TYPE = "proxmox_virtual_environment_haresource"
ACTIONS = {("no-op",), ("create",), ("update",), ("delete",),
           ("delete", "create"), ("create", "delete"), ("read",)}


def _unknown(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(_unknown(v) for v in value)
    return value is True


def api_client(target: dict, environ: dict) -> ReadOnlyPveApi:
    return ReadOnlyPveApi(PveApiRuntimeConfig(
        endpoint=target["api_endpoint"], insecure=target["insecure"],
        api_username=environ["TF_VAR_pve_api_username"],
        api_token_id=environ["TF_VAR_pve_api_token_id"],
        api_token_secret=environ["TF_VAR_pve_api_token_secret"]))


def machine_review(native: dict) -> tuple[dict, list[dict], list[dict]]:
    """Derive actions and clone dependencies from native JSON, not declarations."""
    counts: Counter = Counter()
    changes, dependencies = [], []
    for item in native.get("resource_changes", []):
        if item.get("mode", "managed") != "managed":
            continue
        action = tuple(item["change"]["actions"])
        require(action in ACTIONS, "unsupported native plan action")
        require(item.get("type") in {VM_TYPE, HA_TYPE}, "unsupported managed PVE resource")
        counts["replace" if len(action) == 2 else action[0]] += 1
        if action in {("no-op",), ("read",)}:
            continue
        changes.append(deepcopy(item))
        if item["type"] == VM_TYPE and "create" in action:
            change = item["change"]
            unknown = change.get("after_unknown", {})
            require(not _unknown(unknown.get("clone")), "unknown clone dependency")
            clone = (change.get("after") or {}).get("clone", [])
            require(isinstance(clone, list), "unknown clone dependency")
            for source in clone:
                require(isinstance(source.get("vm_id"), int) and source["vm_id"] > 0
                        and isinstance(source.get("node_name"), str) and source["node_name"],
                        "unknown clone dependency")
                dependency = {"node": source["node_name"], "vmid": source["vm_id"]}
                if dependency not in dependencies:
                    dependencies.append(dependency)
    return {"schema_version": 1, "actions": dict(counts), "changed_resources": len(changes),
            "clone_dependencies": len(dependencies)}, changes, dependencies


def state_instances(state: dict) -> dict[str, list[dict]]:
    """Read raw native state without root outputs or a new provider refresh."""
    result: dict[str, list[dict]] = {}
    for resource in state.get("resources", []):
        if resource.get("mode", "managed") != "managed":
            continue
        prefix = resource.get("module", "")
        prefix = prefix + "." if prefix else ""
        base = prefix + resource["type"] + "." + resource["name"]
        for instance in resource.get("instances", []):
            import json
            address = base
            if "index_key" in instance:
                address += "[" + json.dumps(instance["index_key"], ensure_ascii=False) + "]"
            result.setdefault(address, []).append(instance)
    return result


def _resolve(planned: Any, unknown: Any, actual: Any) -> Any:
    # Only unknown values come from the original post-apply snapshot. Known
    # plan expectations must survive provider drift and later observations.
    if unknown is True:
        return deepcopy(actual)
    if isinstance(planned, dict):
        unknown = unknown if isinstance(unknown, dict) else {}
        actual = actual if isinstance(actual, dict) else {}
        return {key: _resolve(planned.get(key), unknown.get(key), actual.get(key))
                for key in set(planned) | set(unknown)}
    if isinstance(planned, list):
        return [_resolve(value, unknown[i] if isinstance(unknown, list) and i < len(unknown) else None,
                         actual[i] if isinstance(actual, list) and i < len(actual) else None)
                for i, value in enumerate(planned)]
    return deepcopy(planned)


def expectations(changes: list[dict], snapshot: dict | None) -> list[dict]:
    instances = state_instances(snapshot) if snapshot is not None else {}
    expected = []
    for item in changes:
        change, address = item["change"], item["address"]
        current = instances.get(address, [])
        live = [i for i in current if not i.get("deposed")]
        actual = live[0].get("attributes", {}) if len(live) == 1 else {}
        before = change.get("before") or {}
        action = change["actions"]
        after = _resolve(change.get("after") or {}, change.get("after_unknown", {}), actual)
        def identity(value: dict) -> dict:
            return {"node": value.get("node_name"), "vmid": value.get("vm_id")}
        if item["type"] == HA_TYPE:
            expected.append({"kind": "ha", "action": action, "values": after if "create" in action or "update" in action else before,
                             "absent": action == ["delete"], "snapshot_complete": snapshot is not None})
            continue
        if action == ["delete"]:
            expected.append({"kind": "vm", **identity(before), "absent": True,
                             "state_absent": not current, "snapshot_complete": snapshot is not None})
            continue
        expected.append({"kind": "vm", **identity(after), "absent": False, "values": after,
                         "native_identity": actual.get("smbios", []),
                         "snapshot_complete": snapshot is not None and len(live) == 1,
                         "deposed": any(i.get("deposed") for i in current),
                         "replacement": "delete" in action,
                         "before_identity": before.get("smbios", [])})
        if "delete" in action and identity(before) != identity(after):
            expected.append({"kind": "vm", **identity(before), "absent": True,
                             "state_absent": not any(i.get("deposed") for i in current),
                             "snapshot_complete": snapshot is not None})
    return expected


def _parts(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    return {key: val for token in value.split(",") if "=" in token for key, val in [token.split("=", 1)]}


def template_identity(config: dict) -> dict:
    disks = {key: str(value).split(",", 1)[0] for key, value in config.items()
             if re.fullmatch(r"(?:scsi|virtio|sata|ide)\d+", key) and "media=cdrom" not in str(value)}
    uuid = _parts(config.get("smbios1")).get("uuid")
    require(bool(uuid) and bool(disks), "template native identity is missing")
    return {"smbios_uuid": uuid, "disks": disks}


def _size_gib(value: str | None) -> float | None:
    match = re.fullmatch(r"([0-9.]+)([KMGT]?)", value or "")
    if not match:
        return None
    return float(match[1]) * {"": 1 / 1024**3, "K": 1 / 1024**2, "M": 1 / 1024, "G": 1, "T": 1024}[match[2]]


def _vm_fields(expected: dict, config: dict, status: dict) -> dict[str, str]:
    checks: dict[str, str] = {}

    def compare(name: str, want: Any, got: Any) -> None:
        checks[name] = "unknown" if want is None or got is None else "passed" if want == got else "failed"

    values = expected["values"]
    cpu, memory = values.get("cpu") or [{}], values.get("memory") or [{}]
    compare("cores", cpu[0].get("cores"), config.get("cores"))
    if cpu[0].get("type") is not None:
        compare("cpu_type", cpu[0]["type"], str(config.get("cpu", "")).split(",")[0] or None)
    if cpu[0].get("sockets") is not None:
        compare("sockets", cpu[0]["sockets"], config.get("sockets", 1))
    compare("memory", memory[0].get("dedicated"), int(config["memory"]) if str(config.get("memory", "")).isdigit() else None)
    compare("power", "running" if values.get("started") is True else "stopped" if values.get("started") is False else None, status.get("status"))
    if values.get("on_boot") is not None:
        compare("on_boot", values["on_boot"], str(config.get("onboot", 0)) == "1")
    for field, api_field in (("bios", "bios"), ("machine", "machine"), ("scsi_hardware", "scsihw")):
        if values.get(field) is not None:
            compare(field, values[field], config.get(api_field))
    for i, disk in enumerate(values.get("disk") or []):
        raw = config.get(disk.get("interface"))
        volume = str(raw).split(",", 1)[0] if raw else None
        compare(f"disk.{i}.storage", disk.get("datastore_id"), volume.split(":", 1)[0] if volume else None)
        compare(f"disk.{i}.size", disk.get("size"), _size_gib(_parts(raw).get("size")))
        if disk.get("file_id"):
            compare(f"disk.{i}.volume", disk["file_id"], volume)
    if not values.get("disk"):
        checks["disks"] = "unknown"
    expected_disks = {d.get("interface") for d in values.get("disk") or []}
    actual_disks = {k for k, v in config.items() if re.fullmatch(r"(?:scsi|sata|virtio|ide)\d+", k)
                    and "media=cdrom" not in str(v) and "cloudinit" not in str(v)}
    compare("disk_attachments", expected_disks, actual_disks)
    if any(re.fullmatch(r"unused\d+", k) for k in config):
        checks["unused_disks"] = "failed"
    for i, nic in enumerate(values.get("network_device") or []):
        raw = _parts(config.get(f"net{i}"))
        compare(f"nic.{i}.bridge", nic.get("bridge"), raw.get("bridge"))
        model = nic.get("model") or "virtio"
        mac = nic.get("mac_address")
        compare(f"nic.{i}.mac", mac.upper() if isinstance(mac, str) else None,
                raw[model].upper() if raw.get(model) else None)
    compare("network_attachments", {f"net{i}" for i, _ in enumerate(values.get("network_device") or [])},
            {k for k in config if re.fullmatch(r"net\d+", k)})
    for init in values.get("initialization") or []:
        custom = _parts(config.get("cicustom"))
        for field, key in (("user_data_file_id", "user"), ("network_data_file_id", "network")):
            if field in init:
                compare(f"cloudinit.{key}", init[field], custom.get(key))
    for pci in values.get("hostpci") or []:
        raw = _parts(config.get(pci.get("device")))
        compare("pci." + str(pci.get("device")), pci.get("mapping"), raw.get("mapping"))
        for field in ("pcie", "rombar", "xvga"):
            if pci.get(field) is not None:
                compare("pci." + str(pci.get("device")) + "." + field,
                        str(int(pci[field])), raw.get(field, {"pcie": "0", "rombar": "1", "xvga": "0"}[field]))
    native = expected.get("native_identity") or []
    uuid = native[0].get("uuid") if native else None
    if uuid:
        compare("native_identity", uuid, _parts(config.get("smbios1")).get("uuid"))
    if expected.get("replacement"):
        before = expected.get("before_identity") or []
        prior_uuid = before[0].get("uuid") if before else None
        checks["replacement_identity"] = "unknown" if not uuid else "failed" if uuid == prior_uuid else "passed"
    return checks


def verify_configuration(expected: list[dict], api: Any) -> dict:
    items = []
    for wanted in expected:
        checks: dict[str, str] = {}
        if not wanted.get("snapshot_complete"):
            items.append({"status": "unknown", "checks": {"original_snapshot": "unknown"}})
            continue
        try:
            if wanted["kind"] == "ha":
                values = wanted["values"]
                resource_id = values.get("resource_id")
                record = next((r for r in api.ha_status() if r.get("sid") == resource_id), None)
                if not resource_id:
                    checks["ha"] = "unknown"
                elif wanted["absent"]:
                    checks["ha"] = "passed" if record is None else "failed"
                else:
                    checks["ha"] = "passed" if record and record.get("state") == values.get("state") else "failed"
            elif not isinstance(wanted.get("vmid"), int) or not wanted.get("node"):
                checks["identity"] = "unknown"
            else:
                try:
                    config = api.vm_config(wanted["node"], wanted["vmid"])
                except PveApiNotConfiguredError:
                    checks["existence"] = "passed" if wanted["absent"] else "failed"
                else:
                    if wanted["absent"]:
                        checks["existence"] = "failed"
                    else:
                        checks = _vm_fields(wanted, config, api.vm_status(wanted["node"], wanted["vmid"]))
                if wanted.get("deposed") or wanted.get("state_absent") is False:
                    checks["state_residual"] = "failed"
        except Exception:
            checks["observation"] = "unknown"
        status = "failed" if "failed" in checks.values() else "unknown" if not checks or "unknown" in checks.values() else "passed"
        items.append({"status": status, "checks": checks})
    status = "failed" if any(i["status"] == "failed" for i in items) else "unknown" if any(i["status"] == "unknown" for i in items) else "passed"
    return {"status": status, "scope": "changed_objects" if items else "empty", "objects": items}
