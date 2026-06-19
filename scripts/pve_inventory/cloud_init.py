"""Render and upload runtime cloud-init user-data snippets for Section 4A."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError, require
from .io import load_json, write_text
from .paths import DEFAULT_TFVARS, DEFAULT_USER_DATA_DIR
from .secrets import hash_cloud_init_password


REQUIRED_ENV_VARS = (
    "PVE_VM_CLEMON_PASSWORD",
    "PVE_VM_CLEMON_PUBLIC_KEY",
    "PVE_VM_OPS_PASSWORD",
    "PVE_VM_OPS_PUBLIC_KEY",
)


@dataclass(frozen=True)
class CloudInitSnippet:
    vmid: int
    name: str
    file_name: str
    file_id: str
    content: str


def snippet_storage_path(storage_id: str, file_name: str) -> str:
    return f"{storage_id}:snippets/{file_name}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="Render local cloud-init snippets")
    render.add_argument("--tfvars", type=Path, default=DEFAULT_TFVARS, help="Path to generated.auto.tfvars.json")
    render.add_argument("--output-dir", type=Path, default=DEFAULT_USER_DATA_DIR, help="Directory for rendered snippets")
    render.add_argument("--storage-id", default="images", help="PVE snippets storage id")

    upload = subparsers.add_parser("upload", help="Render and upload cloud-init snippets")
    upload.add_argument("--tfvars", type=Path, default=DEFAULT_TFVARS, help="Path to generated.auto.tfvars.json")
    upload.add_argument("--output-dir", type=Path, default=DEFAULT_USER_DATA_DIR, help="Directory for rendered snippets")
    upload.add_argument("--storage-id", default="images", help="PVE snippets storage id")
    upload.add_argument("--pve-host", required=True, help="Target PVE node hostname or alias")
    upload.add_argument("--ssh-user", default="pve-ops", help="SSH user for snippet upload")

    verify = subparsers.add_parser("verify", help="Render and verify cloud-init snippets")
    verify.add_argument("--tfvars", type=Path, default=DEFAULT_TFVARS, help="Path to generated.auto.tfvars.json")
    verify.add_argument("--output-dir", type=Path, default=DEFAULT_USER_DATA_DIR, help="Directory for rendered snippets")
    verify.add_argument("--storage-id", default="images", help="PVE snippets storage id")
    verify.add_argument("--pve-host", required=True, help="Target PVE node hostname or alias")
    verify.add_argument("--ssh-user", default="pve-ops", help="SSH user for snippet verification")

    return parser.parse_args(argv)


def read_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    require(bool(value), f"missing required environment variable: {name}")
    return value


def load_generated_tfvars(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    require(isinstance(payload, dict), f"{path}: expected a JSON object")
    return payload


def build_user_data(vm: dict[str, Any], env: dict[str, str]) -> str:
    data = {
        "hostname": vm["name"],
        "preserve_hostname": False,
        "disable_root": True,
        "ssh_pwauth": False,
        "package_update": False,
        "package_upgrade": False,
        "users": [
            {
                "name": "clemon",
                "gecos": "clemon",
                "groups": "sudo",
                "shell": "/bin/bash",
                "sudo": ["ALL=(ALL) ALL"],
                "lock_passwd": False,
                "passwd": hash_cloud_init_password(env["PVE_VM_CLEMON_PASSWORD"]),
                "ssh_authorized_keys": [env["PVE_VM_CLEMON_PUBLIC_KEY"]],
            },
            {
                "name": "ops",
                "gecos": "ops",
                "groups": "sudo",
                "shell": "/bin/bash",
                "sudo": ["ALL=(ALL) ALL"],
                "lock_passwd": False,
                "passwd": hash_cloud_init_password(env["PVE_VM_OPS_PASSWORD"]),
                "ssh_authorized_keys": [env["PVE_VM_OPS_PUBLIC_KEY"]],
            },
        ],
    }
    return "#cloud-config\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def render_snippets(tfvars_path: Path, storage_id: str) -> list[CloudInitSnippet]:
    payload = load_generated_tfvars(tfvars_path)
    vms = payload.get("vms", [])
    require(isinstance(vms, list), f"{tfvars_path}: vms must be a list")

    env = {name: read_required_env(name) for name in REQUIRED_ENV_VARS}
    snippets: list[CloudInitSnippet] = []
    for vm in vms:
        require(isinstance(vm, dict), f"{tfvars_path}: vms entries must be objects")
        if vm.get("passthrough") is not None:
            continue
        vmid = vm.get("vmid")
        name = vm.get("name")
        require(isinstance(vmid, int), f"{tfvars_path}: vmid must be an integer")
        require(isinstance(name, str) and name, f"{tfvars_path}: name must be a non-empty string")
        file_name = f"opentofu-vm-{vmid}-user-data.yml"
        snippets.append(
            CloudInitSnippet(
                vmid=vmid,
                name=name,
                file_name=file_name,
                file_id=snippet_storage_path(storage_id, file_name),
                content=build_user_data(vm, env),
            )
        )
    snippets.sort(key=lambda item: (item.vmid, item.name))
    return snippets


def write_snippets(snippets: list[CloudInitSnippet], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for snippet in snippets:
        write_text(output_dir / snippet.file_name, snippet.content, secure=True)


def upload_snippets(snippets: list[CloudInitSnippet], args: argparse.Namespace) -> None:
    remote = f"{args.ssh_user}@{args.pve_host}"
    for snippet in snippets:
        try:
            subprocess.run(
                [
                    "ssh",
                    remote,
                    "sudo",
                    "-n",
                    "/usr/local/sbin/astra-pve-snippet-upload",
                    "--storage",
                    args.storage_id,
                    "--filename",
                    snippet.file_name,
                ],
                input=snippet.content,
                text=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise ValidationError("ssh is required for snippet upload") from exc


def verify_snippets(snippets: list[CloudInitSnippet], args: argparse.Namespace) -> None:
    remote = f"{args.ssh_user}@{args.pve_host}"
    for snippet in snippets:
        try:
            subprocess.run(
                [
                    "ssh",
                    remote,
                    "sudo",
                    "-n",
                    "/usr/local/sbin/astra-pve-snippet-upload",
                    "--storage",
                    args.storage_id,
                    "--filename",
                    snippet.file_name,
                    "--verify",
                ],
                check=True,
            )
        except FileNotFoundError as exc:
            raise ValidationError("ssh is required for snippet verification") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    snippets = render_snippets(args.tfvars, args.storage_id)
    write_snippets(snippets, args.output_dir)

    if args.command == "upload":
        upload_snippets(snippets, args)
        print(f"uploaded {len(snippets)} cloud-init snippets to {args.pve_host}")
    elif args.command == "verify":
        verify_snippets(snippets, args)
        print(f"verified {len(snippets)} cloud-init snippets on {args.pve_host}")
    else:
        print(f"rendered {len(snippets)} cloud-init snippets to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
