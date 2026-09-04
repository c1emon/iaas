from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iaas_automation.common.cli import run_validation_cli

from . import RESOURCE_FILES, validate_all, validate_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate repository-owned OPNsense desired state")
    parser.add_argument("--resource", choices=sorted(RESOURCE_FILES))
    parser.add_argument("--file", type=Path)
    parser.add_argument("--vars-dir", type=Path, help="Directory containing OPNsense desired-state YAML files")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.vars_dir is not None and (args.resource or args.file):
        parser.error("--vars-dir cannot be combined with --resource or --file")
    if args.vars_dir is None and bool(args.resource) != bool(args.file):
        parser.error("supply --vars-dir or both --resource and --file")
    if args.resource:
        validate_file(args.resource, args.file)
    else:
        assert args.vars_dir is not None
        validate_all(args.vars_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))
