"""Offline native checksum acceptance for a previously downloaded dependency bundle.

Run inside the fixed runtime image with Docker ``--network none``. This helper
never downloads providers and emits only a safe JSON result, not tool output.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from iaas.runtime_execution.dependencies import restore_dependencies


def _lock(archive: Path) -> tuple[bytes, str]:
    with tarfile.open(archive, "r:gz") as bundle:
        stream = bundle.extractfile(".terraform.lock.hcl")
        if stream is None:
            raise ValueError("missing lock")
        with stream:
            lock = stream.read()
    matches = re.findall(
        r'provider\s+"([^"\n]*bpg/proxmox)"\s*\{([^}]+)\}',
        lock.decode("utf-8"),
    )
    if len(matches) != 1 or not re.search(
        r'version\s*=\s*"0\.111\.1"', matches[0][1]
    ):
        raise ValueError("unexpected provider lock")
    return lock, matches[0][0]


def _init(root: Path, providers: Path, tofu: str) -> subprocess.CompletedProcess[str]:
    home = root / "home"
    home.mkdir(mode=0o700)
    config = root / "tofu.rc"
    config.write_text("disable_checkpoint = true\n", encoding="utf-8")
    # No host credential, backend/state, proxy or provider-cache channel enters
    # either native invocation. The plugin directory is the restored bundle.
    environment = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "TMPDIR": str(root),
        "TF_CLI_CONFIG_FILE": str(config),
        "TF_IN_AUTOMATION": "1",
        "CHECKPOINT_DISABLE": "1",
    }
    return subprocess.run(
        [tofu, "init", "-backend=false", "-input=false", "-lockfile=readonly",
         "-get=false", "-no-color", f"-plugin-dir={providers}"],
        cwd=root, env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=180, check=False,
    )


def verify(archive: Path, output: Path) -> dict[str, object]:
    tofu = shutil.which("tofu")
    if tofu is None:
        raise ValueError("missing OpenTofu")
    lock, source = _lock(archive)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    report: dict[str, object] = {"status": "failed", "provider_version": "0.111.1"}
    for label in ("valid", "tampered"):
        root = output / label
        root.mkdir(mode=0o700)
        (root / "main.tf.json").write_text(json.dumps({
            "terraform": {"required_providers": {
                "proxmox": {"source": source, "version": "= 0.111.1"}
            }}
        }), encoding="utf-8")
        lock_path = root / ".terraform.lock.hcl"
        lock_path.write_bytes(lock)
        providers = restore_dependencies(archive, root, output / f"{label}-restored")
        executables = sorted(
            path for path in providers.rglob("terraform-provider-proxmox*")
            if path.is_file() and path.stat().st_mode & 0o111
        )
        if len(executables) != 1 or "0.111.1" not in executables[0].parts:
            raise ValueError("unexpected restored provider package")
        if label == "tampered":
            with executables[0].open("ab") as stream:
                stream.write(b"\niaas-checksum-tamper-fixture\n")
        result = _init(root, providers, tofu)
        unchanged = lock_path.read_bytes() == lock
        checksum_rejected = result.returncode != 0 and (
            "checksum" in result.stdout.lower()
            and ("doesn't match" in result.stdout.lower()
                 or "does not match" in result.stdout.lower())
        )
        report[label] = {
            "exit_code": result.returncode,
            "lock_unchanged": unchanged,
            "provider_executables": len(executables),
            "checksum_rejected": checksum_rejected,
        }
        passed = unchanged and (
            result.returncode == 0 if label == "valid" else checksum_rejected
        )
        if not passed:
            (output / "result.json").write_text(json.dumps(report) + "\n", encoding="utf-8")
            return report
    report["status"] = "success"
    (output / "result.json").write_text(json.dumps(report) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args.archive.resolve(strict=True), args.output.absolute())
    except Exception:
        # Exception/tool text can contain client configuration; never expose it.
        report = {"status": "failed", "reason": "offline checksum acceptance failed"}
    print(json.dumps(report))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
