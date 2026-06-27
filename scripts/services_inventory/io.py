"""I/O helpers for the service inventory tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from scripts.pve_inventory.errors import ValidationError, require


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:  # type: ignore[attr-defined]
        raise ValidationError(f"{path}: invalid YAML: {exc}") from exc
    except OSError as exc:
        raise ValidationError(f"{path}: unable to read file: {exc}") from exc
    require(isinstance(data, dict), f"{path}: expected a mapping at the document root")
    return cast(dict[str, Any], data)


def write_text(path: Path, text: str) -> None:
    """Write a UTF-8 text file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
