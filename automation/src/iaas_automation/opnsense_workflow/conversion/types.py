"""Reusable wire types; special empty and member-map policies stay field-scoped."""
from copy import deepcopy
import re
from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, StrictStr, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from iaas_automation.common.conversion import ConversionError


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("boolean_is_not_integer")
    return value


INTEGER: TypeAdapter[int] = TypeAdapter(Annotated[int, BeforeValidator(_reject_bool)])
TEXT: TypeAdapter[str] = TypeAdapter(StrictStr)
OBJECT_MAP: TypeAdapter[dict[object, object]] = TypeAdapter(dict[object, object])
OBJECT_LIST: TypeAdapter[list[object]] = TypeAdapter(list[object])


class _Selection(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    selected: bool


class _ListSelection(_Selection):
    identifier: StrictStr | StrictInt = Field(validation_alias=AliasChoices("key", "value"))


def selected(value: Any, *, multiple: bool = False) -> Any:
    identifiers: list[str | int] = []
    original: Any = value
    try:
        if isinstance(value, dict):
            mapping = OBJECT_MAP.validate_python(value)
            for key, option in mapping.items():
                if _Selection.model_validate(option).selected:
                    # The dict key is the identifier, never its display label.
                    identifiers.append(TEXT.validate_python(key))
        elif isinstance(value, list):
            options = OBJECT_LIST.validate_python(value)
            if any(isinstance(item, dict) for item in options):
                for option in options:
                    entry = _ListSelection.model_validate(option)
                    if entry.selected:
                        identifiers.append(entry.identifier)
            else:
                return deepcopy(original)
        else:
            return deepcopy(original)
    except PydanticValidationError:
        raise ConversionError("malformed_native_selector") from None
    if len(set(identifiers)) != len(identifiers) or (not multiple and len(identifiers) > 1):
        raise ConversionError("malformed_native_selector")
    return identifiers if multiple else (identifiers[0] if identifiers else "")


def as_list(value: Any) -> Any:
    if isinstance(value, dict):
        mapping = OBJECT_MAP.validate_python(value)
        return [key for key in mapping if key != ""]
    if isinstance(value, str):
        return [item for item in re.split(r"[,\n]", value) if item != ""]
    return deepcopy(value)
