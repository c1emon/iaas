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
    context = ssl._create_unverified_context()
    req = urllib_request.Request(url, method="GET")
    try:
        with urllib_request.urlopen(req, timeout=_timeout_seconds(check), context=context) as response:
            status = int(response.status)
            if expected and status not in expected:
                return ProbeOutcome("failed", f"GET {url} returned {status} not in {sorted(expected)}")
            if not expected and not (200 <= status < 400):
                return ProbeOutcome("failed", f"GET {url} returned {status}")
            return ProbeOutcome("passed", f"GET {url} returned {status}")
    except urllib_error.HTTPError as exc:
        status = int(exc.code)
        if expected and status in expected:
            return ProbeOutcome("passed", f"GET {url} returned {status}")
        if not expected and 200 <= status < 400:
            return ProbeOutcome("passed", f"GET {url} returned {status}")
        return ProbeOutcome("failed", f"GET {url} returned {status}")
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        return ProbeOutcome("unreachable", f"GET {url} unreachable: {exc}")


def probe_http(check: dict[str, Any]) -> ProbeOutcome:
    return _http_request(check)


def probe_https(check: dict[str, Any]) -> ProbeOutcome:
    return _http_request(check)


def _encode_dns_name(name: str) -> bytes:
    """Encode a DNS name into the wire format used by the UDP query builder."""
    parts = [part for part in name.split(".") if part]
    encoded = b"".join(bytes([len(part)]) + part.encode("idna") for part in parts)
    return encoded + b"\x00"


def _decode_dns_name(payload: bytes, offset: int) -> tuple[str, int]:
    """Decode a possibly-compressed DNS name from a response payload."""
    labels: list[str] = []
    jumped = False
    original_offset = offset
    while True:
        length = payload[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            pointer = ((length & 0x3F) << 8) | payload[offset + 1]
            if not jumped:
                original_offset = offset + 2
            offset = pointer
            jumped = True
            continue
        offset += 1
        labels.append(payload[offset : offset + length].decode("idna"))
        offset += length
    return ".".join(labels), (original_offset if jumped else offset)


def probe_dns(check: dict[str, Any]) -> ProbeOutcome:
    """Send a minimal UDP DNS query and check for a usable answer."""
    resolver = check.get("resolver") or "8.8.8.8"
    query = check["target"]
    record_type = str(check.get("record_type") or "a").upper()
    qtype = {"A": 1, "AAAA": 28, "CNAME": 5, "TXT": 16, "SRV": 33, "ANY": 255}.get(record_type, 1)
    packet_id = random.randint(0, 65535)
    header = struct.pack("!HHHHHH", packet_id, 0x0100, 1, 0, 0, 0)
    question = _encode_dns_name(query) + struct.pack("!HH", qtype, 1)
    request = header + question
    expected_answers = check.get("expected_answer")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(_timeout_seconds(check))
            sock.sendto(request, (resolver, 53))
            payload, _ = sock.recvfrom(4096)
    except (socket.timeout, OSError) as exc:
        return ProbeOutcome("unreachable", f"DNS {query} via {resolver} unreachable: {exc}")

    # The response parser only reads the fields needed to classify success/failure.
    _, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", payload[:12])
    rcode = flags & 0x000F
    if rcode != 0:
        return ProbeOutcome("failed", f"DNS {query} via {resolver} failed with rcode {rcode}")

    offset = 12
    for _ in range(qdcount):
        _, offset = _decode_dns_name(payload, offset)
        offset += 4

    answers: list[str] = []
    for _ in range(ancount):
        _, offset = _decode_dns_name(payload, offset)
        answer_type, _, _, rdlength = struct.unpack("!HHIH", payload[offset : offset + 10])
        offset += 10
        rdata = payload[offset : offset + rdlength]
        offset += rdlength
        if answer_type == 1 and rdlength == 4:
            answers.append(socket.inet_ntoa(rdata))
        elif answer_type == 28 and rdlength == 16:
            answers.append(socket.inet_ntop(socket.AF_INET6, rdata))
        elif answer_type == 5:
            cname, _ = _decode_dns_name(payload, offset - rdlength)
            answers.append(cname)

    if expected_answers:
        if isinstance(expected_answers, list):
            expected_set = {str(item) for item in expected_answers}
        else:
            expected_set = {str(expected_answers)}
        if not expected_set.intersection(answers):
            return ProbeOutcome("failed", f"DNS {query} via {resolver} did not return expected answer")
    elif not answers:
        return ProbeOutcome("failed", f"DNS {query} via {resolver} returned no answers")

    return ProbeOutcome("passed", f"DNS {query} via {resolver} returned {', '.join(answers) if answers else 'an answer'}")


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
        except Exception as exc:  # pragma: no cover - defensive guard for online use
            outcome = ProbeOutcome("unreachable", f"{service['name']} probe raised {exc}")
        # Map probe outcomes onto the shared PVE result severities for reporting.
        severity = cast(Severity, {"passed": "PASS", "failed": "FAIL", "unreachable": "FAIL", "skipped": "SKIP"}[outcome.status])
        results.append(CheckResult(severity, check_id, f"{outcome.status}: {service['name']} - {outcome.message}"))
    return results
