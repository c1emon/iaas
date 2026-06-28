from __future__ import annotations

import hashlib
from dataclasses import dataclass


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


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
