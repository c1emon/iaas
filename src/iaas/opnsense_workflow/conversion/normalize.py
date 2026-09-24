"""Canonical comparison of already-admitted desired or observed records."""
from copy import deepcopy
from decimal import Decimal
from typing import Any
from .schema import DEFAULTS, LIST_FIELDS, STANDARD_FIELDS
from .types import OBJECT_LIST, as_list as _as_list

def _copy_value(value: Any) -> Any:
    return deepcopy(value)


def _sort_list(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    items = OBJECT_LIST.validate_python(value)
    return sorted((_copy_value(item) for item in items), key=lambda item: repr(item))


def normalize_standard_record(resource: str, record: dict[str, Any]) -> dict[str, Any]:
    """Return a validator-backed, comparison-stable standard declaration.

    This function deliberately does not infer resource identity or ownership.
    It only supplies provider-compatible optional defaults and stable ordering
    for fields whose Collection representation is a set-like list. ``state``
    remains explicit. Full cross-resource validation belongs to the caller's
    selected declaration document, where filter safety context is available.
    """

    if resource not in STANDARD_FIELDS:
        raise ValueError(f"unsupported OPNsense resource: {resource}")
    # Keep this runtime boundary for untyped provider callers; strict callers are statically typed.
    if not isinstance(record, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError("resource declaration must be a mapping")
    result = deepcopy(record)
    if result.get("state") == "present":
        for field, default in DEFAULTS.get(resource, {}).items():
            result.setdefault(field, deepcopy(default))
        for field in LIST_FIELDS[resource]:
            if field in result:
                result[field] = _sort_list(result[field])
        if resource == "filter-rules":
            for field in ("source_net", "destination_net", "source_port", "destination_port"):
                if field in result:
                    converted = _as_list(result[field])
                    values: list[object]
                    if isinstance(converted, list):
                        values = OBJECT_LIST.validate_python(converted)
                    else:
                        values = [converted]
                    result[field] = _sort_list([str(item) for item in values])
            protocol = result.get('protocol')
            if isinstance(protocol, str):
                result['protocol'] = {'icmpv6': 'ICMPv6', 'any': 'any'}.get(protocol.lower(), protocol.upper())
        elif resource == "dnat":
            for field in ("source_net", "destination_net"):
                if isinstance(result.get(field), list):
                    result[field] = ",".join(sorted(str(item) for item in result[field]))
            for field in ("source_port", "destination_port", "local_port"):
                if field in result and isinstance(result[field], int):
                    result[field] = str(result[field])
            if isinstance(result.get("protocol"), str):
                result["protocol"] = result["protocol"].lower()
        if resource == 'aliases' and result.get('type') == 'urltable' and 'updatefreq_days' in result:
            result['updatefreq_days'] = format(Decimal(str(result['updatefreq_days'])).normalize(), 'f')
    return result
