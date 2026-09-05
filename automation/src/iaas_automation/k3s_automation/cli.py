"""Offline K3s intent validation and review rendering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from iaas_automation.common.cli import run_validation_cli
from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import load_yaml, write_text

from .config import build_composed_model, render_review
from .operations import validate_deployment_scope, validate_exact_scope, validate_upgrade
from .secrets import load_protected_environment_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse explicit K3s intent and inventory inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", type=Path, required=True, help="Path to K3s intent YAML")
    parser.add_argument("--inventory", type=Path, required=True, help="Path to generated PVE Ansible inventory")
    parser.add_argument(
        "--scope",
        help="Explicit comma-separated declared node references; required by online command wrappers",
    )
    parser.add_argument(
        "--whole-cluster-scope",
        action="store_true",
        help="Require --scope to name every declared K3s node exactly once",
    )
    parser.add_argument(
        "--runtime-secrets",
        type=Path,
        help="Protected external-reference JSON; the path is checked without rendering values",
    )
    parser.add_argument("--render", type=Path, help="Write the deterministic review model to this path")
    parser.add_argument("--upgrade-target", help="Exact target K3s version for an offline upgrade plan")
    parser.add_argument("--observed-versions", type=Path, help="JSON mapping of explicit node refs to observed versions")
    parser.add_argument("--render-upgrade-plan", type=Path, help="Write the validated non-secret upgrade plan JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate the composed model and optionally render its review form."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    model = build_composed_model(load_yaml(args.intent), load_yaml(args.inventory))
    if args.scope is not None:
        if args.whole_cluster_scope:
            validate_deployment_scope(model, args.scope)
        else:
            validate_exact_scope(model, args.scope)
    elif args.whole_cluster_scope:
        require(False, "--whole-cluster-scope requires --scope")
    if args.runtime_secrets is not None:
        load_protected_environment_json(args.runtime_secrets)
    upgrade_arguments = (args.upgrade_target, args.observed_versions, args.render_upgrade_plan)
    if any(argument is not None for argument in upgrade_arguments):
        if not all(argument is not None for argument in upgrade_arguments):
            raise ValidationError(
                "upgrade planning requires --upgrade-target, --observed-versions, and --render-upgrade-plan"
            )
        if args.scope is None:
            raise ValidationError("upgrade planning requires --scope")
        try:
            observed_versions = json.loads(args.observed_versions.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ValidationError("observed versions must be a readable JSON object") from None
        if not isinstance(observed_versions, dict):
            raise ValidationError("observed versions must be a JSON object")
        plan = validate_upgrade(model, args.scope, observed_versions, args.upgrade_target)
        write_text(
            args.render_upgrade_plan,
            json.dumps(
                {
                    "scope": list(plan.scope),
                    "target_version": plan.target_version,
                    "skipped": list(plan.skipped),
                    "to_upgrade": list(plan.to_upgrade),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    if args.render is not None:
        write_text(args.render, render_review(model))
        print(f"K3s review rendered: {args.render}")
    else:
        print("K3s intent validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))
