"""Decode provider representations without losing identity or unknown fields."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from iaas_automation.common.conversion import ConversionError, convert_bool, optional_bool
from .schema import (
    _BOOL_FIELDS, _FIELD_ALIASES, _IGNORED_NATIVE_FIELDS, _INTEGER_FIELDS,
    _INVERTED_FIELDS, _LIST_FIELDS, _NATIVE_FALSE_FIELDS, _NATIVE_METADATA,
    _NATIVE_UNEXPRESSED, _SELECT_FIELDS, _STANDARD_FIELDS,
)
from .types import INTEGER, TEXT, as_list, selected


@dataclass(frozen=True)
class ConvertedRow:
    fields: dict[str, Any]
    extras: dict[str, Any]
    errors: tuple[str, ...]


# Invalid references cannot be treated as an empty reverse-reference set.
_REFERENCE_FIELDS = {"source_net", "destination_net", "target", "external", "source_port",
                     "destination_port", "local_port", "interface", "gateway", "content", "members"}
_IDENTITY_FIELDS = {"name", "address", "uuid", "id", "description"}


def _field(resource: str | None, name: str, value: Any) -> Any:
    if name in _SELECT_FIELDS:
        multiple = (name in {"members", "icmp_type", "icmpv6_type", "tcp_flags", "tcp_flags_clear", "received-on", "proto"}
                    or (name == "interface" and resource in {"filter-rules", "dnat"}))
        value = selected(value, multiple=multiple)
    if name in _BOOL_FIELDS:
        return convert_bool(value)
    if name in _INTEGER_FIELDS or name == "subnet_bits":
        return INTEGER.validate_python(value)
    if name == "updatefreq_days" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value) if float(value).is_integer() else round(value, 1))
    if name in _LIST_FIELDS.get(resource or "", set()):
        value = as_list(value)
    if (resource == "filter-rules" and value != "" and not isinstance(value, dict)
            and name in {"source_net", "destination_net", "source_port", "destination_port"}):
        value = as_list(value)
    if name in _REFERENCE_FIELDS:
        if isinstance(value, list):
            return [TEXT.validate_python(item) for item in value]
        # NAT ports also accept numeric literals under the existing schema.
        if name in {"source_port", "destination_port", "local_port"} and type(value) is int:
            return value
        return TEXT.validate_python(value)
    if name in _IDENTITY_FIELDS or name in {"type", "action", "direction", "ip_protocol", "protocol"}:
        return TEXT.validate_python(value)
    return deepcopy(value)


def convert_provider_row(resource: str | None, row: dict[str, Any]) -> ConvertedRow:
    """Structural failure raises; ordinary config failure retains decoded references.

    Every source is converted under its own contract before aliases are folded.
    Extra native data is never dumped over validated canonical fields.
    """
    if not isinstance(row, dict):
        raise ConversionError("malformed_provider_row")
    values: dict[str, Any] = {}
    extras = deepcopy(row)
    errors: list[str] = []
    sources: dict[str, list[tuple[str, Any]]] = {}
    known = (set(_FIELD_ALIASES) | set(_FIELD_ALIASES.values()) | _BOOL_FIELDS | _INTEGER_FIELDS
             | _SELECT_FIELDS | _IDENTITY_FIELDS | _REFERENCE_FIELDS | {"subnet_bits", "subnet", "network", "updatefreq_days"}
             | _NATIVE_UNEXPRESSED.get(resource or "", set())
             | set(_STANDARD_FIELDS.get(resource or "", ())))
    for key, value in row.items():
        if key in {"source", "destination"}:
            if not isinstance(value, dict):
                raise ConversionError("malformed_provider_row")
            for leaf, dest in (("network", "net"), ("port", "port"), ("not", "invert")):
                if leaf in value:
                    sources.setdefault(f"{key}_{dest}", []).append((f"{key}.{leaf}", value[leaf]))
                    extras[key].pop(leaf)
            if not extras[key]:
                extras.pop(key)
        elif key in known:
            destination = "name" if resource == "interface-groups" and key == "ifname" else _FIELD_ALIASES.get(key, key)
            sources.setdefault(destination, []).append((key, value))
            extras.pop(key)
    for name, entries in sources.items():
        decoded: list[Any] = []
        for source, value in entries:
            try:
                if source in _INVERTED_FIELDS:
                    if resource == "interface-groups" and source == "nogroup" and value == "":
                        value = False
                    value = not convert_bool(value)
                decoded.append(_field(resource, name, value))
            except (ConversionError, PydanticValidationError) as error:
                if isinstance(error, ConversionError) and error.code == "malformed_native_selector":
                    raise ConversionError(error.code) from None
                if len(entries) > 1:
                    raise ConversionError("conflicting_native_alias") from None
                identity = _IDENTITY_FIELDS - ({"description"} if resource in {"aliases", "vips", "gateways", "interface-groups"} else set())
                if name in identity or name in _REFERENCE_FIELDS:
                    raise ConversionError("invalid_identity_or_reference") from None
                errors.append(name)
        if decoded:
            if any(item != decoded[0] for item in decoded[1:]):
                raise ConversionError("conflicting_native_alias")
            values[name] = decoded[0]
    if resource == "vips" and any(key in row for key in ("subnet", "network", "subnet_bits")):
        prefix = values.get("subnet_bits")
        networks = [values[key] for key in ("subnet", "network") if key in values]
        if (not networks or not all(isinstance(network, str) for network in networks)
                or type(prefix) is not int or not 0 <= prefix <= 128):
            raise ConversionError("invalid_identity_or_reference")
        addresses = [f"{network}/{prefix}" for network in networks]
        if "address" in values:
            addresses.append(values["address"])
        if any(address != addresses[0] for address in addresses[1:]):
            raise ConversionError("conflicting_native_alias")
        values["address"] = addresses[0]
    return ConvertedRow(values, extras, tuple(sorted(set(errors))))


def unexpressed_fields(resource: str, extras: dict[str, Any], flat: dict[str, Any]) -> list[str]:
    fields = _NATIVE_UNEXPRESSED.get(resource, set())
    found: list[str] = []
    defaults = {'vips': {'mode': 'ipalias', 'advertising_base': 1, 'advertising_skew': 0},
                'gateways': {'enabled': True}, 'filter-rules': {'state_type': 'keep'}}.get(resource, {})
    for field in fields:
        value = flat.get(field)
        if field in _NATIVE_FALSE_FIELDS:
            if value is None or value == "" or optional_bool(value) is False:
                continue
            found.append(field)
            continue
        if field in {'interface_invert', 'disable_replyto', 'allow_opts'} and value not in (None, ""):
            converted = optional_bool(value)
            if converted is None:
                found.append(field)
                continue
            value = converted
        if field in defaults and str(value) == str(defaults[field]):
            continue
        if value not in (None, "", [], {}, False):
            found.append(field)
    for field, value in extras.items():
        if field in fields or field in _NATIVE_METADATA.get(resource, set()):
            continue
        if field in _IGNORED_NATIVE_FIELDS and field not in {"source", "destination"}:
            continue
        if field in {"description", "state"}:
            continue
        if value not in (None, "", [], {}):
            # Unknown keys can contain credentials; return a controlled category.
            found.append(field if field in {"source", "destination"} else "unknown_native_field")
    allowed = set(_STANDARD_FIELDS[resource]) | fields | _IGNORED_NATIVE_FIELDS | {"description", "state"} | set(defaults)
    for field, value in flat.items():
        if field not in allowed and value not in (None, "", [], {}):
            found.append("unknown_native_field")
    return sorted(set(found))
