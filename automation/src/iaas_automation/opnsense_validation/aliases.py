"""Alias dependency planning over desired and observed definitions."""

from decimal import Decimal, InvalidOperation
import ipaddress
import math
import re
from urllib.parse import parse_qsl, urlsplit

from iaas_automation.common.errors import ValidationError


ALIAS_NAME = re.compile(r"(?:[A-Za-z]|(?:[_A-Za-z][A-Za-z0-9]|[A-Za-z][_A-Za-z0-9])[_A-Za-z0-9]{0,29})")
ADDRESS_TYPES = {"host", "network", "urltable", "networkgroup"}


def fail(message):
    raise ValidationError("opnsense alias validation failed: " + message)


def validate_frequency(value, path):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9])?", value):
        fail(path + " must be a quoted decimal with at most one fractional digit")
    number = Decimal(value)
    converted = float(value)
    if number < Decimal("0.1") or not math.isfinite(converted):
        fail(path + " must be finite and at least 0.1 days")
    # Match the pinned Collection's float conversion and rounding exactly.
    rounded = round(converted, None if str(converted).endswith('.0') else 1)
    if Decimal(str(rounded)) != number:
        fail(path + " loses precision in the pinned Collection")


def validate_url(value, path):
    try:
        if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
            raise ValueError
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or '#' in value:
            raise ValueError
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
        # The pinned Collection accepts dotted DNS names or IPv4 URL hosts,
        # excludes IPv4 first octets outside 1..223 and last octets 0/255,
        # and requires any explicit port to contain two to five digits.
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            if not re.fullmatch(r'(?:[a-z\u00a1-\uffff0-9](?:-?[a-z\u00a1-\uffff0-9])*\.)+[a-z\u00a1-\uffff]{2,}',
                                parsed.hostname, re.IGNORECASE):
                raise ValueError
        else:
            if address.version != 4 or not 1 <= address.packed[0] <= 223 or not 1 <= address.packed[-1] <= 254:
                raise ValueError
        if ':' in parsed.netloc and not re.fullmatch(r'[0-9]{2,5}', parsed.netloc.rsplit(':', 1)[1]):
            raise ValueError
        if any(key.lower() in {"token", "access_token", "api_key", "key", "password", "secret", "auth", "signature", "sig"}
               for key, _ in parse_qsl(parsed.query)):
            raise ValueError
    except (ValueError, TypeError):
        fail(path + " must be a provider-compatible absolute non-secret HTTP(S) URL without userinfo or fragment")


def dependency_order(graph):
    """Stable dependency-first order; no recursive traversal limit."""
    pending = {name: set(members) & graph.keys() for name, members in graph.items()}
    ordered = []
    while pending:
        ready = sorted(name for name, members in pending.items() if not members)
        if not ready:
            fail("alias dependency cycle")
        ordered.extend(ready)
        for name in ready:
            del pending[name]
        for members in pending.values():
            members.difference_update(ready)
    return ordered


def validate_local(records):
    local = {record['name']: record for record in records}
    graph = {}
    for name, record in local.items():
        if record['state'] != 'present':
            continue
        members = record['content'] if record['type'] == 'networkgroup' else []
        graph[name] = members
        if len(members) != len(set(members)) or name in members:
            fail("surviving group has duplicate members or self-reference")
        for member in members:
            if member in local and (local[member]['state'] == 'absent' or local[member]['type'] not in ADDRESS_TYPES):
                fail("surviving group references an absent or non-address local member")
    dependency_order(graph)


def live_dependencies(record):
    kind = record.get('type')
    if kind not in {'host', 'network', 'networkgroup'}:
        return []
    content = record.get('content')
    if not isinstance(content, list) or not all(isinstance(item, str) for item in content):
        fail("reachable external alias content is unsupported")
    if kind == 'networkgroup':
        if not content or any(not ALIAS_NAME.fullmatch(item) for item in content) or len(set(content)) != len(content):
            fail("reachable group dependency syntax is unsupported")
        return content
    members = []
    for item in content:
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError:
            if ALIAS_NAME.fullmatch(item):
                members.append(item)
            elif kind == 'host' and len(item) <= 253 and re.fullmatch(
                r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\.?', item
            ):
                continue  # A DNS leaf cannot be an alias name under the provider syntax.
            else:
                fail("reachable external address dependency syntax is unsupported")
    return members


def plan_aliases(records, live):
    """Never adopt external definitions; inspect only reachable live dependencies."""
    if not isinstance(live, list):
        fail("live alias definitions are unavailable")
    observed = {}
    for record in live:
        if not isinstance(record, dict) or not isinstance(record.get('name'), str) or record['name'] in observed:
            fail("live alias identity is malformed or ambiguous")
        observed[record['name']] = record
    local = {record['name']: record for record in records}
    present = {name: record for name, record in local.items() if record['state'] == 'present'}
    absent = set(local) - present.keys()
    for name, record in present.items():
        if name in observed and observed[name].get('type') != record['type']:
            fail("existing alias type changes require an explicit migration")
    effective = {name: record for name, record in observed.items() if name not in absent} | present
    graph = {}
    todo = [name for name, record in present.items() if record['type'] == 'networkgroup']
    while todo:
        name = todo.pop()
        if name in graph:
            continue
        record = effective.get(name)
        if record is None or record.get('type') not in ADDRESS_TYPES:
            fail("reachable alias dependency is missing or not address-compatible")
        members = live_dependencies(record)
        graph[name] = members
        todo.extend(members)
    dependency_order(graph)
    # Include transitive external edges when sorting local updates.
    for name in present:
        graph.setdefault(name, [])
    updates = [local[name] for name in dependency_order(graph) if name in present]
    deletion_graph = {}
    for name in sorted(absent & observed.keys()):
        record = observed[name]
        deletion_graph[name] = live_dependencies(record)
    removals = [local[name] for name in reversed(dependency_order(deletion_graph))]
    changed = bool(removals)
    for name, record in present.items():
        old = observed.get(name)
        if old is None:
            changed = True
            continue
        for field in ('type', 'description', 'enabled'):
            changed |= old.get(field) != record[field]
        changed |= sorted(map(str, old.get('content', []))) != sorted(map(str, record['content']))
        if record['type'] == 'urltable':
            try:
                changed |= Decimal(str(old.get('updatefreq_days'))) != Decimal(record['updatefreq_days'])
            except (InvalidOperation, ValueError, TypeError):
                changed = True
    return {'batches': [[record] for record in updates + removals], 'would_change': changed,
            'present_count': len(updates), 'removal_count': len(removals)}
