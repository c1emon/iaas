"""Validate a non-secret external-platform handoff without host access."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import load_yaml, write_text
from iaas_automation.k3s_automation.config import build_composed_model

from .config import attach_ca_fingerprint, build_handoff, render_bundle


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--handoff-intent", type=Path, required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--render", type=Path, help="Explicit protected operator output path")
    parser.add_argument("--ca-fingerprint", help="Authoritative CA fingerprint supplied only by the read-only workflow")
    return parser.parse_args(argv)


def _safe_output(path: Path) -> None:
    root = Path.cwd().resolve()
    resolved = path.resolve()
    require(resolved != root and root not in resolved.parents, "handoff output: repository-owned paths are not allowed")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    model = build_composed_model(load_yaml(args.intent), load_yaml(args.inventory))
    handoff = build_handoff(load_yaml(args.handoff_intent), model, args.scope)
    if args.render is None:
        print(f"Platform handoff composition passed: {handoff['cluster']['name']} ({handoff['cluster']['api_endpoint']})")
        return 0
    require(args.ca_fingerprint is not None, "--render requires an authoritative --ca-fingerprint from the read-only handoff workflow")
    _safe_output(args.render)
    bundle = attach_ca_fingerprint(handoff, args.ca_fingerprint)
    write_text(args.render, render_bundle(bundle), secure=True)
    print(f"Platform handoff bundle rendered: {args.render} ({bundle['cluster']['name']})")
    return 0
