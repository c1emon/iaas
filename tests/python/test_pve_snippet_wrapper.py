"""Offline tests for the PVE cloud-init snippet upload wrapper."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "automation" / "pve-node" / "bin" / "iaas-pve-snippet-upload"


def make_fake_pvesm(tmp_path: Path, target_path: Path) -> Path:
    script = tmp_path / "pvesm"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ ${1-} != path ]]; then\n"
        "  exit 2\n"
        "fi\n"
        "printf '%s\\n' \"${FAKE_PVESM_TARGET}\"\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def run_wrapper(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(WRAPPER), *args], capture_output=True, text=True, env=env)


def test_verify_with_matching_checksum_succeeds(tmp_path: Path) -> None:
    storage = "images"
    filename = "opentofu-vm-501-user-data.yml"
    target_path = tmp_path / storage / "snippets" / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "#cloud-config\nhostname: media-lab-01\n"
    target_path.write_text(payload, encoding="utf-8")

    fake_pvesm = make_fake_pvesm(tmp_path, target_path)
    env = os.environ | {
        "IAAS_PVE_SNIPPET_UPLOAD_PVESM": str(fake_pvesm),
        "FAKE_PVESM_TARGET": str(target_path),
    }

    result = run_wrapper([
        "--verify",
        "--storage",
        storage,
        "--filename",
        filename,
        "--sha256",
        hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    ], env)

    assert result.returncode == 0
    assert result.stderr == ""
    assert target_path.read_text(encoding="utf-8") == payload


def test_verify_with_network_config_checksum_succeeds(tmp_path: Path) -> None:
    storage = "images"
    filename = "opentofu-vm-501-network-config.yml"
    target_path = tmp_path / storage / "snippets" / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "version: 2\nethernets: {}\n"
    target_path.write_text(payload, encoding="utf-8")

    fake_pvesm = make_fake_pvesm(tmp_path, target_path)
    env = os.environ | {
        "IAAS_PVE_SNIPPET_UPLOAD_PVESM": str(fake_pvesm),
        "FAKE_PVESM_TARGET": str(target_path),
    }

    result = run_wrapper([
        "--verify",
        "--storage",
        storage,
        "--filename",
        filename,
        "--sha256",
        hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    ], env)

    assert result.returncode == 0
    assert result.stderr == ""


def test_verify_with_mismatched_checksum_fails_without_mutation(tmp_path: Path) -> None:
    storage = "images"
    filename = "opentofu-vm-501-user-data.yml"
    target_path = tmp_path / storage / "snippets" / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "#cloud-config\nhostname: media-lab-01\n"
    target_path.write_text(payload, encoding="utf-8")

    fake_pvesm = make_fake_pvesm(tmp_path, target_path)
    env = os.environ | {
        "IAAS_PVE_SNIPPET_UPLOAD_PVESM": str(fake_pvesm),
        "FAKE_PVESM_TARGET": str(target_path),
    }

    result = run_wrapper([
        "--verify",
        "--storage",
        storage,
        "--filename",
        filename,
        "--sha256",
        "0" * 64,
    ], env)

    assert result.returncode == 1
    assert "checksum mismatch" in result.stderr
    assert target_path.read_text(encoding="utf-8") == payload


def test_verify_missing_file_fails(tmp_path: Path) -> None:
    storage = "images"
    filename = "opentofu-vm-501-user-data.yml"
    target_path = tmp_path / storage / "snippets" / filename

    fake_pvesm = make_fake_pvesm(tmp_path, target_path)
    env = os.environ | {
        "IAAS_PVE_SNIPPET_UPLOAD_PVESM": str(fake_pvesm),
        "FAKE_PVESM_TARGET": str(target_path),
    }

    result = run_wrapper([
        "--verify",
        "--storage",
        storage,
        "--filename",
        filename,
        "--sha256",
        "0" * 64,
    ], env)

    assert result.returncode == 1
    assert "missing snippet" in result.stderr


def test_verify_rejects_invalid_sha256_argument() -> None:
    result = run_wrapper([
        "--verify",
        "--storage",
        "images",
        "--filename",
        "opentofu-vm-501-user-data.yml",
        "--sha256",
        "not-a-sha",
    ], os.environ.copy())

    assert result.returncode == 1
    assert "sha256 must be a 64-character hexadecimal digest" in result.stderr
