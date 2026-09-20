"""Opt-in representation conversion, separate from strict declaration admission."""
from typing import Any

from pydantic import TypeAdapter, ValidationError as PydanticValidationError

from .errors import Diagnostic

_BOOLEAN = TypeAdapter(bool)


class ConversionError(ValueError):
    """Controlled failure without Pydantic inputs, messages or dynamic paths."""

    def __init__(self, code: str = "invalid_value") -> None:
        self.diagnostic = Diagnostic("conversion", code, field_path=("value",))
        self.code = code
        super().__init__(code)


def convert_bool(value: Any) -> bool:
    try:
        return _BOOLEAN.validate_python(value)
    except PydanticValidationError:
        raise ConversionError("invalid_boolean") from None


def optional_bool(value: Any) -> bool | None:
    """Observation callers may explicitly represent a failed conversion as unknown."""
    try:
        return convert_bool(value)
    except ConversionError:
        return None
