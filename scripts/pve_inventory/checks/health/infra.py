"""HA and Ceph health checks."""

from __future__ import annotations

from typing import Any

from ...pve_api import PveApiError, PveApiNotConfiguredError, PveApiUnavailableError, PveReadOnlyApi, redact_sensitive_text
from ..results import CheckResult, Severity


def _emit(results: list[CheckResult], severity: Severity, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=severity, check_id=check_id, message=message))


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _safe_message(api: PveReadOnlyApi, message: str) -> str:
    redactor = getattr(api, "redact_operator_text", None)
    if callable(redactor):
        return redactor(message)  # type: ignore[misc]
    return redact_sensitive_text(message, [])


def _lookup_field(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def _ceph_health_status(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    health = data.get("health")
    if isinstance(health, dict):
        value = health.get("status") or health.get("state")
        return str(value or "").upper()
    if health is not None:
        return str(health).upper()
    return str(data.get("status") or "").upper()


def check_ha(api: PveReadOnlyApi, results: list[CheckResult]) -> None:
    try:
        records = _as_list(api.ha_status())
    except (PveApiNotConfiguredError, PveApiUnavailableError):
        _emit(results, "SKIP", "ha", "HA endpoint is unavailable or not configured")
        return
    except PveApiError as exc:
        _emit(results, "SKIP", "ha", _safe_message(api, f"HA checks unavailable: {exc}"))
        return
    if not records:
        _emit(results, "SKIP", "ha", "HA subsystem has no resources")
        return
    unhealthy: list[str] = []
    for record in records:
        state = str(_lookup_field(record, "state", "status") or "").lower()
        name = str(_lookup_field(record, "sid", "service", "name") or "ha-resource")
        if state in {"error", "fence", "fenced", "unknown", "failed", "unhealthy"}:
            unhealthy.append(name)
            _emit(results, "FAIL", f"ha.{name}", f"HA resource {name} is unhealthy ({state})")
        elif state:
            _emit(results, "PASS", f"ha.{name}", f"HA resource {name} is {state}")
    if unhealthy:
        _emit(results, "FAIL", "ha", f"HA resources unhealthy: {', '.join(unhealthy)}")
    elif records:
        _emit(results, "PASS", "ha", "HA resources are healthy")


def check_ceph(api: PveReadOnlyApi, results: list[CheckResult]) -> None:
    try:
        data = api.ceph_status()
    except (PveApiNotConfiguredError, PveApiUnavailableError):
        _emit(results, "SKIP", "ceph", "Ceph endpoint is unavailable or not configured")
        return
    except PveApiError as exc:
        _emit(results, "SKIP", "ceph", _safe_message(api, f"Ceph checks unavailable: {exc}"))
        return
    health = _ceph_health_status(data)
    if health == "HEALTH_OK":
        _emit(results, "PASS", "ceph", "Ceph health is HEALTH_OK")
    elif health == "HEALTH_WARN":
        _emit(results, "WARN", "ceph", "Ceph health is HEALTH_WARN")
    elif health == "HEALTH_ERR":
        _emit(results, "FAIL", "ceph", "Ceph health is HEALTH_ERR")
    else:
        _emit(results, "SKIP", "ceph", "Ceph health status is unavailable")
