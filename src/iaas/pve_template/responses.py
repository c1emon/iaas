"""Safe request outcome classification at the authenticated PVE boundary."""
from __future__ import annotations

import re
from urllib.error import HTTPError

from iaas.runtime_execution.execution import OperationFailed


class RequestRejected(OperationFailed):
    """The native permission check rejected this request before execution."""

    def __init__(self, method: str, path: str, http_status: int = 403) -> None:
        super().__init__('request_rejected')
        self.method, self.path, self.http_status = method, path, http_status


class RequestOutcomeUnknown(OperationFailed):
    """No authoritative evidence establishes whether the request executed."""

    def __init__(self, http_status: int | None = None) -> None:
        super().__init__('request_outcome_unknown')
        self.http_status = http_status


def permission_rejection(error: HTTPError, *, url: str, path: str) -> bool:
    """Recognize the native pre-dispatch VM permission failure, not generic 403."""
    vm = re.fullmatch(r'/api2/json/nodes/[^/]+/qemu/(\d+)(?:/.*)?', path)
    if (error.code != 403 or error.url != url or vm is None
            or not str(error.headers.get('Server', '')).startswith('pve-api-daemon/')):
        return False
    return re.fullmatch(
        rf'Permission check failed \(/vms/{vm[1]}, VM\.[A-Za-z.]+(?:\|VM\.[A-Za-z.]+)*\)\s*',
        str(error.reason),
    ) is not None
