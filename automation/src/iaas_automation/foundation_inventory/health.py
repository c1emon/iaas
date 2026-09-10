"""Explicit online read-only foundation health probes.

These probes are intentionally separate from offline validation so the CLI can
keep generated-doc checks safe while still offering operator-driven live checks.
"""

from __future__ import annotations

import random
import socket
import ssl
import struct
from dataclasses import dataclass
from typing import Any, Callable, Literal, cast
from urllib import error as urllib_error
from urllib import request as urllib_request

from iaas_automation.pve_inventory.checks.results import CheckResult, Severity


ProbeStatus = Literal["passed", "failed", "unreachable", "skipped"]


@dataclass(frozen=True)
class ProbeOutcome:
    status: ProbeStatus
    message: str


Probe = Callable[[dict[str, Any]], ProbeOutcome]


def _timeout_seconds(check: dict[str, Any]) -> float:
    return float(check.get("timeout_seconds") or 3)


def _as_target_host_port(target: str) -> tuple[str, int]:
    host, port_text = target.rsplit(":", 1)
    return host, int(port_text)


def probe_tcp(check: dict[str, Any]) -> ProbeOutcome:
    host, port = _as_target_host_port(check["target"])
    try:
        with socket.create_connection((host, port), timeout=_timeout_seconds(check)):
            return ProbeOutcome("passed", f"tcp {host}:{port} reachable")
    except (socket.timeout, ConnectionError, OSError) as exc:
        return ProbeOutcome("unreachable", f"tcp {host}:{port} unreachable: {exc}")


def _http_request(check: dict[str, Any]) -> ProbeOutcome:
    """Run a GET-like HTTP probe and classify the response without mutating state."""
    expected = set(check.get("expected_status") or [])
    url = check["target"]
    req = urllib_request.Request(url, method="GET")
    try:
        context = ssl.create_default_context(cafile=check.get("ca_file"))
        with urllib_request.urlopen(req, timeout=_timeout_seconds(check), context=context) as response:
            status = int(response.status)
            if expected and status not in expected:
                return ProbeOutcome("failed", f"HTTP status {status} not in {sorted(expected)}")
            if not expected and not (200 <= status < 400):
                return ProbeOutcome("failed", f"HTTP status {status}")
            return ProbeOutcome("passed", f"HTTP status {status}")
    except urllib_error.HTTPError as exc:
        status = int(exc.code)
        if expected and status in expected:
            return ProbeOutcome("passed", f"HTTP status {status}")
        if not expected and 200 <= status < 400:
            return ProbeOutcome("passed", f"HTTP status {status}")
        return ProbeOutcome("failed", f"HTTP status {status}")
    except (ssl.SSLError, ValueError):
        return ProbeOutcome("failed", "HTTPS certificate or trust configuration failed")
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        if isinstance(getattr(exc, "reason", None), ssl.SSLError):
            return ProbeOutcome("failed", "HTTPS certificate verification failed")
        if check.get("ca_file") and isinstance(exc, FileNotFoundError):
            return ProbeOutcome("failed", "HTTPS trust file is unavailable")
        return ProbeOutcome("unreachable", "HTTP endpoint unreachable")


def probe_http(check: dict[str, Any]) -> ProbeOutcome:
    return _http_request(check)


def probe_https(check: dict[str, Any]) -> ProbeOutcome:
    return _http_request(check)


def _encode_dns_name(name: str) -> bytes:
    """Encode a DNS name into the wire format used by the UDP query builder."""
    parts = [part.encode("idna") for part in name.rstrip(".").split(".")]
    if any(not part or len(part) > 63 for part in parts):
        raise ValueError("invalid DNS label")
    encoded = b"".join(bytes([len(part)]) + part for part in parts)
    if len(encoded) > 254:
        raise ValueError("DNS name too long")
    return encoded + b"\x00"


def _decode_dns_name(payload: bytes, offset: int) -> tuple[str, int]:
    """Decode a possibly-compressed DNS name from a response payload."""
    labels: list[str] = []
    jumped = False
    original_offset = offset
    visited: set[int] = set()
    name_length = 0
    while True:
        if offset >= len(payload) or offset in visited or len(visited) >= 128:
            raise ValueError("invalid DNS compression or offset")
        visited.add(offset)
        length = payload[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(payload):
                raise ValueError("truncated DNS pointer")
            pointer = ((length & 0x3F) << 8) | payload[offset + 1]
            if not jumped:
                original_offset = offset + 2
            offset = pointer
            jumped = True
            continue
        if length > 63 or offset + 1 + length > len(payload):
            raise ValueError("invalid DNS label")
        name_length += length + 1
        if name_length > 254:
            raise ValueError("DNS name too long")
        offset += 1
        labels.append(payload[offset : offset + length].decode("idna"))
        offset += length
    return ".".join(labels), (original_offset if jumped else offset)


def _dns_answers(payload: bytes, packet_id: int, query: str, qtype: int) -> list[str]:
    if len(payload) < 12 or len(payload) > 4096:
        raise ValueError("invalid DNS packet size")
    response_id, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", payload[:12])
    if response_id != packet_id or not flags & 0x8000 or flags & 0x7A0F or qdcount != 1 or ancount > 128:
        raise ValueError("DNS identity, status, truncation or count mismatch")
    question, offset = _decode_dns_name(payload, 12)
    question_type, question_class = struct.unpack("!HH", payload[offset:offset + 4])
    if question.lower() != query.rstrip(".").lower() or question_type != qtype or question_class != 1:
        raise ValueError("DNS question mismatch")
    offset += 4
    records: list[tuple[str, int, str]] = []
    for _ in range(ancount):
        owner, offset = _decode_dns_name(payload, offset)
        kind, record_class, _, length = struct.unpack("!HHIH", payload[offset:offset + 10])
        offset += 10
        end = offset + length
        if end > len(payload) or record_class != 1:
            raise ValueError("invalid DNS record")
        data = payload[offset:end]
        value = None
        if kind in {1, 28}:
            family, size = (socket.AF_INET, 4) if kind == 1 else (socket.AF_INET6, 16)
            if length != size:
                raise ValueError("invalid DNS address")
            value = socket.inet_ntop(family, data)
        elif kind == 5:
            value, consumed = _decode_dns_name(payload, offset)
            if consumed != end:
                raise ValueError("invalid CNAME length")
            value = value.lower()
        elif kind == 16:
            chunks = []
            position = 0
            while position < len(data):
                size = data[position]
                position += 1
                if position + size > len(data):
                    raise ValueError("truncated TXT")
                chunks.append(data[position:position + size])
                position += size
            value = b"".join(chunks).decode("utf-8")
        elif kind == 33:
            if length < 7:
                raise ValueError("truncated SRV")
            priority, weight, port = struct.unpack("!HHH", data[:6])
            target, consumed = _decode_dns_name(payload, offset + 6)
            if consumed != end:
                raise ValueError("invalid SRV length")
            value = f"{priority} {weight} {port} {target.lower()}"
        if value is not None:
            records.append((owner.lower(), kind, value))
        offset = end
    owners = {query.rstrip(".").lower()}
    for _ in records:
        expanded = owners | {value for owner, kind, value in records if owner in owners and kind == 5}
        if expanded == owners:
            break
        owners = expanded
    return [value for owner, kind, value in records if owner in owners and (qtype == 255 or kind == qtype)]


def probe_dns(check: dict[str, Any]) -> ProbeOutcome:
    """Query only the caller's resolver; classify bounded, matching UDP answers."""
    resolver = check.get("resolver")
    if not resolver:
        return ProbeOutcome("failed", "DNS requires an explicit resolver")
    try:
        query = check["target"]
        qtype = {"A": 1, "AAAA": 28, "CNAME": 5, "TXT": 16, "SRV": 33, "ANY": 255}[
            str(check.get("record_type") or "a").upper()]
        packet_id = random.randint(0, 65535)
        request = struct.pack("!HHHHHH", packet_id, 0x0100, 1, 0, 0, 0)
        request += _encode_dns_name(query) + struct.pack("!HH", qtype, 1)
        family, socktype, protocol, _, destination = socket.getaddrinfo(resolver, 53, type=socket.SOCK_DGRAM)[0]
        with socket.socket(family, socktype, protocol) as sock:
            sock.settimeout(_timeout_seconds(check))
            # A connected UDP socket accepts replies only from the selected resolver/port.
            sock.connect(destination)
            sock.send(request)
            payload = sock.recv(4097)
        answers = _dns_answers(payload, packet_id, query, qtype)
        expected = check.get("expected_answer")
        if expected is not None:
            expected_set = set(expected if isinstance(expected, list) else [expected])
            if not expected_set.intersection(answers):
                return ProbeOutcome("failed", "DNS did not return an expected answer")
        elif not answers:
            return ProbeOutcome("failed", "DNS returned no supported answers")
        return ProbeOutcome("passed", f"DNS returned {len(answers)} matching answer(s)")
    except (ValueError, KeyError, IndexError, struct.error, UnicodeError):
        return ProbeOutcome("failed", "DNS response is malformed, truncated, unsupported or mismatched")
    except (socket.timeout, OSError):
        return ProbeOutcome("unreachable", "DNS resolver unreachable")


def probe_api(check: dict[str, Any]) -> ProbeOutcome:
    return _http_request(check)


PROBE_DISPATCH: dict[str, Probe] = {
    "tcp": probe_tcp,
    "http": probe_http,
    "https": probe_https,
    "dns": probe_dns,
    "api": probe_api,
}


def run_health_checks(model: dict[str, Any], probe_dispatch: dict[str, Probe] | None = None) -> list[CheckResult]:
    """Run explicit read-only health probes for each declared service."""
    dispatch = probe_dispatch or PROBE_DISPATCH
    results: list[CheckResult] = []
    for service in model["foundation_services"]:
        check = service.get("health_check")
        check_id = f"foundation.health.{service['name']}"
        if check is None:
            results.append(CheckResult("SKIP", check_id, f"skipped: {service['name']} has no health check"))
            continue
        probe = dispatch.get(check["type"])
        if probe is None:
            results.append(CheckResult("SKIP", check_id, f"skipped: {service['name']} has unsupported health probe {check['type']}"))
            continue
        try:
            outcome = probe(check)
        except Exception:  # Keep untrusted endpoint/parser exception text out of reports.
            outcome = ProbeOutcome("failed", "probe could not classify the response")
        # Map probe outcomes onto the shared PVE result severities for reporting.
        severity = cast(Severity, {"passed": "PASS", "failed": "FAIL", "unreachable": "FAIL", "skipped": "SKIP"}[outcome.status])
        results.append(CheckResult(severity, check_id, f"{outcome.status}: {service['name']} - {outcome.message}"))
    return results
