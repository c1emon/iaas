"""Small, read-only checks for loaded port-alias PF rules.

The OPNsense 26.7.3 ``pf_statistics`` response keeps rules as the raw
``pfctl`` rule text used as dictionary keys.  This module deliberately parses
only the portions needed for a port Alias check.  It does not call OPNsense,
reload PF, or try to model the complete PF grammar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any
from uuid import UUID


PF_STATISTICS_RULES_PATH = "diagnostics/firewall/pf_statistics/rules"
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_LABEL_RE = re.compile(r'\blabel\s+"([^"]+)"')
_INDEX_RE = re.compile(r"^@(\d+)\s+")
_PORT_NUMBER = re.compile(r"^\d+$")
_PORT_RANGE = re.compile(r"^(\d+)\s*:\s*(\d+)$")
_PORT_DASH_RANGE = re.compile(r"^(\d+)\s*-\s*(\d+)$")
_PORT_OPEN_RANGE = re.compile(r"^(\d+)\s*<>\s*(\d+)$")

# Words that can follow the destination endpoint in the fixed OPNsense rule
# output.  An unknown trailing clause is intentionally treated as unsupported.
_RULE_TAIL = {
    "allow-opts",
    "binat-to",
    "dup-to",
    "flags",
    "keep",
    "label",
    "max-pkt-rate",
    "nat-to",
    "no-df",
    "no-pfsync",
    "prio",
    "queue",
    "rdr-to",
    "reply-to",
    "route-to",
    "rtable",
    "scrub",
    "set",
    "set-prio",
    "state",
    "tag",
    "tagged",
    "tos",
    "urpf-failed",
}


def check_port_alias_active(
    alias: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    consumers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare one port Alias with its related loaded PF rules.

    ``alias`` is a normalized Alias row (``name``, ``type == "port"`` and a
    list-valued ``content``).  ``consumers`` contains only the related filter
    or NAT configuration rows.  Each consumer must contain a native ``uuid``
    and may contain ``protocol``, ``source_port`` and ``destination_port``.
    ``snapshot`` is the complete decoded response from
    :data:`PF_STATISTICS_RULES_PATH`.

    The result uses the workflow's current-state statuses.  ``not_applicable``
    is emitted only for a complete snapshot and a complete consumer list with
    no consumer referring to this Alias.  No result implies activation or
    completion of a preceding write.
    """

    expected, reason = _alias_ports(alias)
    if expected is None:
        return _result("incomplete", reason or "malformed_port_alias")

    rules, reason = _snapshot_rules(snapshot)
    if rules is None:
        return _result("incomplete", reason or "incomplete_pf_statistics")

    if not isinstance(consumers, (list, tuple)):
        return _result("incomplete", "incomplete_consumer_configuration")

    related: list[dict[str, Any]] = []
    seen_uuid: set[str] = set()
    for consumer in consumers:
        if not isinstance(consumer, Mapping):
            return _result("incomplete", "malformed_consumer_configuration")
        if consumer.get("status") not in (None, "complete"):
            return _result("incomplete", "incomplete_consumer_configuration")
        enabled, reason = _consumer_is_enabled(consumer)
        if enabled is None:
            return _result("incomplete", reason or "malformed_consumer_enabled_state")
        if not enabled:
            continue
        uuid = consumer.get("uuid")
        if not _native_uuid(uuid):
            return _result("incomplete", "consumer_native_uuid_unavailable")
        uuid = str(uuid).lower()
        if uuid in seen_uuid:
            return _result("incomplete", "duplicate_consumer_native_uuid")
        seen_uuid.add(uuid)

        references, reason = _consumer_references(consumer, alias.get("name"))
        if references is None:
            return _result("incomplete", reason or "malformed_consumer_configuration")
        if references:
            if consumer.get("resource") in {"dnat", "one-to-one-nat"}:
                return _result("incomplete", "unsupported_nat_consumer_identity")
            related.append({"row": consumer, "uuid": uuid, "references": references})

    if not related:
        return _result("not_applicable", "complete_consumer_configuration_empty")

    loaded: dict[str, list[dict[str, Any]]] = {}
    for section, section_rules in rules.items():
        for raw_rule, counters in section_rules.items():
            parsed, reason = _parse_rule(raw_rule, counters, alias.get("name"))
            if parsed is None:
                # Only an associated malformed rule is material to this
                # check.  Unrelated internal rules may use other PF syntax.
                label = _rule_label(raw_rule)
                if label in {item["uuid"] for item in related}:
                    return _result("incomplete", reason or "malformed_loaded_pf_rule")
                continue
            parsed["section"] = section
            loaded.setdefault(parsed["uuid"], []).append(parsed)

    matches: list[dict[str, Any]] = []
    for item in related:
        uuid = item["uuid"]
        active = loaded.get(uuid, [])
        if not active:
            return _result("failed", "consumer_native_uuid_not_loaded", uuid=uuid)
        matching, reason = _matching_loaded_rules(active, item["row"])
        if matching is None:
            return _result("failed", reason or "loaded_port_alias_rule_mismatch", uuid=uuid, matches=matches)
        for role in item["references"]:
            expanded: list[tuple[int, int]] = []
            for rule in matching:
                ports = rule[f"{role}_ports"]
                if ports is None:
                    return _result("failed", "loaded_port_alias_rule_mismatch", uuid=uuid, matches=matches)
                expanded.extend(ports)
            if _merge_intervals(expanded) != expected:
                return _result("failed", "loaded_port_alias_rule_mismatch", uuid=uuid, matches=matches)
        for rule in matching:
            matches.append(
                {
                    "uuid": uuid,
                    "section": rule["section"],
                    "pf_index": rule["pf_index"],
                    "protocol": rule["protocol"],
                    "source_port": rule["source_port_raw"],
                    "destination_port": rule["destination_port_raw"],
                }
            )

    return _result("verified", "loaded_port_alias_matches", matches=matches)


def parse_loaded_pf_rules(
    snapshot: Mapping[str, Any],
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Parse the UUID-labelled filter rules needed by bounded consumers.

    Unlabelled internal/NAT rules are retained only as outside-scope input;
    they cannot be correlated to managed native consumers.
    """
    rules, reason = _snapshot_rules(snapshot)
    if rules is None:
        return None, reason or "incomplete_pf_statistics"
    result: list[dict[str, Any]] = []
    for section, section_rules in rules.items():
        for raw_rule, counters in section_rules.items():
            if _rule_label(raw_rule) is None:
                continue
            parsed, reason = _parse_rule(raw_rule, counters)
            if parsed is None:
                return None, reason or "malformed_loaded_pf_rule"
            parsed["section"] = section
            result.append(parsed)
    return result, None


def _result(status: str, reason: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status, "reason": reason}
    result.update(extra)
    return result


def _native_uuid(value: Any) -> bool:
    if not isinstance(value, str) or not _UUID_RE.fullmatch(value):
        return False
    try:
        return str(UUID(value)).lower() == value.lower()
    except ValueError:
        return False


def _alias_ports(alias: Mapping[str, Any]) -> tuple[tuple[tuple[int, int], ...] | None, str | None]:
    if not isinstance(alias, Mapping) or alias.get("type") != "port":
        return None, "selected_alias_is_not_port"
    name = alias.get("name")
    if not isinstance(name, str) or not name:
        return None, "malformed_port_alias_name"
    content = alias.get("content")
    if not isinstance(content, list) or not content:
        return None, "malformed_port_alias_content"
    intervals: list[tuple[int, int]] = []
    for item in content:
        if not isinstance(item, str):
            return None, "malformed_port_alias_content"
        parsed = _port_token(item.strip())
        if parsed is None:
            return None, "unsupported_port_alias_content"
        intervals.extend(parsed)
    return _merge_intervals(intervals), None


def _snapshot_rules(snapshot: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]] | None, str | None]:
    if not isinstance(snapshot, Mapping):
        return None, "malformed_pf_statistics_snapshot"
    if snapshot.get("status") not in (None, "complete"):
        return None, "incomplete_pf_statistics_snapshot"
    root = snapshot.get("rules")
    if not isinstance(root, Mapping):
        return None, "missing_pf_statistics_rules"
    result: dict[str, Mapping[str, Any]] = {}
    for section in ("filter rules", "nat rules"):
        section_rules = root.get(section)
        if not isinstance(section_rules, Mapping):
            return None, "incomplete_pf_statistics_rules"
        for raw_rule, counters in section_rules.items():
            if not isinstance(raw_rule, str) or not raw_rule or not isinstance(counters, Mapping):
                return None, "malformed_pf_statistics_rule"
            if not _balanced_rule_text(raw_rule):
                return None, "malformed_pf_statistics_rule"
        result[section] = section_rules
    return result, None


def _balanced_rule_text(value: str) -> bool:
    pairs = {"{": "}", "(": ")", "[": "]"}
    stack: list[str] = []
    quote = False
    escaped = False
    for char in value:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = False
            continue
        if char == '"':
            quote = True
        elif char in pairs:
            stack.append(pairs[char])
        elif char in pairs.values():
            if not stack or stack.pop() != char:
                return False
    return not quote and not stack


def _consumer_references(
    consumer: Mapping[str, Any], alias_name: Any
) -> tuple[dict[str, tuple[str, ...]] | None, str | None]:
    if not isinstance(alias_name, str) or not alias_name:
        return None, "malformed_port_alias_name"
    references: dict[str, tuple[str, ...]] = {}
    for field, role in (("source_port", "source"), ("destination_port", "destination")):
        value = consumer.get(field)
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        if any(not isinstance(item, str) for item in values):
            return None, "malformed_consumer_port_configuration"
        values = tuple(item for item in values if item)
        if alias_name in values:
            references[role] = values
        elif any(alias_name == item.lstrip("$") for item in values):
            references[role] = values
    # A translated/local port is a different PF clause.  This focused
    # checker cannot claim that a source/destination expansion verifies it.
    for field in ("local_port", "target_port"):
        value = consumer.get(field)
        values = value if isinstance(value, list) else [value]
        if any(isinstance(item, str) and item.lstrip("$") == alias_name for item in values):
            return None, "unsupported_consumer_translated_port_role"
    return references, None


def _consumer_is_enabled(consumer: Mapping[str, Any]) -> tuple[bool | None, str | None]:
    disabled = consumer.get("disabled")
    enabled = consumer.get("enabled")
    if disabled is not None and type(disabled) is not bool:
        return None, "malformed_consumer_enabled_state"
    if enabled is not None and type(enabled) is not bool:
        return None, "malformed_consumer_enabled_state"
    if disabled is True or enabled is False:
        return False, None
    return True, None


def _rule_label(raw_rule: str) -> str | None:
    match = _LABEL_RE.search(raw_rule)
    if not match:
        return None
    value = match.group(1).lower()
    return value if _native_uuid(value) else None


def _parse_rule(
    raw_rule: Any, counters: Mapping[str, Any], alias_name: Any = None
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw_rule, str) or not isinstance(counters, Mapping):
        return None, "malformed_loaded_pf_rule"
    label = _rule_label(raw_rule)
    if label is None:
        return None, "loaded_pf_rule_uuid_unavailable"
    words = _top_level_words(raw_rule)
    on_index = next((i for i, word in enumerate(words) if word[0] == "on"), None)
    on = None
    if on_index is not None and on_index + 1 < len(words):
        on = raw_rule[words[on_index + 1][1] : words[on_index + 1][2]]
    proto_index = next((i for i, word in enumerate(words) if word[0] == "proto"), None)
    protocol: tuple[str, ...] | None = None
    if proto_index is not None:
        if proto_index + 1 >= len(words):
            protocol_end = len(raw_rule)
        else:
            candidate = words[proto_index + 1]
            protocol_end = candidate[1] if candidate[0] in {"from", "to"} else candidate[2]
        protocol = _expression_values(raw_rule, words[proto_index][2], protocol_end)
        if protocol is None:
            return None, "unsupported_loaded_pf_rule_protocol"
        protocol = tuple(item.lower() for item in protocol)
    from_index = next((i for i, word in enumerate(words) if word[0] == "from"), None)
    to_index = next(
        (i for i, word in enumerate(words)
         if word[0] == "to" and (from_index is None or i > from_index)),
        None,
    )
    if from_index is None or to_index is None:
        return None, "malformed_loaded_pf_rule_endpoints"
    tail_index = next(
        (i for i in range(to_index + 1, len(words)) if words[i][0] in _RULE_TAIL),
        len(words),
    )
    source = _parse_endpoint(raw_rule[words[from_index][2] : words[to_index][1]])
    destination_end = words[tail_index][1] if tail_index < len(words) else None
    destination = _parse_endpoint(raw_rule[words[to_index][2] : destination_end])
    if source is None or destination is None:
        return None, "unsupported_loaded_pf_rule_endpoint"
    index_match = _INDEX_RE.match(raw_rule)
    return {
        "uuid": label,
        "pf_index": int(index_match.group(1)) if index_match else None,
        "on": on,
        "route_to": _rule_option(raw_rule, "route-to"),
        "section": "",  # filled by the caller's section-independent result
        "protocol": protocol,
        "source_port_raw": source[1],
        "destination_port_raw": destination[1],
        "source_ports": source[2],
        "destination_ports": destination[2],
        "raw": raw_rule,
        "counters": dict(counters),
    }, None


def _parse_endpoint(value: str) -> tuple[str, str | None, tuple[tuple[int, int], ...] | None] | None:
    value = value.strip()
    if not value:
        return None
    address, _, rest = value.partition(" ")
    if not address or address.startswith("!") or address.startswith("$"):
        return None
    rest = rest.strip()
    if not rest:
        return address, None, None
    if not rest.startswith("port "):
        return None
    expression = rest[5:].strip()
    parsed = _parse_port_expression(expression)
    if parsed is None:
        return None
    return address, expression, parsed


def _rule_option(raw_rule: str, option: str) -> tuple[str, str] | None:
    """Read one fixed two-token parenthesized PF route option."""
    words = _top_level_words(raw_rule)
    index = next((i for i, word in enumerate(words) if word[0] == option), None)
    if index is None:
        return None
    start = words[index][2]
    while start < len(raw_rule) and raw_rule[start].isspace():
        start += 1
    if start >= len(raw_rule) or raw_rule[start] != "(":
        return None
    end = _matching_delimiter(raw_rule, start, "(", ")")
    if end is None:
        return None
    parts = raw_rule[start + 1 : end].split()
    return (parts[0], parts[1]) if len(parts) == 2 else None


def _matching_delimiter(value: str, start: int, opening: str, closing: str) -> int | None:
    depth = 0
    quote = False
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = False
            continue
        if char == '"':
            quote = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def _parse_port_expression(value: str) -> tuple[tuple[int, int], ...] | None:
    if not value or "$" in value or "<" in value and "<>" not in value:
        return None
    if value.startswith("{"):
        if not value.endswith("}"):
            return None
        tokens = value[1:-1].strip().split()
        if not tokens:
            return None
        intervals: list[tuple[int, int]] = []
        for token in tokens:
            parsed = _port_token(token)
            if parsed is None:
                return None
            intervals.extend(parsed)
        return _merge_intervals(intervals)
    return _port_token(value)


def _port_token(value: str) -> tuple[tuple[int, int], ...] | None:
    if not value or any(char in value for char in "{}$<>"):
        match = _PORT_OPEN_RANGE.fullmatch(value)
        if not match:
            return None
        low, high = int(match.group(1)), int(match.group(2))
        if not 0 <= low < high <= 65535:
            return None
        return ((low + 1, high - 1),) if low + 1 <= high - 1 else ()
    if _PORT_NUMBER.fullmatch(value):
        number = int(value)
        return ((number, number),) if 0 <= number <= 65535 else None
    match = _PORT_RANGE.fullmatch(value)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        return ((low, high),) if 0 <= low <= high <= 65535 else None
    match = _PORT_DASH_RANGE.fullmatch(value)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        return ((low, high),) if 0 <= low <= high <= 65535 else None
    return None


def _expression_values(text: str, start: int, end: int) -> tuple[str, ...] | None:
    value = text[start:end].strip()
    if value.startswith("{") and value.endswith("}"):
        values = tuple(value[1:-1].split())
    elif value and re.fullmatch(r"[A-Za-z0-9_-]+", value):
        values = (value,)
    else:
        return None
    return values or None


def _top_level_words(value: str) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    brace = paren = bracket = 0
    quote = False
    escaped = False
    i = 0
    while i < len(value):
        char = value[i]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = False
            i += 1
            continue
        if char == '"':
            quote = True
            i += 1
            continue
        if char == "{":
            brace += 1
        elif char == "}":
            brace -= 1
        elif char == "(":
            paren += 1
        elif char == ")":
            paren -= 1
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket -= 1
        elif not (brace or paren or bracket) and (char.isalnum() or char in "_-"):
            start = i
            while i < len(value) and (value[i].isalnum() or value[i] in "_-"):
                i += 1
            result.append((value[start:i].lower(), start, i))
            continue
        i += 1
    if quote or brace != 0 or paren != 0 or bracket != 0:
        return []
    return result


def _matching_loaded_rules(
    active: Sequence[Mapping[str, Any]], consumer: Mapping[str, Any]
) -> tuple[list[Mapping[str, Any]] | None, str | None]:
    configured_protocol = _configured_protocols(consumer.get("protocol"))
    if configured_protocol is None:
        return None, "malformed_consumer_protocol"
    matching = [
        rule for rule in active
        if tuple(rule["protocol"] or ("any",)) == configured_protocol
    ]
    return (matching, None) if matching else (None, "loaded_port_alias_protocol_mismatch")


def _configured_protocols(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return ("any",)
    values = value if isinstance(value, list) else [value]
    if any(not isinstance(item, str) for item in values):
        return None
    result = tuple(item.lower() for item in values if item)
    if not result:
        return ("any",)
    return tuple(sorted(set(result)))


def _merge_intervals(intervals: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not intervals:
        return ()
    ordered = sorted(intervals)
    merged: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for low, high in ordered[1:]:
        if low <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low, high])
    return tuple((low, high) for low, high in merged)
