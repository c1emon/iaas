"""One filter-rule port selector, shared by admission and provider conversion."""
import re
from typing import Any, NoReturn

from iaas.common.errors import ValidationError
from .aliases import ALIAS_NAME


def rule_port(value: Any, path: str) -> str:
    def reject(reason: str) -> NoReturn:
        raise ValidationError(f"opnsense validation failed: {path}: {reason}")

    if isinstance(value, list):
        if len(value) != 1:
            reject("requires one port or continuous range; multiple ports require an explicit port alias")
        value = value[0]
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not value:
        reject("must be a port, continuous range, or port alias")
    if ',' in value:
        reject("comma-separated ports are forbidden; use an explicit port alias")
    if re.fullmatch(r"[0-9]+", value):
        if not 1 <= int(value) <= 65535:
            reject("must be within 1..65535")
    elif re.fullmatch(r"[0-9]+-[0-9]+", value):
        start, end = map(int, value.split('-'))
        if not 1 <= start <= end <= 65535:
            reject("port range must be within 1..65535 and ascending")
    elif not ALIAS_NAME.fullmatch(value):
        reject("invalid port/range syntax; use a port, ascending range, or port alias")
    return value
