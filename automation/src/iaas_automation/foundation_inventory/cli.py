"""Command-line orchestration for foundation recovery validation and generation.

The CLI keeps offline checks, committed-doc generation, and explicit online
health probing as separate modes so read-only validation stays safe by default.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iaas_automation.common.cli import run_validation_cli
from iaas_automation.common.errors import ValidationError
from iaas_automation.common.io import load_yaml, write_text
from iaas_automation.pve_inventory.checks.results import has_failures, render_report

from .health import run_health_checks
from .model import build_model
from .render import build_markdown
from .validation import validate_foundation_inventory


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True, help="Path to foundation inventory")
    parser.add_argument("--docs", type=Path, help="Generated foundation recovery documentation output")
    parser.add_argument("--generate", action="store_true", help="Generate committed outputs")
    parser.add_argument("--check", action="store_true", help="Fail if committed outputs are stale")
    parser.add_argument("--health", action="store_true", help="Run explicit online read-only health checks")
    return parser.parse_args(argv)


def _check_output(path: Path, expected_text: str) -> str | None:
    """Return a stale/missing marker instead of raising for doc freshness checks."""
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        return f"missing: {path}"
    if existing != expected_text:
        return f"stale: {path}"
    return None


def main(argv: list[str] | None = None) -> int:
    """Run offline validation, generation, staleness checks, or live health probes."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    flags = [args.generate, args.check, args.health]
    if sum(bool(flag) for flag in flags) > 1:
        raise ValidationError("--generate, --check, and --health are mutually exclusive")
    if (args.generate or args.check) and args.docs is None:
        raise ValidationError("--docs is required with --generate or --check")

    inventory_doc = load_yaml(args.inventory)
    inventory = validate_foundation_inventory(inventory_doc)
    model = build_model(inventory)
    docs = build_markdown(model)

    if args.generate:
        assert args.docs is not None
        write_text(args.docs, docs)
        print("Foundation recovery documentation generated")
        return 0

    if args.check:
        assert args.docs is not None
        mismatch = _check_output(args.docs, docs)
        if mismatch:
            raise ValidationError(mismatch)
        print("Foundation recovery documentation is up to date")
        return 0

    if args.health:
        results = run_health_checks(model)
        print(render_report(results), end="")
        return 1 if has_failures(results) else 0

    print("Foundation recovery validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))
