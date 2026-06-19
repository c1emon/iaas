"""File and YAML I/O helpers for the inventory tool."""

from __future__ import annotations

import json
import yaml
from pathlib import Path
from typing import Any, cast

from .errors import ValidationError, require


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


def load_json(path: Path) -> Any:
    """Load JSON from disk."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    except OSError as exc:
        raise ValidationError(f"{path}: unable to read file: {exc}") from exc


def check_text_file(path: Path, expected_text: str) -> bool:
    """Return True when the file bytes match the expected text."""
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return existing == expected_text


def check_outputs(expected: dict[str, str], paths: dict[str, Path]) -> list[str]:
    """Return stale/missing output paths in deterministic order."""
    mismatches: list[str] = []
    for key in ("tfvars", "ansible", "docs"):
        path = paths[key]
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            mismatches.append(f"missing: {path}")
            continue
        if existing != expected[key]:
            mismatches.append(f"stale: {path}")
    return mismatches
