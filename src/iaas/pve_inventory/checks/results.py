"""Result objects and stable human reporting for PVE preflight.

The preflight returns pass/warn/fail/skip records so callers can keep the
exit code policy separate from the operator-facing text output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Severity = Literal["PASS", "WARN", "FAIL", "SKIP"]


@dataclass(frozen=True)
class CheckResult:
    """One immutable preflight outcome."""
    severity: Severity
    check_id: str
    message: str


def has_failures(results: list[CheckResult]) -> bool:
    """Return True when any blocking failure was recorded."""
    return any(result.severity == "FAIL" for result in results)


def render_report(results: list[CheckResult]) -> str:
    """Render a compact operator summary without exposing secrets."""
    counts = {severity: 0 for severity in ("PASS", "WARN", "FAIL", "SKIP")}
    lines: list[str] = []
    for result in results:
        counts[result.severity] += 1
        lines.append(f"{result.severity:<4} {result.check_id}: {result.message}")
    lines.append(f"summary: {counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail, {counts['SKIP']} skip")
    return "\n".join(lines) + "\n"
