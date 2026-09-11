"""Explicit native dependency preparation and portable locked package reuse."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import shutil
import tarfile

from iaas_automation.common.errors import require
from .execution import Execution


def prepare_dependencies(root: Path, execution: Execution, archive: Path, tofu: str = "tofu") -> None:
    before = (root / ".terraform.lock.hcl").read_bytes()
    execution.run("prepare-dependencies", [tofu, "init", "-backend=false", "-input=false", "-lockfile=readonly"], root)
    require((root / ".terraform.lock.hcl").read_bytes() == before, "dependency preparation changed the caller lockfile")
    require(not archive.exists(), "dependency output already exists")
    with tarfile.open(archive, "w:gz", dereference=True) as bundle:
        for name in (".terraform.lock.hcl", ".terraform/providers", ".terraform/modules"):
            path = root / name
            if path.exists():
                bundle.add(path, arcname=name)
    archive.chmod(0o600)


def restore_dependencies(archive: Path, root: Path, destination: Path) -> Path:
    require(not destination.exists(), "dependency restoration directory must be new")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            allowed = member.name == ".terraform.lock.hcl" or path.parts[:2] in {
                (".terraform", "providers"), (".terraform", "modules")}
            require(allowed and not path.is_absolute() and ".." not in path.parts
                    and (member.isfile() or member.isdir()), "invalid dependency archive member")
        lock = bundle.extractfile(".terraform.lock.hcl")
        require(lock is not None, "dependency archive has no provider lock")
        assert lock is not None
        with lock:
            require(lock.read() == (root / ".terraform.lock.hcl").read_bytes(), "dependency provider lock does not match root")
        destination.mkdir(parents=True, mode=0o700)
        bundle.extractall(destination, filter="data")
    modules = destination / ".terraform/modules"
    if modules.exists():
        (root / ".terraform").mkdir(mode=0o700, exist_ok=True)
        shutil.copytree(modules, root / ".terraform/modules")
    for path in destination.rglob("*"):
        # Providers must remain executable; sensitive directory access is gated
        # by the task's 0700 parent rather than stripping executable bits.
        if path.is_dir():
            path.chmod(0o700)
    return destination / ".terraform/providers"
