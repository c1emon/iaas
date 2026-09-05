"""Offline K3s intent validation and review rendering."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iaas_automation.common.cli import run_validation_cli
from iaas_automation.common.io import load_yaml, write_text

from .config import build_composed_model, render_review


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse explicit K3s intent and inventory inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", type=Path, required=True, help="Path to K3s intent YAML")
    parser.add_argument("--inventory", type=Path, required=True, help="Path to generated PVE Ansible inventory")
    parser.add_argument("--render", type=Path, help="Write the deterministic review model to this path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate the composed model and optionally render its review form."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    model = build_composed_model(load_yaml(args.intent), load_yaml(args.inventory))
    if args.render is not None:
        write_text(args.render, render_review(model))
        print(f"K3s review rendered: {args.render}")
    else:
        print("K3s intent validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))
