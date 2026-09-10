"""Parse read-only Linux observations without substituting desired state."""

import ipaddress
import re


def k3s_capabilities(probe):
    if probe.get("rc", 1) != 0:
        return []
    match = re.fullmatch(r"CapEff:\s*([0-9a-fA-F]{1,16})\s*", probe.get("stdout", ""))
    if not match:
        return []
    bits = int(match[1], 16)
    return [name for name, bit in [("NET_ADMIN", 12), ("SYS_ADMIN", 21)] if bits & (1 << bit)]


def k3s_interface_observation(probe, address, interface):
    missing = {"node_ip": "", "node_interface": ""}
    if probe.get("rc", 1) != 0:
        return missing
    expected = ipaddress.ip_address(address)
    for line in probe.get("stdout", "").splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[2] not in {"inet", "inet6"}:
            continue
        try:
            observed = ipaddress.ip_interface(fields[3]).ip
        except ValueError:
            continue
        device = fields[1].split("@", 1)[0]
        if observed == expected and device == interface:
            return {"node_ip": str(observed), "node_interface": device}
    return missing


class FilterModule:
    def filters(self):
        return {"k3s_capabilities": k3s_capabilities,
                "k3s_interface_observation": k3s_interface_observation}
