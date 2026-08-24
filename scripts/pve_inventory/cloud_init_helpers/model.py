from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from scripts.common.errors import require


MANIFEST_FILE_NAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = 1
DEFAULT_SSH_TIMEOUT_SECONDS = 30.0
_SAFE_STORAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SAFE_SNIPPET_FILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")


@dataclass(frozen=True)
class CloudInitSnippet:
    vmid: int
    name: str
    file_name: str
    file_id: str
    content: str
    byte_count: int = 0
    sha256: str = ""
    kind: str = "user-data"


def snippet_storage_path(storage_id: str, file_name: str) -> str:
    validate_storage_id(storage_id)
    validate_snippet_file_name(file_name)
    return f"{storage_id}:snippets/{file_name}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_storage_id(storage_id: str) -> str:
    require(isinstance(storage_id, str), "storage_id must be a string")
    require(storage_id.strip() == storage_id, "storage_id must not contain leading or trailing whitespace")
    require(bool(storage_id) and _SAFE_STORAGE_ID_RE.fullmatch(storage_id) is not None, "storage_id must be a non-empty safe storage identifier")
    return storage_id


def validate_snippet_file_name(file_name: str) -> str:
    require(isinstance(file_name, str), "file_name must be a string")
    require(file_name.strip() == file_name, "file_name must not contain leading or trailing whitespace")
    require(
        bool(file_name)
        and "/" not in file_name
        and "\\" not in file_name
        and ".." not in file_name
        and _SAFE_SNIPPET_FILE_NAME_RE.fullmatch(file_name) is not None,
        "file_name must be a safe snippet basename",
    )
    return file_name


def validate_sha256_hex(value: str) -> str:
    require(isinstance(value, str), "sha256 must be a string")
    require(_SAFE_SHA256_RE.fullmatch(value) is not None, "sha256 must be a 64-character hexadecimal digest")
    return value


def validate_snippet_kind(kind: str) -> str:
    require(kind in {"user-data", "network-config"}, "kind must be user-data or network-config")
    return kind
