"""Materialize explicitly declared root files, retaining relative relationships."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Any

from iaas_automation.common.errors import require


def relative_path(name: Any) -> PurePosixPath:
    require(isinstance(name, str) and bool(name), "root file destination must be relative")
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in name,
            "root file destination escapes its declared bundle")
    return path


def materialize_root(spec: dict[str, Any], files: dict[str, Path], destination: Path) -> Path:
    require(isinstance(spec, dict) and set(spec) == {"id", "directory", "files"},
            "root requires id, directory and explicit files mapping")
    require(isinstance(spec["id"], str) and bool(spec["id"]), "root id is required")
    directory = relative_path(spec["directory"])
    entries = spec["files"]
    require(isinstance(entries, dict) and bool(entries), "root files must be explicitly declared")
    paths: list[tuple[Path, Path]] = []
    for name, alias in entries.items():
        relative = relative_path(name)
        require(alias in files, "declared root file is not supplied")
        require(not any(part in {".git", ".terraform"} for part in relative.parts)
                and ".tfstate" not in relative.name and not relative.name.endswith(".tfplan")
                and relative.name != "zz_iaas_backend_override.tf.json",
                "state, caches and runtime-owned files cannot be root inputs")
        paths.append((files[alias], destination.joinpath(*relative.parts)))
    require(not destination.exists(), "root materialization destination must be new")
    destination.mkdir(parents=True, mode=0o700)
    for source, output in paths:
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as target:
            target.write(source.read_bytes())
        output.chmod(0o600 | (source.stat().st_mode & 0o100))
    root = destination.joinpath(*directory.parts)
    require(root.is_dir(), "declared root directory is absent")
    require((root / ".terraform.lock.hcl").is_file(), "caller provider lockfile is required")
    return root
