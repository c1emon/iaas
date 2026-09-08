"""Representative external-directory correctness checks."""

from pathlib import Path
import os
import shutil
import subprocess

import pytest

from iaas_automation.runtime_paths import validate_paths


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_make_environment(monkeypatch):
    for name in ("MAKEFLAGS", "MAKEOVERRIDES", "MFLAGS", "ENVIRONMENT_DIR", "OUTPUT_DIR",
                 "GENERATED_DIR", "RUNTIME_DIR", "PVE_DIR", "INVENTORY_DIR", "ASTRA"):
        monkeypatch.delenv(name, raising=False)


def test_generated_subtree_and_external_output(tmp_path):
    environment = tmp_path / "environment"
    validate_paths(environment, tmp_path / "implementation", [
        environment / "generated", tmp_path / "output with spaces",
    ])


@pytest.mark.parametrize("location", ["environment", "environment/inventory/result", "environment/ansible", "implementation/cache", "."])
def test_reject_overlapping_outputs(tmp_path, location):
    with pytest.raises(ValueError, match="output"):
        validate_paths(tmp_path / "environment", tmp_path / "implementation", [tmp_path / location])


def test_symlink_output_cannot_overwrite_inputs(tmp_path):
    environment = tmp_path / "environment"
    (environment / "inventory").mkdir(parents=True)
    output = tmp_path / "output"
    output.symlink_to(environment / "inventory", target_is_directory=True)
    with pytest.raises(ValueError, match="overlaps"):
        validate_paths(environment, tmp_path / "implementation", [output / "vms.yml"])


def test_make_help_and_missing_environment_from_arbitrary_directory(tmp_path):
    command = ["make", "-f", str(ROOT / "Makefile")]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0
    assert "IaaS operations" in result.stdout
    result = subprocess.run(command + ["pve-generate"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "ENVIRONMENT_DIR is required" in result.stderr
    result = subprocess.run(command + ["help", "ASTRA=old"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "no longer supported" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_external_readonly_environment_generation_and_stale_check(tmp_path):
    environment = tmp_path / "external environment"
    inventory = environment / "inventory"
    inventory.mkdir(parents=True)
    for name in ("pve-cluster.yml", "vms.yml", "services.yml", "foundation.yml"):
        shutil.copyfile(ROOT / "environments/astra/inventory" / name, inventory / name)
        (inventory / name).chmod(0o444)
    inventory.chmod(0o555)
    environment.chmod(0o555)
    output = tmp_path / "external output"
    command = ["make", "-f", str(ROOT / "Makefile"),
               f"ENVIRONMENT_DIR={environment}", f"OUTPUT_DIR={output}"]
    try:
        result = subprocess.run(command + ["generate", "check-generated"], cwd=tmp_path,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert not (environment / "generated").exists()
        docs = output / "generated/docs/services.md"
        assert "environments/astra" not in docs.read_text()
        assert docs.stat().st_uid == os.getuid()
        docs.write_text("stale\n")
        result = subprocess.run(command + ["services-check"], cwd=tmp_path,
                                capture_output=True, text=True)
        assert result.returncode != 0
        result = subprocess.run(command + [f"SERVICES_DOCS={inventory}/services.yml", "services-generate"],
                                cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode != 0
        assert "overlaps" in result.stderr
    finally:
        environment.chmod(0o755)
        inventory.chmod(0o755)
