"""Offline tests for the PVE cloud-init snippet upload wrapper."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "automation" / "pve-node" / "bin" / "iaas-pve-snippet-upload"


def test_capability_probe_is_read_only_and_reports_missing_dependency(tmp_path):
    fake = tmp_path / 'pvesm'
    marker = tmp_path / 'called'
    fake.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
    fake.chmod(0o755)
    env = os.environ | {'IAAS_PVE_SNIPPET_UPLOAD_PVESM': str(fake)}
    before = set(tmp_path.iterdir())
    result = run_wrapper(['--capabilities'], env)
    assert result.returncode == 0
    declaration = json.loads(result.stdout)
    assert declaration['schema_version'] == 'helper-capabilities/v1'
    assert declaration['helper'] == 'upload'
    assert all(declaration['capabilities'].values())
    assert set(tmp_path.iterdir()) == before
    fake.unlink()
    result = run_wrapper(['--capabilities'], env)
    assert not any(json.loads(result.stdout)['capabilities'].values())
    assert run_wrapper(['--capabilities', '--create-only'], env).returncode != 0


def test_create_only_never_overwrites_existing_file_or_symlink(tmp_path):
    filename = 'accept-9005-user-data.yml'
    target = tmp_path / 'snippets' / filename
    target.parent.mkdir()
    fake = make_fake_pvesm(tmp_path, target)
    env = os.environ | {'IAAS_PVE_SNIPPET_UPLOAD_PVESM': str(fake), 'FAKE_PVESM_TARGET': str(target)}
    args = ['bash', str(WRAPPER), '--create-only', '--storage', 'local', '--filename', filename]
    created = subprocess.run(args, input='#cloud-config\nusers: [default]\n', text=True, capture_output=True, env=env)
    assert created.returncode == 0
    original = target.read_bytes()
    assert subprocess.run(args, input='replacement', text=True, capture_output=True, env=env).returncode != 0
    assert target.read_bytes() == original
    target.unlink()
    victim = tmp_path / 'victim'
    target.symlink_to(victim)
    assert subprocess.run(args, input='replacement', text=True, capture_output=True, env=env).returncode != 0
    assert not victim.exists()


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


def test_unresolved_storage_fails_before_writes(tmp_path: Path) -> None:
    fake_pvesm = tmp_path / "pvesm"
    fake_pvesm.write_text("#!/bin/sh\nexit 1\n")
    fake_pvesm.chmod(0o755)
    result = run_wrapper(["--storage", "images", "--filename", "opentofu-vm-501-user-data.yml"],
                         os.environ | {"IAAS_PVE_SNIPPET_UPLOAD_PVESM": str(fake_pvesm)})
    assert result.returncode != 0
    assert "unable to resolve" in result.stderr
    assert list(tmp_path.iterdir()) == [fake_pvesm]


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


def test_observation_missing_then_ready_and_symlink_conflict(tmp_path):
    filename = 'vm-501-user-data.yml'
    target = tmp_path / 'snippets' / filename
    target.parent.mkdir()
    fake = make_fake_pvesm(tmp_path, target)
    env = os.environ | {'IAAS_PVE_SNIPPET_UPLOAD_PVESM': str(fake), 'FAKE_PVESM_TARGET': str(target)}
    payload = '#cloud-config\nhostname: vm\n'
    args = ['--verify', '--observe', '--storage', 'local', '--filename', filename,
            '--sha256', hashlib.sha256(payload.encode()).hexdigest()]
    missing = json.loads(run_wrapper(args, env).stdout)
    assert missing['status'] == 'pending' and missing['reason_code'] == 'exact_target_absent'
    target.write_text(payload)
    ready = json.loads(run_wrapper(args, env).stdout)
    assert ready['status'] == 'ready' and ready['inode'] == target.stat().st_ino
    target.unlink()
    other = tmp_path / 'other.yml'
    other.write_text(payload)
    target.symlink_to(other)
    failed = json.loads(run_wrapper(args, env).stdout)
    assert failed['status'] == 'failed' and failed['reason_code'] == 'not_exclusive_regular_file'
    assert other.read_text() == payload
