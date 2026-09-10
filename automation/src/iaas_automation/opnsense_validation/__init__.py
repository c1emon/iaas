from __future__ import annotations

import ipaddress
from pathlib import Path
import re
from typing import Any, NoReturn

import yaml

from iaas_automation.common.errors import ValidationError
from .aliases import ALIAS_NAME, validate_frequency, validate_local, validate_url


RESOURCE_FILES = {
    "aliases": "aliases.yml",
    "vips": "vips.yml",
    "gateways": "gateways.yml",
    "filter-rules": "filter-rules.yml",
}
TOP_LEVEL = {
    "aliases": "opnsense_aliases",
    "vips": "opnsense_vips",
    "gateways": "opnsense_gateways",
    "filter-rules": "opnsense_filter_rules",
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


def _validate_filter_rule(record: dict[str, Any], path: str) -> tuple[str]:
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
        _string(interface, f"{path}.interface[{index}]", pattern=INTERFACE)
    for field, allowed in {"direction": {"in", "out"}, "action": {"pass", "block", "reject"}, "ip_protocol": {"inet", "inet6", "inet46"}, "protocol": {"any", "TCP", "UDP", "TCP/UDP", "ICMP", "ICMPv6"}}.items():
        value = _string(record[field], f"{path}.{field}")
        if value not in allowed:
            _error(f"{path}.{field}", f"must be one of {', '.join(sorted(allowed))}")
    _net_values(record["source_net"], f"{path}.source_net")
    destination = _net_values(record["destination_net"], f"{path}.destination_net")
    own_destinations = (set(interfaces) - set(destination) if record.get("destination_invert", False)
                        else set(interfaces) & set(destination))
    if record.get("destination_invert", False) and "any" in destination:
        own_destinations = set()
    if record["action"] in {"block", "reject"} and own_destinations:
        _error(f"{path}.destination_net", "deny rule must not include its own interface")
    for field in {"source_port", "destination_port"} & record.keys():
        _ports(record[field], f"{path}.{field}")
    if "gateway" in record:
        _string(record["gateway"], f"{path}.gateway")
    return (f"iaas:opnsense:filter:{scope}:{slug}",)


VALIDATORS = {"aliases": _validate_alias, "vips": _validate_vip, "gateways": _validate_gateway, "filter-rules": _validate_filter_rule}


def validate_document(resource: str, document: Any) -> None:
    if resource not in VALIDATORS:
        _error("resource", f"unsupported resource {resource}")
    document = _mapping(document, resource)
    top_level = TOP_LEVEL[resource]
    if set(document) != {top_level}:
        _error(resource, f"must contain only {top_level}")
    records = _list(document[top_level], top_level)
    identities: set[tuple[str, ...]] = set()
    for index, value in enumerate(records):
        path = f"{top_level}[{index}]"
        identity = VALIDATORS[resource](_mapping(value, path), path)
        if identity in identities:
            _error(path, f"duplicate managed identity {' / '.join(identity)}")
        identities.add(identity)
    if resource == 'aliases':
        validate_local(records)


def validate_file(resource: str, path: Path) -> None:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        _error(str(path), "could not load YAML")
    validate_document(resource, document)


def validate_all(vars_dir: Path) -> None:
    for resource, filename in RESOURCE_FILES.items():
        validate_file(resource, vars_dir / filename)
