"""Reserved network configuration names, separate from guest credentials."""

from iaas.common.errors import require

RESERVED_PROXY_NAMES = frozenset({"HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY", "FTP_PROXY"})


def require_guest_credential_name(name: str) -> None:
    require(name.upper() not in RESERVED_PROXY_NAMES,
            f"reserved proxy environment name cannot be used as a guest credential: {name}")
