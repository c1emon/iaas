"""Value-free field checks and file-aware offline configuration errors."""

from collections.abc import Callable, Mapping
import re
from typing import Any

from .errors import ValidationError, require


class InputValidationError(ValidationError):
    """Public diagnostic constructed only from local validation and scrubbed inputs."""


def require_fields(value: Mapping[str, Any], allowed: set[str], label: str,
                   *, required: set[str] | None = None) -> None:
    unknown = set(value) - allowed
    missing = (required or set()) - set(value)
    def safe(fields):
        return ", ".join(sorted(
            key if isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", key)
            else "<invalid-field>" for key in fields)[:8])
    require(not unknown, f"{label} contains unsupported fields: {safe(unknown)}")
    require(not missing, f"{label} missing fields: {safe(missing)}")


def checked_input(selected: Any, name: str, document: Any,
                  validator: Callable[[Any], Any]) -> Any:
    """Attach the selected logical file without exposing source values."""
    try:
        return validator(document)
    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, ValidationError) else "input: invalid structure or unsupported value"
        values: set[str] = set()

        def collect(value: Any) -> None:
            if isinstance(value, str) and value:
                values.add(value)
            elif isinstance(value, Mapping):
                for key, item in value.items():
                    if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", key) is None:
                        values.add(str(key))
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(document)
        for value in sorted(values, key=len, reverse=True):
            reason = re.sub(r"(?<![A-Za-z0-9_.-])" + re.escape(value) + r"(?![A-Za-z0-9_.-])", "<value>", reason)
        reason = " ".join(reason.split())[:1024]
        origin = getattr(selected, "input_paths", {}).get(name, name)
        raise InputValidationError(f"{origin}: {reason}") from None
