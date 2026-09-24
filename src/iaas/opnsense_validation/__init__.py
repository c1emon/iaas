from __future__ import annotations

import ipaddress
from pathlib import Path
import re
from typing import Any, NoReturn

import yaml

from iaas.common.errors import ValidationError
from .aliases import ALIAS_NAME, validate_frequency, validate_local, validate_url


DEFAULT_RESOURCE_FILES = {
    "aliases": "aliases.yml",
    "vips": "vips.yml",
    "gateways": "gateways.yml",
    "filter-rules": "filter-rules.yml",
}
RESOURCE_FILES = {
    **DEFAULT_RESOURCE_FILES,
    "dnat": "dnat.yml",
    "one-to-one-nat": "one-to-one-nat.yml",
    "interface-groups": "interface-groups.yml",
}
TOP_LEVEL = {
    "aliases": "opnsense_aliases",
    "vips": "opnsense_vips",
    "gateways": "opnsense_gateways",
    "filter-rules": "opnsense_filter_rules",
    "dnat": "opnsense_dnat_rules",
    "one-to-one-nat": "opnsense_one_to_one_nat_rules",
    "interface-groups": "opnsense_interface_groups",
}
IDENTIFIER = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
INTERFACE = re.compile(r"^[a-z][a-z0-9_]*$")
IDENTITY_PART = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _error(path: str, message: str) -> NoReturn:
    raise ValidationError(f"opnsense validation failed: {path}: {message}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _error(path, "must be a mapping")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _error(path, "must be a list")
    return value


def _string(value: Any, path: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        _error(path, "must be a non-empty string")
    if pattern and not pattern.fullmatch(value):
        _error(path, "has invalid syntax")
    return value


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        _error(path, "must be a boolean")
    return value


def _rule_interface(value: Any, path: str) -> str:
    from .interface_groups import GROUP_NAME

    value = _string(value, path)
    if not INTERFACE.fullmatch(value) and not GROUP_NAME.fullmatch(value):
        _error(path, "must be a physical interface key or valid interface group name")
    return value


def _integer(value: Any, path: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int:
        _error(path, "must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        upper = f"..{maximum}" if maximum is not None else "+"
        _error(path, f"must be within {minimum}{upper}")
    return value


def _shape(record: dict[str, Any], path: str, required: set[str], optional: set[str] = set()) -> None:
    missing = sorted(required - record.keys())
    if missing:
        _error(path, f"missing required keys {', '.join(missing)}")
    unknown = sorted(record.keys() - required - optional)
    if unknown:
        _error(path, f"unknown keys {', '.join(unknown)}")


def _state(value: Any, path: str) -> str:
    value = _string(value, path)
    if value not in {"present", "absent"}:
        _error(path, "must be present or absent")
    return value


def _ip_or_network(value: str, path: str) -> None:
    try:
        if "/" in value:
            ipaddress.ip_network(value, strict=False)
        else:
            ipaddress.ip_address(value)
    except ValueError:
        _error(path, "must be an IP address or CIDR")


def _token(value: Any, path: str) -> str:
    value = _string(value, path)
    if value in {"any", "(self)"}:
        return value
    try:
        _ip_or_network(value, path)
    except ValidationError:
        if not IDENTIFIER.fullmatch(value):
            _error(path, "must be an IP/CIDR or valid object token")
    return value


def _ports(value: Any, path: str) -> None:
    values = value if isinstance(value, list) else [value]
    if not values:
        _error(path, "must not be empty")
    for index, item in enumerate(values):
        item_path = f"{path}[{index}]" if isinstance(value, list) else path
        if type(item) is int:
            _integer(item, item_path, minimum=1, maximum=65535)
            continue
        item = _string(item, item_path)
        if item.isdecimal():
            _integer(int(item), item_path, minimum=1, maximum=65535)
        elif re.fullmatch(r"\d+-\d+", item):
            start, end = (int(part) for part in item.split("-"))
            if not 1 <= start <= end <= 65535:
                _error(item_path, "port range must be within 1..65535 and ascending")
        elif not IDENTIFIER.fullmatch(item):
            _error(item_path, "must be a port, inclusive range, or valid alias")


def _net_values(value: Any, path: str) -> list[str]:
    values = value if isinstance(value, list) else [value]
    if not values:
        _error(path, "must not be empty")
    return [_token(item, f"{path}[{index}]" if isinstance(value, list) else path) for index, item in enumerate(values)]


def _validate_alias(record: dict[str, Any], path: str) -> tuple[str]:
    _shape(record, path, {"name", "type", "content", "description", "enabled", "state"}, {"updatefreq_days"})
    name = _string(record["name"], f"{path}.name", pattern=ALIAS_NAME)
    if len(name) > 32:
        _error(f"{path}.name", "must be at most 32 characters")
    alias_type = _string(record["type"], f"{path}.type")
    if alias_type not in {"host", "network", "port", "urltable", "networkgroup"}:
        _error(f"{path}.type", "must be one of host, network, port, urltable, networkgroup")
    state = _state(record["state"], f"{path}.state")
    if alias_type == 'urltable':
        if state == 'present' and 'updatefreq_days' not in record:
            _error(f"{path}.updatefreq_days", "is required for present URL tables")
        if 'updatefreq_days' in record:
            validate_frequency(record['updatefreq_days'], f"{path}.updatefreq_days")
    elif 'updatefreq_days' in record:
        _error(f"{path}.updatefreq_days", "is only allowed for URL tables")
    content = _list(record["content"], f"{path}.content")
    if not content:
        _error(f"{path}.content", "must not be empty")
    for index, item in enumerate(content):
        item_path = f"{path}.content[{index}]"
        if alias_type == "port":
            _ports(item, item_path)
        elif alias_type == 'urltable':
            validate_url(item, item_path)
        elif alias_type == 'networkgroup':
            _string(item, item_path, pattern=ALIAS_NAME)
        else:
            _ip_or_network(_string(item, item_path), item_path)
    _string(record["description"], f"{path}.description")
    _boolean(record["enabled"], f"{path}.enabled")
    _state(record["state"], f"{path}.state")
    return (name,)


def _validate_vip(record: dict[str, Any], path: str) -> tuple[str, str]:
    _shape(record, path, {"description", "interface", "address", "bind", "expand", "state"})
    _string(record["description"], f"{path}.description")
    interface = _string(record["interface"], f"{path}.interface", pattern=INTERFACE)
    address = _string(record["address"], f"{path}.address")
    if "/" not in address:
        _error(f"{path}.address", "must be an IP address with prefix")
    _ip_or_network(address, f"{path}.address")
    _boolean(record["bind"], f"{path}.bind")
    _boolean(record["expand"], f"{path}.expand")
    _state(record["state"], f"{path}.state")
    return address, interface


GATEWAY_FIELDS = {
    "name", "interface", "ip_protocol", "gateway", "default_gw", "far_gw", "monitor_disable",
    "monitor_noroute", "monitor", "force_down", "latency_low", "latency_high", "loss_low",
    "loss_high", "interval", "time_period", "loss_interval", "data_length", "priority", "weight",
    "description", "state",
}


def _validate_gateway(record: dict[str, Any], path: str) -> tuple[str, str]:
    _shape(record, path, GATEWAY_FIELDS)
    name = _string(record["name"], f"{path}.name", pattern=IDENTIFIER)
    _string(record["interface"], f"{path}.interface", pattern=INTERFACE)
    protocol = _string(record["ip_protocol"], f"{path}.ip_protocol")
    if protocol not in {"inet", "inet6"}:
        _error(f"{path}.ip_protocol", "must be inet or inet6")
    gateway = _string(record["gateway"], f"{path}.gateway")
    monitor = _string(record["monitor"], f"{path}.monitor")
    try:
        expected = 4 if protocol == "inet" else 6
        if ipaddress.ip_address(gateway).version != expected or ipaddress.ip_address(monitor).version != expected:
            _error(path, f"gateway and monitor must be {protocol} addresses")
    except ValueError:
        _error(path, f"gateway and monitor must be {protocol} addresses")
    for field in {"default_gw", "far_gw", "monitor_disable", "monitor_noroute", "force_down"}:
        _boolean(record[field], f"{path}.{field}")
    if record["default_gw"] is not False:
        _error(f"{path}.default_gw", "must be false")
    numbers = {"latency_low": (1, 9999), "latency_high": (1, 9999),
               "loss_low": (1, 99), "loss_high": (1, 99), "interval": (1, 9999),
               "time_period": (1, 9999), "data_length": (0, 9999),
               "priority": (0, 255), "weight": (1, 5)}
    for field, (minimum, maximum) in numbers.items():
        _integer(record[field], f"{path}.{field}", minimum=minimum, maximum=maximum)
    # The pinned Collection declares an integer, with no primitive range for this field.
    if type(record["loss_interval"]) is not int:
        _error(f"{path}.loss_interval", "must be an integer")
    if record["latency_low"] > record["latency_high"]:
        _error(path, "latency_low must not exceed latency_high")
    if record["loss_low"] > record["loss_high"]:
        _error(path, "loss_low must not exceed loss_high")
    _string(record["description"], f"{path}.description")
    _state(record["state"], f"{path}.state")
    return name, gateway


FILTER_REQUIRED = {"scope", "slug", "state", "enabled", "sequence", "interface", "direction", "action", "quick", "ip_protocol", "protocol", "source_net", "destination_net"}
FILTER_OPTIONAL = {"source_invert", "source_port", "destination_invert", "destination_port", "gateway", "log"}


def _validate_filter_rule(record: dict[str, Any], path: str, context: dict | None = None) -> tuple[str]:
    if "description" in record:
        _error(f"{path}.description", "is generated from scope and slug")
    _shape(record, path, FILTER_REQUIRED, FILTER_OPTIONAL)
    scope = _string(record["scope"], f"{path}.scope", pattern=IDENTITY_PART)
    slug = _string(record["slug"], f"{path}.slug", pattern=IDENTITY_PART)
    _state(record["state"], f"{path}.state")
    for field in {"enabled", "quick"} | ({"source_invert"} if "source_invert" in record else set()) | ({"destination_invert"} if "destination_invert" in record else set()) | ({"log"} if "log" in record else set()):
        _boolean(record[field], f"{path}.{field}")
    _integer(record["sequence"], f"{path}.sequence", minimum=1, maximum=99999)
    interfaces = _list(record["interface"], f"{path}.interface")
    for index, interface in enumerate(interfaces):
        _rule_interface(interface, f"{path}.interface[{index}]")
    for field, allowed in {"direction": {"in", "out"}, "action": {"pass", "block", "reject"}, "ip_protocol": {"inet", "inet6", "inet46"}, "protocol": {"any", "TCP", "UDP", "TCP/UDP", "ICMP", "ICMPv6"}}.items():
        value = _string(record[field], f"{path}.{field}")
        if value not in allowed:
            _error(f"{path}.{field}", f"must be one of {', '.join(sorted(allowed))}")
    source = _net_values(record["source_net"], f"{path}.source_net")
    destination = _net_values(record["destination_net"], f"{path}.destination_net")
    for values, field in ((source, "source"), (destination, "destination")):
        if record.get(f"{field}_invert", False) and len(values) != 1:
            _error(f"{path}.{field}_net", "inversion requires a single target")
    own_destinations = (set(interfaces) - set(destination) if record.get("destination_invert", False)
                        else set(interfaces) & set(destination))
    if record.get("destination_invert", False) and "any" in destination:
        own_destinations = set()
    if own_destinations and record.get("destination_invert", False) and context:
        own_destinations -= _excluded_interfaces(destination[0], own_destinations, context, record["ip_protocol"])
    if record["action"] in {"block", "reject"} and own_destinations:
        _error(f"{path}.destination_net", "deny rule must not include its own interface")
    for field in {"source_port", "destination_port"} & record.keys():
        _ports(record[field], f"{path}.{field}")
    if "gateway" in record:
        _string(record["gateway"], f"{path}.gateway")
    return (f"iaas:opnsense:filter:{scope}:{slug}",)


from .dnat import validate_dnat
from .one_to_one import validate_one_to_one
from .interface_groups import validate_interface_group

VALIDATORS = {"aliases": _validate_alias, "vips": _validate_vip, "gateways": _validate_gateway,
              "filter-rules": _validate_filter_rule, "dnat": validate_dnat,
              "one-to-one-nat": validate_one_to_one, "interface-groups": validate_interface_group}


def _validate_rule_context(value: Any) -> dict:
    context = _mapping(value, "opnsense_filter_rule_context")
    _shape(context, "opnsense_filter_rule_context", {"interface_networks", "aliases"})
    networks = _mapping(context["interface_networks"], "interface_networks")
    for interface, values in networks.items():
        _rule_interface(interface, "interface_networks key")
        values = _list(values, "interface_networks[]")
        if not values:
            _error("interface_networks[]", "must not be empty")
        for cidr in values:
            try:
                ipaddress.ip_network(_string(cidr, "interface_networks[]"), strict=True)
            except ValueError:
                _error("interface_networks[]", "requires an aligned CIDR")
    validate_document("aliases", {"opnsense_aliases": context["aliases"]})
    return context


def _excluded_interfaces(target: str, interfaces: set[str], context: dict, ip_protocol: str) -> set[str]:
    """Prove static alias coverage; dynamic URL members supply no safety proof."""
    aliases = {row["name"]: row for row in context["aliases"]
               if row["state"] == "present" and row["enabled"]}
    pending, seen, networks = [target], set(), []
    while pending:
        token = pending.pop()
        if token in seen:
            continue
        seen.add(token)
        try:
            networks.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            alias = aliases.get(token)
            if alias and alias["type"] in {"host", "network", "networkgroup"}:
                pending.extend(alias["content"])
    covered = []
    for family in (4, 6):
        covered.extend(ipaddress.collapse_addresses(net for net in networks if net.version == family))
    result = set()
    families = {"inet": {4}, "inet6": {6}, "inet46": {4, 6}}[ip_protocol]
    for interface in interfaces:
        values = context["interface_networks"].get(interface, [])
        ingress = [ipaddress.ip_network(value) for value in values
                   if ipaddress.ip_network(value).version in families]
        if {net.version for net in ingress} == families and all(
                any(net.version == other.version and net.subnet_of(other) for other in covered)
                for net in ingress):
            result.add(interface)
    return result


def validate_document(resource: str, document: Any) -> None:
    if resource not in VALIDATORS:
        _error("resource", f"unsupported resource {resource}")
    document = _mapping(document, resource)
    top_level = TOP_LEVEL[resource]
    extra = {"opnsense_filter_rule_context"} if resource == "filter-rules" else set()
    if top_level not in document or set(document) - {top_level} - extra:
        _error(resource, f"must contain only {top_level}")
    context = (_validate_rule_context(document["opnsense_filter_rule_context"])
               if "opnsense_filter_rule_context" in document else None)
    records = _list(document[top_level], top_level)
    identities: set[tuple[str, ...]] = set()
    for index, value in enumerate(records):
        path = f"{top_level}[{index}]"
        record = _mapping(value, path)
        identity = (_validate_filter_rule(record, path, context) if resource == "filter-rules"
                    else VALIDATORS[resource](record, path))
        if identity in identities:
            _error(path, f"duplicate managed identity {' / '.join(identity)}")
        identities.add(identity)
    if resource == 'aliases':
        validate_local(records)
    if resource == 'interface-groups':
        groups = {row['name'] for row in records}
        for index, group in enumerate(records):
            if group['state'] == 'present' and set(group['members']) & groups:
                _error(f'{top_level}[{index}].members', 'nested interface groups are not supported')


def validate_file(resource: str, path: Path) -> None:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        _error(str(path), "could not load YAML")
    validate_document(resource, document)


def validate_documents(documents: dict[str, Any]) -> None:
    """Validate a selected resource set and any duplicated alias facts."""
    for resource, document in documents.items():
        validate_document(resource, document)
    context = documents.get("filter-rules", {}).get("opnsense_filter_rule_context", {})
    selected = {row["name"]: row for row in documents.get("aliases", {}).get("opnsense_aliases", [])}
    for row in context.get("aliases", []):
        if row["name"] in selected and row != selected[row["name"]]:
            _error("opnsense_filter_rule_context.aliases", "conflicts with selected alias declaration")
    groups = {row["name"]: row for row in documents.get("interface-groups", {}).get("opnsense_interface_groups", [])}
    for resource in ('filter-rules', 'dnat', 'one-to-one-nat'):
        for row in documents.get(resource, {}).get(TOP_LEVEL[resource], []):
            if row['state'] != 'present':
                continue
            interfaces = row['interface'] if isinstance(row['interface'], list) else [row['interface']]
            for interface in interfaces:
                if interface in groups and groups[interface]['state'] == 'absent':
                    _error(resource + '.interface', 'references an interface group selected for deletion')
            if resource == 'filter-rules':
                continue
            for field in ('source_net', 'destination_net', 'target', 'external',
                          'source_port', 'destination_port', 'local_port'):
                alias = selected.get(row.get(field))
                if alias is None:
                    continue
                if alias['state'] == 'absent':
                    _error(resource + '.' + field, 'references an alias selected for deletion')
                if (field.endswith('port')) != (alias['type'] == 'port'):
                    _error(resource + '.' + field, 'selected alias has an incompatible type')


def validate_all(vars_dir: Path) -> None:
    try:
        documents = {resource: yaml.safe_load((vars_dir / filename).read_text(encoding="utf-8"))
                     for resource, filename in DEFAULT_RESOURCE_FILES.items()}
    except (OSError, yaml.YAMLError):
        _error(str(vars_dir), "could not load YAML")
    validate_documents(documents)
