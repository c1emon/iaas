"""Run one read-only current-state inspection for a reviewed OPNsense candidate.

Example::

    PYTHONPATH=src uv run python -m iaas.opnsense_workflow.inspect \
        --inventory inventory.yml --candidate candidate.json --output current.json

The report is evidence about the selected current state.  It does not save,
activate, or prove action completion or business acceptance.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

from iaas.common.errors import ValidationError, require
from iaas.common.io import load_yaml

from .contracts import load_candidate
from .reader import Reader
from .runtime import target_from_inventory


_CREDENTIAL_NAMES = ("OPNSENSE_API_KEY", "OPNSENSE_API_SECRET")
_SUCCESS_STATUSES = {"verified", "not_applicable"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True, help="Path to the static OPNsense inventory")
    parser.add_argument("--candidate", type=Path, required=True, help="Path to a reviewed OPNsense candidate")
    parser.add_argument("--output", type=Path, required=True, help="New private JSON report path")
    return parser.parse_args(argv)


def _credentials(environment: dict[str, str] | None = None) -> dict[str, str]:
    source: Mapping[str, str] = os.environ if environment is None else environment
    return {name: value for name in _CREDENTIAL_NAMES
            if isinstance(value := source.get(name), str) and value}


def _report_status(statuses: list[Any]) -> tuple[str, int]:
    if all(status in _SUCCESS_STATUSES for status in statuses):
        return "matched", 0
    if any(status == "failed" for status in statuses):
        return "failed", 1
    return "unknown", 2


def _write_new_private_json(path: Path, report: dict[str, Any]) -> None:
    """Create a private report without replacing an existing path."""
    new_parents: list[Path] = []
    parent = path.parent
    while not parent.exists():
        new_parents.append(parent)
        if parent.parent == parent:
            break
        parent = parent.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    for new_parent in reversed(new_parents):
        new_parent.chmod(0o700)
    data = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValidationError("inspection output already exists") from error
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        path.chmod(0o600)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def inspect_candidate(
    inventory_path: Path,
    candidate_path: Path,
    output_path: Path,
    *,
    reader_factory: Callable[[dict[str, Any], dict[str, str]], Any] = Reader,
    environment: dict[str, str] | None = None,
) -> tuple[dict[str, Any], int]:
    """Inspect every selected candidate object through one read-only Reader."""
    if output_path.exists():
        raise ValidationError("inspection output already exists")
    candidate, candidate_digest = load_candidate(candidate_path)
    inventory = load_yaml(inventory_path)
    candidate_target = candidate.get("target")
    if not isinstance(candidate_target, dict):
        raise ValidationError("candidate target is missing")
    scope = candidate_target.get("host")
    if not isinstance(scope, str) or not scope:
        raise ValidationError("candidate target host is missing")
    target = target_from_inventory(inventory, scope)
    require(target == candidate_target, "candidate target does not match inventory")

    reader = reader_factory(target, _credentials(environment))
    objects: list[dict[str, Any]] = []
    try:
        for selected in candidate["selected"]:
            resource = selected["resource"]
            identity = selected["identity"]
            try:
                observation = reader.active_check(resource, identity, selected["desired"])
            except Exception:
                observation = {"status": "unknown", "reason": "active_observation_unavailable"}
            if not isinstance(observation, dict):
                observation = {"status": "unknown", "reason": "malformed_active_observation"}
            objects.append({"resource": resource, "identity": identity, "observation": observation})
    finally:
        close = getattr(reader, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    for item in objects:
        observation = item["observation"]
        if not isinstance(observation.get("status"), str):
            item["observation"] = {
                **observation,
                "status": "unknown",
                "reason": "malformed_active_observation_status",
            }

    statuses = [item["observation"].get("status") for item in objects]
    status, exit_code = _report_status(statuses)
    report = {
        "kind": "opnsense-current-state-inspection",
        "scope": "advanced_current_state",
        "read_only": True,
        "action_proof": "not_proven",
        "business_proof": "not_proven",
        "status": status,
        "exit_code": exit_code,
        "target": target,
        "candidate_sha256": candidate_digest,
        "objects": objects,
    }
    _write_new_private_json(output_path, report)
    return report, exit_code


def main(
    argv: list[str] | None = None,
    *,
    reader_factory: Callable[[dict[str, Any], dict[str, str]], Any] = Reader,
    environment: dict[str, str] | None = None,
) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report, exit_code = inspect_candidate(args.inventory, args.candidate, args.output,
                                              reader_factory=reader_factory, environment=environment)
        print(json.dumps({"status": report["status"], "output": str(args.output)}))
        return exit_code
    except (OSError, TypeError, ValueError, ValidationError):
        print("opnsense inspection failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["inspect_candidate", "main", "parse_args"]
