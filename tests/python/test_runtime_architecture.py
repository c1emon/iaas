"""Platform selection must follow the executable and never silently emulate."""

from pathlib import Path
import subprocess

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_config import selection
from iaas_automation.runtime_execution.operations import capabilities


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("machine,expected", [("x86_64", "linux/amd64"), ("aarch64", "linux/arm64"), ("arm64", "linux/arm64")])
def test_capabilities_report_running_architecture(monkeypatch, machine, expected):
    monkeypatch.setattr(selection.platform, "machine", lambda: machine)
    assert capabilities()["platforms"] == [expected]


def test_unknown_architecture_is_rejected(monkeypatch):
    monkeypatch.setattr(selection.platform, "machine", lambda: "riscv64")
    with pytest.raises(ValidationError, match="architecture"):
        capabilities()


@pytest.mark.parametrize("platform", ["linux/amd64", "linux/arm64", "linux/riscv64"])
def test_build_selects_one_explicit_platform(tmp_path, platform):
    docker = tmp_path / "docker"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    docker.chmod(0o755)
    result = subprocess.run(["/bin/sh", str(ROOT / "automation/runtime/build.sh"), "test:arch"],
                            env={"PATH": f"{tmp_path}:/usr/bin:/bin", "RUNTIME_PLATFORM": platform},
                            capture_output=True, text=True)
    if platform == "linux/riscv64":
        assert result.returncode == 2
        assert not result.stdout
    else:
        assert result.returncode == 0
        assert result.stdout.splitlines()[:5] == ["buildx", "build", "--load", "--platform", platform]


def test_ci_checks_both_architectures_serially():
    job = yaml.safe_load((ROOT / ".github/workflows/offline-validation.yml").read_text())["jobs"]["runtime"]
    assert job["strategy"]["max-parallel"] == 1
    assert {item["arch"] for item in job["strategy"]["matrix"]["include"]} == {"amd64", "arm64"}
    assert any("runtime-tofu-check" in step.get("run", "") for step in job["steps"])
