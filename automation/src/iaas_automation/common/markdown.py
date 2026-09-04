"""Shared Markdown rendering primitives."""

from __future__ import annotations

from typing import Any


def escape_table_cell(value: Any) -> str:
    text = "-" if value is None or value == "" else str(value)
    if text == "-":
        return text
    return text.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>").replace("|", "\\|")
