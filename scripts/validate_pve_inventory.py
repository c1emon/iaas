#!/usr/bin/env python3
"""CLI wrapper for PVE inventory validation/generation.

Keeps the historical script path stable while delegating to the package CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pve_inventory.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
