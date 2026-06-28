"""Render and upload runtime cloud-init user-data snippets for Section 4A."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from scripts.common.errors import ValidationError, require
from scripts.common.io import load_json, write_text

from .paths import DEFAULT_TFVARS, DEFAULT_USER_DATA_DIR
from .secrets import hash_cloud_init_password


MANIFEST_FILE_NAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = 1
DEFAULT_SSH_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class CloudInitSnippet:
    vmid: int
    name: str
    file_name: str
    file_id: str
    content: str
    byte_count: int = 0
    sha256: str = ""


def snippet_storage_path(storage_id: str, file_name: str) -> str:
    return f"{storage_id}:snippets/{file_name}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="Render local cloud-init snippets")
    render.add_argument("--tfvars", type=Path, default=DEFAULT_TFVARS, help="Path to generated.auto.tfvars.json")
    render.add_argument("--output-dir", type=Path, default=DEFAULT_USER_DATA_DIR, help="Directory for rendered snippets")
    render.add_argument("--storage-id", required=True, help="PVE snippets storage id")

    upload = subparsers.add_parser("upload", help="Upload cloud-init snippets from the existing manifest")
    upload.add_argument("--tfvars", type=Path, default=DEFAULT_TFVARS, help="Path to generated.auto.tfvars.json")
    upload.add_argument("--output-dir", type=Path, default=DEFAULT_USER_DATA_DIR, help="Directory for rendered snippets")
    upload.add_argument("--storage-id", required=True, help="PVE snippets storage id")
    upload.add_argument("--pve-host", required=True, help="Target PVE node hostname or alias")
    upload.add_argument("--ssh-user", required=True, help="SSH user for snippet upload")
    upload.add_argument("--ssh-timeout", type=float, default=None, help="SSH timeout in seconds (default: 30 or ASTRA_PVE_SSH_TIMEOUT_SECONDS)")

    verify = subparsers.add_parser("verify", help="Verify cloud-init snippets from the existing manifest")
    verify.add_argument("--tfvars", type=Path, default=DEFAULT_TFVARS, help="Path to generated.auto.tfvars.json")
    verify.add_argument("--output-dir", type=Path, default=DEFAULT_USER_DATA_DIR, help="Directory for rendered snippets")
    verify.add_argument("--storage-id", required=True, help="PVE snippets storage id")
    verify.add_argument("--pve-host", required=True, help="Target PVE node hostname or alias")
    verify.add_argument("--ssh-user", required=True, help="SSH user for snippet verification")
    verify.add_argument("--ssh-timeout", type=float, default=None, help="SSH timeout in seconds (default: 30 or ASTRA_PVE_SSH_TIMEOUT_SECONDS)")

    return parser.parse_args(argv)


def read_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    require(bool(value), f"missing required environment variable: {name}")
    return value


def load_generated_tfvars(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    require(isinstance(payload, dict), f"{path}: expected a JSON object")
    return payload


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_path(output_dir: Path) -> Path:
    return output_dir / MANIFEST_FILE_NAME


def resolve_ssh_timeout(arg_timeout: float | None) -> float:
    if arg_timeout is not None:
        require(arg_timeout > 0, "--ssh-timeout must be greater than zero")
        return arg_timeout
    env_timeout = os.environ.get("ASTRA_PVE_SSH_TIMEOUT_SECONDS", "").strip()
    if not env_timeout:
        return DEFAULT_SSH_TIMEOUT_SECONDS
    try:
        timeout = float(env_timeout)
    except ValueError as exc:
        raise ValidationError("ASTRA_PVE_SSH_TIMEOUT_SECONDS must be a number") from exc
    require(timeout > 0, "ASTRA_PVE_SSH_TIMEOUT_SECONDS must be greater than zero")
    return timeout


def load_automation_cloud_init(payload: dict[str, Any], tfvars_path: Path) -> tuple[dict[str, Any], str, str, dict[str, Any], list[dict[str, Any]]]:
    cluster = payload.get("cluster")
    require(isinstance(cluster, dict), f"{tfvars_path}: cluster must be a mapping")
    cluster_map = cast(dict[str, Any], cluster)
    automation = cluster_map.get("automation")
    require(isinstance(automation, dict), f"{tfvars_path}: cluster.automation must be a mapping")
    automation_map = cast(dict[str, Any], automation)
    cloud_init = automation_map.get("cloud_init")
    require(isinstance(cloud_init, dict), f"{tfvars_path}: cluster.automation.cloud_init must be a mapping")
    cloud_init_map = cast(dict[str, Any], cloud_init)

    defaults = cloud_init_map.get("defaults")
    default_values = {
        "package_update": False,
        "package_upgrade": False,
        "ssh_pwauth": False,
        "disable_root": True,
    }
    if defaults is not None:
        require(isinstance(defaults, dict), f"{tfvars_path}: cluster.automation.cloud_init.defaults must be a mapping")
        defaults_map = cast(dict[str, Any], defaults)
        for key in default_values:
            value = defaults_map.get(key)
            if value is not None:
                require(isinstance(value, bool), f"{tfvars_path}: cluster.automation.cloud_init.defaults.{key} must be a boolean")
                default_values[key] = cast(bool, value)

    snippet_storage_role = cloud_init_map.get("snippet_storage_role")
    require(isinstance(snippet_storage_role, str) and snippet_storage_role, f"{tfvars_path}: cluster.automation.cloud_init.snippet_storage_role must be a non-empty string")
    snippet_storage_role_str = cast(str, snippet_storage_role)
    snippet_file_prefix = cloud_init_map.get("snippet_file_prefix")
    require(isinstance(snippet_file_prefix, str) and snippet_file_prefix, f"{tfvars_path}: cluster.automation.cloud_init.snippet_file_prefix must be a non-empty string")
    snippet_file_prefix_str = cast(str, snippet_file_prefix)
    users = cloud_init_map.get("users")
    require(isinstance(users, list) and users, f"{tfvars_path}: cluster.automation.cloud_init.users must be a non-empty list")
    return cluster_map, snippet_storage_role_str, snippet_file_prefix_str, default_values, cast(list[dict[str, Any]], users)


def resolve_snippets_datastore(cluster: dict[str, Any], tfvars_path: Path, snippet_storage_role: str) -> str:
    storage_roles = cluster.get("storage_roles")
    require(isinstance(storage_roles, dict), f"{tfvars_path}: cluster.storage_roles must be a mapping")
    storage_roles_map = cast(dict[str, Any], storage_roles)
    storage_role = storage_roles_map.get(snippet_storage_role)
    require(isinstance(storage_role, dict), f"{tfvars_path}: cluster.storage_roles.{snippet_storage_role} must be a mapping")
    storage_role_map = cast(dict[str, Any], storage_role)
    datastore = storage_role_map.get("datastore")
    require(isinstance(datastore, str) and datastore, f"{tfvars_path}: cluster.storage_roles.{snippet_storage_role}.datastore must be a non-empty string")
    datastore_str = cast(str, datastore)
    content = storage_role_map.get("content")
    require(isinstance(content, list) and "snippets" in content, f"{tfvars_path}: cluster.storage_roles.{snippet_storage_role}.content must include snippets")
    return datastore_str


def build_cloud_init_user(user: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    name = user.get("name")
    gecos = user.get("gecos")
    groups = user.get("groups")
    shell = user.get("shell")
    sudo = user.get("sudo")
    password_env = user.get("password_env")
    public_key_env = user.get("public_key_env")
    require(isinstance(name, str) and name, "cloud-init user name must be a non-empty string")
    require(isinstance(gecos, str) and gecos, "cloud-init user gecos must be a non-empty string")
    require(isinstance(groups, str) and groups, "cloud-init user groups must be a non-empty string")
    require(isinstance(shell, str) and shell, "cloud-init user shell must be a non-empty string")
    require(isinstance(sudo, list) and sudo and all(isinstance(item, str) and item for item in sudo), "cloud-init user sudo must be a non-empty list of non-empty strings")
    require(isinstance(password_env, str) and password_env, "cloud-init user password_env must be a non-empty string")
    require(isinstance(public_key_env, str) and public_key_env, "cloud-init user public_key_env must be a non-empty string")
    name_str = cast(str, name)
    gecos_str = cast(str, gecos)
    groups_str = cast(str, groups)
    shell_str = cast(str, shell)
    sudo_list = cast(list[str], sudo)
    password_env_str = cast(str, password_env)
    public_key_env_str = cast(str, public_key_env)
    require(password_env_str in env, f"missing required environment variable: {password_env_str}")
    require(public_key_env_str in env, f"missing required environment variable: {public_key_env_str}")
    return {
        "name": name_str,
        "gecos": gecos_str,
        "groups": groups_str,
        "shell": shell_str,
        "sudo": sudo_list,
        "lock_passwd": False,
        "passwd": hash_cloud_init_password(env[password_env_str]),
        "ssh_authorized_keys": [env[public_key_env_str]],
    }


def build_user_data(vm: dict[str, Any], users: list[dict[str, Any]], defaults: dict[str, Any], env: dict[str, str]) -> str:
    data = {
        "hostname": vm["name"],
        "preserve_hostname": False,
        "disable_root": defaults["disable_root"],
        "ssh_pwauth": defaults["ssh_pwauth"],
        "package_update": defaults["package_update"],
        "package_upgrade": defaults["package_upgrade"],
        "users": [build_cloud_init_user(user, env) for user in users],
    }
    return "#cloud-config\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def render_snippets(tfvars_path: Path, storage_id: str) -> list[CloudInitSnippet]:
    payload = load_generated_tfvars(tfvars_path)
    vms = payload.get("vms", [])
    require(isinstance(vms, list), f"{tfvars_path}: vms must be a list")
    cluster, snippet_storage_role, snippet_file_prefix, defaults, users = load_automation_cloud_init(payload, tfvars_path)
    snippets_datastore = resolve_snippets_datastore(cluster, tfvars_path, snippet_storage_role)
    require(storage_id == snippets_datastore, f"--storage-id {storage_id} must match cluster.automation.cloud_init snippet datastore {snippets_datastore}")
    required_env_vars = []
    for user in users:
        require(isinstance(user, dict), f"{tfvars_path}: cluster.automation.cloud_init.users entries must be objects")
        for field in ("password_env", "public_key_env"):
            value = user.get(field)
            require(isinstance(value, str) and value, f"{tfvars_path}: cluster.automation.cloud_init.users entries must define {field}")
            if value not in required_env_vars:
                required_env_vars.append(value)
    env = {name: read_required_env(name) for name in required_env_vars}
    snippets: list[CloudInitSnippet] = []
    for vm in vms:
        require(isinstance(vm, dict), f"{tfvars_path}: vms entries must be objects")
        vmid = vm.get("vmid")
        name = vm.get("name")
        require(isinstance(vmid, int), f"{tfvars_path}: vmid must be an integer")
        require(isinstance(name, str) and name, f"{tfvars_path}: name must be a non-empty string")
        file_name = f"{snippet_file_prefix}-{vmid}-user-data.yml"
        content = build_user_data(vm, users, defaults, env)
        content_bytes = content.encode("utf-8")
        snippets.append(
            CloudInitSnippet(
                vmid=vmid,
                name=name,
                file_name=file_name,
                file_id=snippet_storage_path(snippets_datastore, file_name),
                content=content,
                byte_count=len(content_bytes),
                sha256=sha256_hex(content_bytes),
            )
        )
    snippets.sort(key=lambda item: (item.vmid, item.name))
    return snippets


def build_manifest(snippets: list[CloudInitSnippet], tfvars_path: Path, storage_id: str) -> dict[str, Any]:
    tfvars_bytes = tfvars_path.read_bytes()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tfvars_path": str(tfvars_path),
        "source_tfvars_sha256": sha256_hex(tfvars_bytes),
        "storage_id": storage_id,
        "snippets": [
            {
                "vmid": snippet.vmid,
                "name": snippet.name,
                "file_name": snippet.file_name,
                "file_id": snippet.file_id,
                "byte_count": snippet.byte_count,
                "sha256": snippet.sha256,
            }
            for snippet in snippets
        ],
    }


def write_rendered_artifacts(snippets: list[CloudInitSnippet], tfvars_path: Path, storage_id: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_snippets: list[CloudInitSnippet] = []
    for snippet in snippets:
        snippet_path = output_dir / snippet.file_name
        write_text(snippet_path, snippet.content, secure=True)
        snippet_bytes = snippet_path.read_bytes()
        written_snippets.append(
            CloudInitSnippet(
                vmid=snippet.vmid,
                name=snippet.name,
                file_name=snippet.file_name,
                file_id=snippet.file_id,
                content=snippet.content,
                byte_count=len(snippet_bytes),
                sha256=sha256_hex(snippet_bytes),
            )
        )
    manifest = build_manifest(written_snippets, tfvars_path, storage_id)
    write_text(manifest_path(output_dir), json.dumps(manifest, indent=2, sort_keys=True) + "\n", secure=True)


def load_rendered_artifacts(output_dir: Path, storage_id: str) -> list[CloudInitSnippet]:
    manifest_file = manifest_path(output_dir)
    if not manifest_file.exists():
        raise ValidationError(f"{manifest_file}: missing manifest for rendered cloud-init snippets")
    payload = load_json(manifest_file)
    require(isinstance(payload, dict), f"{manifest_file}: expected a JSON object")
    require(payload.get("schema_version") == MANIFEST_SCHEMA_VERSION, f"{manifest_file}: unsupported manifest schema version")
    manifest_storage_id = payload.get("storage_id")
    require(isinstance(manifest_storage_id, str) and manifest_storage_id, f"{manifest_file}: storage_id must be a non-empty string")
    require(manifest_storage_id == storage_id, f"{manifest_file}: storage_id does not match --storage-id")
    snippets_data = payload.get("snippets")
    require(isinstance(snippets_data, list) and snippets_data, f"{manifest_file}: snippets must be a non-empty list")

    snippets: list[CloudInitSnippet] = []
    for raw_entry in snippets_data:
        require(isinstance(raw_entry, dict), f"{manifest_file}: snippets entries must be objects")
        entry = cast(dict[str, Any], raw_entry)
        vmid = entry.get("vmid")
        name = entry.get("name")
        file_name = entry.get("file_name")
        file_id = entry.get("file_id")
        byte_count = entry.get("byte_count")
        expected_sha256 = entry.get("sha256")
        require(isinstance(vmid, int), f"{manifest_file}: snippet vmid must be an integer")
        require(isinstance(name, str) and name, f"{manifest_file}: snippet name must be a non-empty string")
        require(isinstance(file_name, str) and file_name, f"{manifest_file}: snippet file_name must be a non-empty string")
        require(isinstance(file_id, str) and file_id, f"{manifest_file}: snippet file_id must be a non-empty string")
        require(isinstance(byte_count, int) and byte_count >= 0, f"{manifest_file}: snippet byte_count must be a non-negative integer")
        require(isinstance(expected_sha256, str) and len(expected_sha256) == 64, f"{manifest_file}: snippet sha256 must be a 64-character hex string")
        vmid_int = cast(int, vmid)
        name_str = cast(str, name)
        file_name_str = cast(str, file_name)
        file_id_str = cast(str, file_id)
        byte_count_int = cast(int, byte_count)
        expected_sha256_str = cast(str, expected_sha256)

        snippet_path = output_dir / file_name_str
        if not snippet_path.exists():
            raise ValidationError(f"{snippet_path}: missing rendered snippet for VM {name_str} ({vmid_int})")
        try:
            snippet_bytes = snippet_path.read_bytes()
        except OSError as exc:
            raise ValidationError(f"{snippet_path}: unable to read rendered snippet for VM {name_str} ({vmid_int})") from exc
        actual_sha256 = sha256_hex(snippet_bytes)
        if len(snippet_bytes) != byte_count_int or actual_sha256 != expected_sha256_str:
            raise ValidationError(f"{snippet_path}: checksum mismatch for VM {name_str} ({vmid_int})")
        try:
            content = snippet_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"{snippet_path}: rendered snippet for VM {name_str} ({vmid_int}) is not valid UTF-8") from exc
        snippets.append(
            CloudInitSnippet(
                vmid=vmid_int,
                name=name_str,
                file_name=file_name_str,
                file_id=file_id_str,
                content=content,
                byte_count=byte_count_int,
                sha256=actual_sha256,
            )
        )
    snippets.sort(key=lambda item: (item.vmid, item.name))
    return snippets


def run_ssh_snippet_command(snippet: CloudInitSnippet, args: argparse.Namespace, command: list[str], input_text: str | None = None) -> None:
    remote = f"{args.ssh_user}@{args.pve_host}"
    ssh_argv = ["ssh", remote, *command]
    timeout = resolve_ssh_timeout(getattr(args, "ssh_timeout", None))
    try:
        subprocess.run(
            ssh_argv,
            input=input_text,
            text=input_text is not None,
            check=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ValidationError("ssh is required for snippet operations") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidationError(
            f"ssh timed out after {timeout:.0f}s while processing {snippet.file_name} for VM {snippet.name} ({snippet.vmid})"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ValidationError(
            f"ssh command failed with exit code {exc.returncode} while processing {snippet.file_name} for VM {snippet.name} ({snippet.vmid})"
        ) from exc


def upload_snippets(snippets: list[CloudInitSnippet], args: argparse.Namespace) -> None:
    for snippet in snippets:
        run_ssh_snippet_command(
            snippet,
            args,
            [
                "sudo",
                "-n",
                "/usr/local/sbin/astra-pve-snippet-upload",
                "--storage",
                args.storage_id,
                "--filename",
                snippet.file_name,
            ],
            input_text=snippet.content,
        )


def verify_snippets(snippets: list[CloudInitSnippet], args: argparse.Namespace) -> None:
    for snippet in snippets:
        run_ssh_snippet_command(
            snippet,
            args,
            [
                "sudo",
                "-n",
                "/usr/local/sbin/astra-pve-snippet-upload",
                "--storage",
                args.storage_id,
                "--filename",
                snippet.file_name,
                "--verify",
                "--sha256",
                snippet.sha256,
            ],
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "render":
        snippets = render_snippets(args.tfvars, args.storage_id)
        write_rendered_artifacts(snippets, args.tfvars, args.storage_id, args.output_dir)
        print(f"rendered {len(snippets)} cloud-init snippets to {args.output_dir}")
    elif args.command == "upload":
        snippets = load_rendered_artifacts(args.output_dir, args.storage_id)
        upload_snippets(snippets, args)
        print(f"uploaded {len(snippets)} cloud-init snippets to {args.pve_host}")
    elif args.command == "verify":
        snippets = load_rendered_artifacts(args.output_dir, args.storage_id)
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
