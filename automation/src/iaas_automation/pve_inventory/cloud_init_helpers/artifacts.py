from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import load_json, write_text

from .model import CloudInitSnippet, MANIFEST_FILE_NAME, MANIFEST_SCHEMA_VERSION, sha256_hex, validate_sha256_hex, validate_snippet_file_name, validate_snippet_kind, validate_storage_id


def manifest_path(output_dir: Path) -> Path:
    return output_dir / MANIFEST_FILE_NAME


def build_manifest(snippets: list[CloudInitSnippet], tfvars_path: Path, storage_id: str) -> dict[str, Any]:
    validate_storage_id(storage_id)
    tfvars_bytes = tfvars_path.read_bytes()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tfvars_path": str(tfvars_path),
        "source_tfvars_sha256": sha256_hex(tfvars_bytes),
        "storage_id": storage_id,
        "snippets": [
            {
                "kind": snippet.kind,
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
        validate_snippet_file_name(snippet.file_name)
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
                kind=snippet.kind,
            )
        )
    manifest = build_manifest(written_snippets, tfvars_path, storage_id)
    write_text(manifest_path(output_dir), json.dumps(manifest, indent=2, sort_keys=True) + "\n", secure=True)


def load_rendered_artifacts(output_dir: Path, storage_id: str, tfvars_path: Path, *, allow_empty: bool = False) -> list[CloudInitSnippet]:
    validate_storage_id(storage_id)
    manifest_file = manifest_path(output_dir)
    if not manifest_file.exists():
        raise ValidationError(f"{manifest_file}: missing manifest for rendered cloud-init snippets")
    payload = load_json(manifest_file)
    require(isinstance(payload, dict), f"{manifest_file}: expected a JSON object")
    require(payload.get("schema_version") == MANIFEST_SCHEMA_VERSION, f"{manifest_file}: unsupported manifest schema version")
    try:
        source_bytes = tfvars_path.read_bytes()
    except OSError as exc:
        raise ValidationError("unable to read current --tfvars input") from exc
    require(payload.get("source_tfvars_sha256") == sha256_hex(source_bytes),
            "rendered manifest does not match current --tfvars; render cloud-init again")
    manifest_storage_id = payload.get("storage_id")
    require(isinstance(manifest_storage_id, str) and manifest_storage_id, f"{manifest_file}: storage_id must be a non-empty string")
    validate_storage_id(manifest_storage_id)
    require(manifest_storage_id == storage_id, f"{manifest_file}: storage_id does not match --storage-id")
    snippets_data = payload.get("snippets")
    require(isinstance(snippets_data, list) and (allow_empty or bool(snippets_data)), f"{manifest_file}: snippets must be a non-empty list")

    snippets: list[CloudInitSnippet] = []
    for raw_entry in snippets_data:
        require(isinstance(raw_entry, dict), f"{manifest_file}: snippets entries must be objects")
        entry = cast(dict[str, Any], raw_entry)
        vmid = entry.get("vmid")
        kind = entry.get("kind", "user-data")
        name = entry.get("name")
        file_name = entry.get("file_name")
        file_id = entry.get("file_id")
        byte_count = entry.get("byte_count")
        expected_sha256 = entry.get("sha256")
        require(isinstance(vmid, int), f"{manifest_file}: snippet vmid must be an integer")
        require(isinstance(kind, str) and kind, f"{manifest_file}: snippet kind must be a non-empty string")
        require(isinstance(name, str) and name, f"{manifest_file}: snippet name must be a non-empty string")
        require(isinstance(file_name, str) and file_name, f"{manifest_file}: snippet file_name must be a non-empty string")
        require(isinstance(file_id, str) and file_id, f"{manifest_file}: snippet file_id must be a non-empty string")
        require(isinstance(byte_count, int) and byte_count >= 0, f"{manifest_file}: snippet byte_count must be a non-negative integer")
        require(isinstance(expected_sha256, str), f"{manifest_file}: snippet sha256 must be a 64-character hex string")
        vmid_int = cast(int, vmid)
        kind_str = validate_snippet_kind(cast(str, kind))
        name_str = cast(str, name)
        file_name_str = cast(str, file_name)
        file_id_str = cast(str, file_id)
        byte_count_int = cast(int, byte_count)
        expected_sha256_str = cast(str, expected_sha256)
        validate_snippet_file_name(file_name_str)
        validate_sha256_hex(expected_sha256_str)

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
                kind=kind_str,
            )
        )
    snippets.sort(key=lambda item: (item.vmid, item.name))
    return snippets
