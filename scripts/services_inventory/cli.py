"""Command-line orchestration for service metadata validation and generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.common.cli import run_validation_cli
from scripts.common.errors import ValidationError
from scripts.common.io import load_yaml, write_text

from .model import build_model
from .paths import DEFAULT_DOCS, DEFAULT_SERVICES, DEFAULT_VMS
from .render import build_markdown
from .validation import load_vm_names, validate_services


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line flags for validation/generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--services", type=Path, default=DEFAULT_SERVICES, help="Path to inventory/services.yml")
    parser.add_argument("--vms", type=Path, default=DEFAULT_VMS, help="Path to inventory/vms.yml")
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS, help="Path to docs/generated/services.md")
    parser.add_argument("--generate", action="store_true", help="Generate committed outputs")
    parser.add_argument("--check", action="store_true", help="Fail if committed outputs are stale")
    return parser.parse_args(argv)


def _check_output(path: Path, expected_text: str) -> str | None:
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        return f"missing: {path}"
    if existing != expected_text:
        return f"stale: {path}"
    return None


def main(argv: list[str] | None = None) -> int:
    """Run validation, generation, or stale-output checks."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.generate and args.check:
        raise ValidationError("--generate and --check are mutually exclusive")

    services_doc = load_yaml(args.services)
    vm_names = load_vm_names(load_yaml(args.vms))
    services, warnings = validate_services(services_doc, vm_names)
    model = build_model(services, warnings)
    docs = build_markdown(model)

    if args.generate:
        write_text(args.docs, docs)
        print("Service metadata documentation generated")
        return 0

    if args.check:
        mismatch = _check_output(args.docs, docs)
        if mismatch:
            raise ValidationError(mismatch)
        print("Service metadata documentation is up to date")
        return 0

    print("Service metadata validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))
