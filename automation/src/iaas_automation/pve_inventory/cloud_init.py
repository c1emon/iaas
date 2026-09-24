"""Render, upload, and verify runtime cloud-init user-data snippets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iaas_automation.common.errors import ValidationError, require

from .cloud_init_helpers.artifacts import load_rendered_artifacts, write_rendered_artifacts
from .cloud_init_helpers.render import render_snippets
from .cloud_init_helpers.ssh import upload_snippets, verify_snippets


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="Render local cloud-init snippets")
    render.add_argument("--tfvars", type=Path, required=True, help="Path to generated OpenTofu variables")
    render.add_argument("--output-dir", type=Path, required=True, help="Directory for rendered snippets")
    render.add_argument("--storage-id", required=True, help="PVE snippets storage id")

    upload = subparsers.add_parser("upload", help="Upload cloud-init snippets from the existing manifest")
    upload.add_argument("--tfvars", type=Path, required=True, help="Path to generated OpenTofu variables")
    upload.add_argument("--output-dir", type=Path, required=True, help="Directory for rendered snippets")
    upload.add_argument("--storage-id", required=True, help="PVE snippets storage id")
    upload.add_argument("--pve-host", required=True, help="Target PVE node hostname or alias")
    upload.add_argument("--ssh-user", required=True, help="SSH user for snippet upload")
    upload.add_argument("--ssh-timeout", type=float, default=None, help="SSH timeout in seconds (default: 30 or IAAS_PVE_SSH_TIMEOUT_SECONDS)")
    upload.add_argument("--ssh-config", type=Path)
    upload.add_argument("--ssh-port", type=int, default=22)
    upload.add_argument("--execution-context", type=Path)

    verify = subparsers.add_parser("verify", help="Verify cloud-init snippets from the existing manifest")
    verify.add_argument("--tfvars", type=Path, required=True, help="Path to generated OpenTofu variables")
    verify.add_argument("--output-dir", type=Path, required=True, help="Directory for rendered snippets")
    verify.add_argument("--storage-id", required=True, help="PVE snippets storage id")
    verify.add_argument("--pve-host", required=True, help="Target PVE node hostname or alias")
    verify.add_argument("--ssh-user", required=True, help="SSH user for snippet verification")
    verify.add_argument("--ssh-timeout", type=float, default=None, help="SSH timeout in seconds (default: 30 or IAAS_PVE_SSH_TIMEOUT_SECONDS)")
    verify.add_argument("--ssh-config", type=Path)
    verify.add_argument("--ssh-port", type=int, default=22)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "render":
        snippets = render_snippets(args.tfvars, args.storage_id)
        write_rendered_artifacts(snippets, args.tfvars, args.storage_id, args.output_dir)
        print(f"rendered {len(snippets)} cloud-init snippets to {args.output_dir}")
    elif args.command == "upload":
        # Upload is an internal phase of admitted saved-plan execution. The
        # legacy standalone write interface no longer accepts bare arguments.
        import json
        from iaas_automation.runtime_execution.credentials import protected_file
        require(args.execution_context is not None, "standalone upload retired; use PVE plan/apply")
        protected_file(args.execution_context)
        context = json.loads(args.execution_context.read_text())
        from iaas_automation.runtime_execution.pve_contracts import validate_execution_admission
        validate_execution_admission(context["execution_admission"], digest=context["plan_sha256"],
                                     target=context["target"], execution_id=context["execution_id"])
        require(context["target"]["ssh_host"] == args.pve_host
                and context["target"]["ssh_user"] == args.ssh_user
                and context["target"]["storage_id"] == args.storage_id,
                "snippet execution target mismatch")
        snippets = load_rendered_artifacts(args.output_dir, args.storage_id, args.tfvars)
        upload_snippets(snippets, args)
        print(f"uploaded {len(snippets)} cloud-init snippets to {args.pve_host}")
    elif args.command == "verify":
        snippets = load_rendered_artifacts(args.output_dir, args.storage_id, args.tfvars)
        verify_snippets(snippets, args)
        print(f"verified {len(snippets)} cloud-init snippets on {args.pve_host}")
    return 0


def _run() -> int:
    try:
        return main()
    except ValidationError as exc:
        print(f"FAIL cloud-init: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_run())
