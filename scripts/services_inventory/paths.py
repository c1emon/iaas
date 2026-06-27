"""Default repository paths for the service inventory tool."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SERVICES = ROOT / "inventory" / "services.yml"
DEFAULT_VMS = ROOT / "inventory" / "vms.yml"
DEFAULT_DOCS = ROOT / "docs" / "generated" / "services.md"
