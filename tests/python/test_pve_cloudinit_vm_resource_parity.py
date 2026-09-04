from __future__ import annotations

from collections.abc import Callable
from difflib import unified_diff
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "automation" / "opentofu" / "modules" / "pve-cloudinit-vm" / "main.tf"
RESOURCE_TYPE = "proxmox_virtual_environment_vm"
MARKERS = {
    "protected": ("# parity-guard: protected-begin", "# parity-guard: protected-end"),
    "unprotected": ("# parity-guard: unprotected-begin", "# parity-guard: unprotected-end"),
}
HEADERS = {
    branch: f'resource "{RESOURCE_TYPE}" "{branch}" {{'
    for branch in MARKERS
}
COUNTS = {
    "protected": "  count = local.vm_is_protected ? 1 : 0",
    "unprotected": "  count = local.vm_is_protected ? 0 : 1",
}


class ParityGuardError(AssertionError):
    pass


def _normalize_newlines(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))


def _validate_marker_layout(source: str) -> None:
    positions: list[int] = []
    for branch in ("protected", "unprotected"):
        for marker in MARKERS[branch]:
            count = source.count(marker)
            if count != 1:
                raise ParityGuardError(f"{marker} must appear exactly once, found {count}")
            positions.append(source.index(marker))
    if positions != sorted(positions):
        raise ParityGuardError("parity guard markers are not in protected/unprotected order")


def _resource_end(text: str, opening_brace: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    line_comment = False
    block_comment = False
    index = opening_brace

    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""

        if line_comment:
            if character == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if character == "*" and following == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
        elif character == "#":
            line_comment = True
        elif character == "/" and following == "/":
            line_comment = True
            index += 1
        elif character == "/" and following == "*":
            block_comment = True
            index += 1
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                break
        index += 1

    raise ParityGuardError("resource block is not balanced before its end marker")


def _extract_marked_resource(source: str, branch: str) -> str:
    begin_marker, end_marker = MARKERS[branch]
    start = source.index(begin_marker) + len(begin_marker)
    end = source.index(end_marker)
    section = source[start:end].lstrip("\r\n")
    header = HEADERS[branch]
    if not section.startswith(header):
        raise ParityGuardError(f"{branch} marker must be immediately followed by {header}")

    close = _resource_end(section, section.index("{"))
    if section[close + 1 :].strip():
        raise ParityGuardError(f"{branch} end marker must immediately follow the resource block")
    return section[: close + 1]


def _normalize_resource(resource: str, branch: str) -> str:
    resource = _normalize_newlines(resource)
    header = HEADERS[branch]
    count = COUNTS[branch]
    if resource.count(header) != 1 or not resource.startswith(header):
        raise ParityGuardError(f"expected exactly one {header}")
    if resource.count(count) != 1:
        raise ParityGuardError(f"{branch} resource must contain exactly one {count}")

    prevent_destroy_lines = re.findall(r"^\s*prevent_destroy\s*=.*$", resource, re.MULTILINE)
    if branch == "protected":
        if prevent_destroy_lines != ["    prevent_destroy = true"]:
            raise ParityGuardError("protected resource must contain exactly one literal prevent_destroy = true")
        resource = resource.replace("    prevent_destroy = true\n", "", 1)
    elif prevent_destroy_lines:
        raise ParityGuardError("unprotected resource must not declare prevent_destroy")

    resource = resource.replace(header, f'resource "{RESOURCE_TYPE}" "parity" {{', 1)
    resource = resource.replace(count, "  count = parity-count", 1)
    return _normalize_newlines(resource)


def assert_vm_resource_parity(source: str) -> None:
    _validate_marker_layout(source)
    protected = _normalize_resource(_extract_marked_resource(source, "protected"), "protected")
    unprotected = _normalize_resource(_extract_marked_resource(source, "unprotected"), "unprotected")
    if protected != unprotected:
        diff = "".join(
            unified_diff(
                unprotected.splitlines(keepends=True),
                protected.splitlines(keepends=True),
                fromfile="unprotected normalized resource",
                tofile="protected normalized resource",
            )
        )
        raise ParityGuardError(f"normalized protected/unprotected VM resources differ:\n{diff}")


def test_current_module_resources_are_in_parity() -> None:
    assert_vm_resource_parity(MODULE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            lambda source: source.replace(MARKERS["protected"][0], "", 1),
            "protected-begin must appear exactly once",
        ),
        (
            lambda source: f"{source}\n{MARKERS['protected'][0]}\n",
            "protected-begin must appear exactly once",
        ),
        (
            lambda source: source.replace(MARKERS["protected"][0], "temporary-marker", 1)
            .replace(MARKERS["unprotected"][0], MARKERS["protected"][0], 1)
            .replace("temporary-marker", MARKERS["unprotected"][0], 1),
            "markers are not in protected/unprotected order",
        ),
    ],
)
def test_marker_layout_fails_closed(source: Callable[[str], str], message: str) -> None:
    with pytest.raises(ParityGuardError, match=message):
        assert_vm_resource_parity(source(MODULE_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            lambda source: source.replace(HEADERS["protected"], HEADERS["protected"].replace('"protected"', '"other"'), 1),
            "protected marker must be immediately followed",
        ),
        (
            lambda source: source.replace(COUNTS["protected"], COUNTS["unprotected"], 1),
            "protected resource must contain exactly one",
        ),
        (
            lambda source: source.replace(COUNTS["unprotected"], COUNTS["protected"], 1),
            "unprotected resource must contain exactly one",
        ),
    ],
)
def test_resource_identity_and_selector_fail_closed(source: Callable[[str], str], message: str) -> None:
    with pytest.raises(ParityGuardError, match=message):
        assert_vm_resource_parity(source(MODULE_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            lambda source: source.replace("    prevent_destroy = true\n", "", 1),
            "protected resource must contain exactly one",
        ),
        (
            lambda source: source.replace(
                "    prevent_destroy = true\n", "    prevent_destroy = true\n    prevent_destroy = true\n", 1
            ),
            "protected resource must contain exactly one",
        ),
        (
            lambda source: source.replace(
                HEADERS["unprotected"],
                f"{HEADERS['unprotected']}\n  lifecycle {{\n    prevent_destroy = true\n  }}",
                1,
            ),
            "unprotected resource must not declare prevent_destroy",
        ),
    ],
)
def test_prevent_destroy_boundary_fails_closed(source: Callable[[str], str], message: str) -> None:
    with pytest.raises(ParityGuardError, match=message):
        assert_vm_resource_parity(source(MODULE_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("  stop_on_destroy = true", "  stop_on_destroy = false"),
        ("      initialization[0].network_data_file_id,", "      initialization[0].network_data_file_id # drift,"),
        ("Passthrough VMs require q35, ovmf, cpu_type host, and HA disabled.", "drifted precondition"),
    ],
)
def test_unrelated_one_sided_drift_fails_with_normalized_diff(old: str, new: str) -> None:
    source = MODULE_PATH.read_text(encoding="utf-8").replace(old, new, 1)
    with pytest.raises(ParityGuardError, match="normalized protected/unprotected VM resources differ") as excinfo:
        assert_vm_resource_parity(source)
    assert "--- unprotected normalized resource" in str(excinfo.value)
