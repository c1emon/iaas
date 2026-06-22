"""Command-line orchestration for PVE inventory validation and generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import ValidationError
from .io import check_outputs, load_yaml, write_text
from .model import build_model
from .paths import DEFAULT_ANSIBLE, DEFAULT_CLUSTER, DEFAULT_DOCS, DEFAULT_TEMPLATE_BUILD_ENV, DEFAULT_TFVARS, DEFAULT_VMS
from .render import render_outputs
from .validation import validate_cluster, validate_vms


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line flags for validation/generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", type=Path, default=DEFAULT_CLUSTER, help="Path to inventory/pve-cluster.yml")
    parser.add_argument("--vms", type=Path, default=DEFAULT_VMS, help="Path to inventory/vms.yml")
    parser.add_argument("--generate", action="store_true", help="Generate committed outputs")
    parser.add_argument("--check", action="store_true", help="Fail if committed outputs are stale")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run validation, generation, or stale-output checks."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.generate and args.check:
        raise ValidationError("--generate and --check are mutually exclusive")

    cluster_doc = load_yaml(args.cluster)
    cluster_state = validate_cluster(cluster_doc)
    vms_doc = load_yaml(args.vms)
    vms = validate_vms(vms_doc, cluster_state)
    model = build_model(cluster_state, vms)
    outputs = render_outputs(model)

    if args.generate:
        write_text(DEFAULT_TFVARS, outputs["tfvars"])
        write_text(DEFAULT_ANSIBLE, outputs["ansible"])
        write_text(DEFAULT_DOCS, outputs["docs"])
        write_text(DEFAULT_TEMPLATE_BUILD_ENV, outputs["template_build_env"])
        print("PVE inventory outputs generated")
        return 0

    if args.check:
        mismatches = check_outputs(outputs, {"tfvars": DEFAULT_TFVARS, "ansible": DEFAULT_ANSIBLE, "docs": DEFAULT_DOCS, "template_build_env": DEFAULT_TEMPLATE_BUILD_ENV})
        if mismatches:
            raise ValidationError("; ".join(mismatches))
        print("PVE inventory outputs are up to date")
        return 0

    print("PVE inventory validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
