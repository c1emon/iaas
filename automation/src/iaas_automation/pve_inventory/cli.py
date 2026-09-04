"""Command-line orchestration for PVE inventory validation and generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iaas_automation.common.cli import run_validation_cli
from iaas_automation.common.errors import ValidationError
from iaas_automation.common.io import check_outputs, load_yaml, write_text

from .inventory.model import build_model
from .inventory.validation.cluster import validate_cluster
from .inventory.validation.vm import validate_vms
from .inventory.render import render_outputs


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line flags for validation/generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", type=Path, required=True, help="Path to the PVE cluster inventory")
    parser.add_argument("--vms", type=Path, required=True, help="Path to the VM inventory")
    parser.add_argument("--tfvars", type=Path, help="Generated OpenTofu variables output")
    parser.add_argument("--ansible", type=Path, help="Generated Ansible inventory output")
    parser.add_argument("--docs", type=Path, help="Generated PVE documentation output")
    parser.add_argument("--template-build-env", type=Path, help="Generated Packer environment output")
    parser.add_argument("--generate", action="store_true", help="Generate committed outputs")
    parser.add_argument("--check", action="store_true", help="Fail if committed outputs are stale")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run validation, generation, or stale-output checks."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.generate and args.check:
        raise ValidationError("--generate and --check are mutually exclusive")
    optional_output_paths = {
        "tfvars": args.tfvars,
        "ansible": args.ansible,
        "docs": args.docs,
        "template_build_env": args.template_build_env,
    }
    if (args.generate or args.check) and any(path is None for path in optional_output_paths.values()):
        raise ValidationError("--tfvars, --ansible, --docs, and --template-build-env are required with --generate or --check")

    cluster_doc = load_yaml(args.cluster)
    cluster_state = validate_cluster(cluster_doc)
    vms_doc = load_yaml(args.vms)
    vms = validate_vms(vms_doc, cluster_state)
    model = build_model(cluster_state, vms)
    outputs = render_outputs(model)

    if args.generate:
        output_paths = {name: path for name, path in optional_output_paths.items() if path is not None}
        for name, path in output_paths.items():
            write_text(path, outputs[name])
        print("PVE inventory outputs generated")
        return 0

    if args.check:
        output_paths = {name: path for name, path in optional_output_paths.items() if path is not None}
        mismatches = check_outputs(outputs, output_paths)
        if mismatches:
            raise ValidationError("; ".join(mismatches))
        print("PVE inventory outputs are up to date")
        return 0

    print("PVE inventory validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))
