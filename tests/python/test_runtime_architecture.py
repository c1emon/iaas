"""Platform selection must follow the executable and never silently emulate."""

from pathlib import Path
import importlib.util
import re
import subprocess

import pytest
import yaml

from iaas.common.errors import ValidationError
from iaas.runtime_config import selection
from iaas.runtime_execution.operations import capabilities


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
    result = subprocess.run(["/bin/sh", str(ROOT / "automation/oci/iaas-runtime/build.sh"), "test:arch"],
                            env={"PATH": f"{tmp_path}:/usr/bin:/bin", "RUNTIME_PLATFORM": platform},
                            capture_output=True, text=True)
    if platform == "linux/riscv64":
        assert result.returncode == 2
        assert not result.stdout
    else:
        assert result.returncode == 0
        assert result.stdout.splitlines()[:5] == ["buildx", "build", "--load", "--platform", platform]
        assert str(ROOT / "automation/oci/iaas-runtime/Dockerfile") in result.stdout
        assert result.stdout.splitlines()[-1] == str(ROOT)


def test_disk_image_builder_uses_its_own_dockerfile_and_explicit_platform(tmp_path):
    docker = tmp_path / "docker"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    docker.chmod(0o755)
    result = subprocess.run(["/bin/sh", str(ROOT / "automation/oci/disk-image-builder/build.sh"), "test:builder"],
                            env={"PATH": f"{tmp_path}:/usr/bin:/bin"}, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.splitlines()[:5] == ["buildx", "build", "--load", "--platform", "linux/amd64"]
    assert str(ROOT / "automation/oci/disk-image-builder/Dockerfile") in result.stdout
    assert result.stdout.splitlines()[-1] == str(ROOT)


def test_ci_checks_both_architectures_serially():
    job = yaml.safe_load((ROOT / ".github/workflows/offline-validation.yml").read_text())["jobs"]["runtime"]
    assert job["strategy"]["max-parallel"] == 1
    assert {item["arch"] for item in job["strategy"]["matrix"]["include"]} == {"amd64", "arm64"}
    assert any("runtime-tofu-check" in step.get("run", "") for step in job["steps"])


def test_runtime_pruning_preserves_only_sdk_documentation_packages():
    dockerfile = (ROOT / "automation/oci/iaas-runtime/Dockerfile").read_text()
    dependency_stage = dockerfile.split(" AS dependencies", 1)[1]
    workdir = re.search(r"^WORKDIR (.+)$", dependency_stage, re.MULTILINE)
    python_version = re.search(r"^FROM python:(\d+\.\d+)", dockerfile, re.MULTILINE)
    assert workdir is not None and python_version is not None
    site_packages = f"{workdir.group(1).lstrip('/')}/.venv/lib/python{python_version.group(1)}/site-packages"

    inspect_path = ROOT / "automation/oci/checks/inspect_image.py"
    spec = importlib.util.spec_from_file_location("runtime_inspect_image", inspect_path)
    assert spec is not None and spec.loader is not None
    inspect_image = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspect_image)

    preserved = inspect_image._is_preserved_package_doc
    assert preserved(inspect_image.PurePosixPath(f"{site_packages}/boto3/docs"))
    assert preserved(inspect_image.PurePosixPath(f"{site_packages}/botocore/docs/bcdoc/restdoc.py"))
    assert not preserved(inspect_image.PurePosixPath(f"{site_packages}/other/docs"))
