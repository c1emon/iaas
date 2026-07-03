"""Default repository paths for the foundation recovery inventory tool."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = ROOT / "inventory" / "foundation.yml"
DEFAULT_DOCS = ROOT / "docs" / "generated" / "foundation-recovery.md"
