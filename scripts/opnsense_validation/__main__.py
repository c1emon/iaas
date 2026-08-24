from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.common.cli import run_validation_cli

from . import RESOURCE_PATHS, validate_all, validate_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate repository-owned OPNsense desired state")
    parser.add_argument("--resource", choices=sorted(RESOURCE_PATHS))
    parser.add_argument("--file", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if bool(args.resource) != bool(args.file):
        parser.error("--resource and --file must be supplied together")
    if args.resource:
        validate_file(args.resource, args.file)
    else:
        validate_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))
