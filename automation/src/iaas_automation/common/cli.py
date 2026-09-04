"""Shared CLI validation boundary helpers."""

from __future__ import annotations

import sys
from collections.abc import Callable

from .errors import ValidationError


def run_validation_cli(main: Callable[[list[str] | None], int], argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except ValidationError as exc:
        print(f"FAIL validation: {exc}", file=sys.stderr)
        return 1
