"""OpenSSL connection arguments for a validated K3s endpoint."""

import ipaddress


def platform_handoff_tls_endpoint(address: str) -> dict[str, str]:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return {"connect": f"{address}:6443", "verify_option": "-verify_hostname", "identity": address}
    host = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    return {"connect": f"{host}:6443", "verify_option": "-verify_ip", "identity": ip.compressed}


class FilterModule:
    def filters(self):
        return {"platform_handoff_tls_endpoint": platform_handoff_tls_endpoint}
