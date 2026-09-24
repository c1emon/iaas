"""Exercise the real Make recipes with inert Python and OpenTofu substitutes."""

import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.integration


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("operation", ["plan", "apply", "destroy"])
def test_legacy_make_pve_write_entrypoints_are_rejected(tmp_path: Path, operation: str) -> None:
    log = tmp_path / "calls"
    runner = tmp_path / "runner"
    runner.write_text('''#!/usr/bin/env python3
import os, sys, time
args = sys.argv[1:]
if "iaas.runtime_paths" in args:
    sys.exit(0)
if "iaas.pve_inventory.cli" in args:
    phase = "check"
elif "iaas.pve_inventory.cloud_init" in args:
    phase = args[2]
else:
    phase = args[1]
with open(os.environ["WORKFLOW_LOG"], "a") as stream:
    stream.write(phase + "\\n")
if phase == "check" and os.environ["STALE_INPUT"] == "1":
    sys.exit(1)
if phase == "render":
    time.sleep(0.1)
    with open(os.environ["WORKFLOW_LOG"], "a") as stream:
        stream.write("render-done\\n")
''')
    runner.chmod(0o755)
    result = subprocess.run([
        "make", "-f", str(ROOT / "Makefile"), f"pve-{operation}",
        f"PYTHON={runner}", f"TOFU={runner}", f"ENVIRONMENT_DIR={tmp_path}",
        f"OUTPUT_DIR={tmp_path / 'output'}", f"PVE_DIR={tmp_path}",
        "STORAGE_ID=images", "PVE_HOST=example.invalid", "PVE_SSH_USER=ops",
    ], cwd=tmp_path, env=os.environ | {"MAKEFLAGS": "-j8", "WORKFLOW_LOG": str(log)},
        capture_output=True, text=True)
    assert result.returncode != 0
    assert not log.exists() or not log.read_text().strip()
    assert "removed" in result.stderr
