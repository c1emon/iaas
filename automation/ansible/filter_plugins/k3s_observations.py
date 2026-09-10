"""Parse read-only Linux observations without substituting desired state."""

import ipaddress
import json
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


def k3s_node_healthy(response, node, version):
    """Require an exact API node/version and the established readiness boundary."""
    try:
        payload = json.loads(response) if isinstance(response, str) else response
        matches = [item for item in payload["items"] if item["metadata"]["name"] == node["vm_ref"]]
        if len(matches) != 1:
            return False
        observed = matches[0]
        status = observed["status"]
        labels = observed["metadata"].get("labels", {})
        role = "server" if any(key in labels for key in ["node-role.kubernetes.io/control-plane", "node-role.kubernetes.io/master"]) else "agent"
        if role != node["role"] or status["nodeInfo"]["kubeletVersion"] != version:
            return False
        conditions = status["conditions"]
        ready = [condition for condition in conditions if condition["type"] == "Ready"]
        if len(ready) != 1:
            return False
        condition = ready[0]
        if condition["status"] == "True":
            return True
        cni_pattern = (r"^(?:container runtime network not ready: networkready=false "
                       r"reason:networkpluginnotready message:)?(?:network plugin returns error: )?"
                       r"cni plugin not initialized$")
        return (condition["status"] == "False"
                and condition.get("reason", "").lower() in {"kubeletnotready", "networkpluginnotready"}
                and re.fullmatch(cni_pattern, condition.get("message", "").lower()) is not None
                and not any(item["status"] == "True" and item["type"] not in {"Ready", "EtcdIsVoter"}
                            for item in conditions))
    except (ValueError, TypeError, KeyError):
        return False


def k3s_installation_allowed(facts, mode, version, checksum):
    state = facts.get("state")
    if state == "fresh":
        return mode in {"install", "converge"}
    if state == "artifact-only":
        return mode == "converge" and facts.get("version") == version and facts.get("sha256") == checksum
    if state != "managed":
        return False
    if mode == "converge":
        return facts.get("version") == version and facts.get("sha256") == checksum
    if mode != "upgrade" or not facts.get("datastore"):
        return False
    pattern = r"^v(\d+)\.(\d+)\.(\d+)\+k3s(\d+)$"
    current, target = re.fullmatch(pattern, facts.get("version", "")), re.fullmatch(pattern, version)
    if current is None or target is None:
        return False
    before, after = tuple(map(int, current.groups())), tuple(map(int, target.groups()))
    if before == after and facts.get("sha256") != checksum:
        return False
    return before <= after and before[0] == after[0] and after[1] - before[1] in {0, 1}


class FilterModule:
    def filters(self):
        return {"k3s_capabilities": k3s_capabilities,
                "k3s_interface_observation": k3s_interface_observation,
                "k3s_node_healthy": k3s_node_healthy,
                "k3s_installation_allowed": k3s_installation_allowed}
