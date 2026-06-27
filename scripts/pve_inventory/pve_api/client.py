"""Read-only proxmoxer-backed PVE API facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

from proxmoxer import AuthenticationError, ProxmoxAPI, ResourceException

from .errors import (
    PveApiAuthenticationError,
    PveApiError,
    PveApiNotConfiguredError,
    PveApiUnavailableError,
    redact_sensitive_text,
)


@dataclass(frozen=True)
class HealthApiRuntimeConfig:
    """API-only runtime inputs used to build a proxmoxer client."""

    endpoint: str
    api_username: str
    api_token_id: str
    api_token_secret: str
    insecure: bool


def _normalize_endpoint(endpoint: str) -> tuple[str, int | None]:
    """Return proxmoxer-friendly host and optional port from a TF-style endpoint."""
    value = endpoint.strip()
    if "//" not in value:
        parsed = urlparse(f"//{value}")
    else:
        parsed = urlparse(value)
    if not parsed.hostname:
        raise ValueError(f"invalid PVE endpoint: {endpoint!r}")
    return parsed.hostname, parsed.port


class ReadOnlyPveApi:
    """Named read-only PVE API queries for health and related checks."""

    def __init__(self, runtime: HealthApiRuntimeConfig, *, timeout: int = 30, prox: ProxmoxAPI | None = None) -> None:
        self._api_token_secret = runtime.api_token_secret
        host, port = _normalize_endpoint(runtime.endpoint)
        kwargs: dict[str, Any] = {
            "user": runtime.api_username,
            "token_name": runtime.api_token_id,
            "token_value": runtime.api_token_secret,
            "verify_ssl": not runtime.insecure,
            "timeout": timeout,
        }
        if port is not None:
            kwargs["port"] = port
        self._prox = prox or ProxmoxAPI(
            host,
            **kwargs,
        )

    @classmethod
    def from_runtime(cls, runtime: HealthApiRuntimeConfig, *, timeout: int = 30) -> "ReadOnlyPveApi":
        return cls(runtime, timeout=timeout)

    def redact_operator_text(self, text: str) -> str:
        """Redact operator-visible text with the known API token secret."""
        return redact_sensitive_text(text, [self._api_token_secret])

    def _safe_message(self, action: str, exc: Exception) -> str:
        raw = str(exc)
        for attr in ("content", "status_message"):
            value = getattr(exc, attr, None)
            if value:
                raw = f"{raw}: {value}"
        raw = redact_sensitive_text(raw, [self._api_token_secret])
        return f"PVE API {action} failed: {raw}".strip()

    def _call(self, action: str, getter: Callable[[], Any]) -> Any:
        try:
            return getter()
        except AuthenticationError as exc:
            raise PveApiAuthenticationError(self._safe_message(action, exc)) from None
        except ResourceException as exc:
            status_code = getattr(exc, "status_code", None)
            message = self._safe_message(action, exc)
            if status_code == 404:
                raise PveApiNotConfiguredError(message, status_code=status_code) from None
            if isinstance(status_code, int) and 500 <= status_code < 600:
                raise PveApiUnavailableError(message, status_code=status_code) from None
            raise PveApiError(message, status_code=status_code) from None
        except Exception as exc:  # pragma: no cover - defensive boundary
            raise PveApiError(self._safe_message(action, exc)) from None

    def cluster_status(self) -> Any:
        return self._call("cluster.status", lambda: self._prox.cluster.status.get())

    def nodes(self) -> Any:
        return self._call("nodes", lambda: self._prox.nodes.get())

    def node_status(self, node: str) -> Any:
        return self._call(f"nodes/{node}/status", lambda: self._prox.nodes(node).status.get())

    def node_storage(self, node: str) -> Any:
        return self._call(f"nodes/{node}/storage", lambda: self._prox.nodes(node).storage.get())

    def vms(self, node: str) -> Any:
        return self._call(f"nodes/{node}/qemu", lambda: self._prox.nodes(node).qemu.get())

    def vm_status(self, node: str, vmid: int) -> Any:
        return self._call(f"nodes/{node}/qemu/{vmid}/status/current", lambda: self._prox.nodes(node).qemu(vmid).status.current.get())

    def vm_config(self, node: str, vmid: int) -> Any:
        return self._call(f"nodes/{node}/qemu/{vmid}/config", lambda: self._prox.nodes(node).qemu(vmid).config.get())

    def ha_status(self) -> Any:
        return self._call("cluster/ha/status/current", lambda: self._prox.cluster.ha.status.current.get())

    def ceph_status(self) -> Any:
        return self._call("cluster/ceph/status", lambda: self._prox.cluster.ceph.status.get())
