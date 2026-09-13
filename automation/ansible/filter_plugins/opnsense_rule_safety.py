"""Reuse domain rule admission after Ansible has loaded the selected document."""

from pathlib import Path
import sys

_AUTOMATION_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_SRC))

from iaas_automation.opnsense_validation import validate_document


def _plain(value):
    """Strip engine metadata without coercing strings or bools to numbers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str):
        return str(value)
    if isinstance(value, dict):
        return {_plain(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def opnsense_rule_safety(rules, context=None):
    document = {"opnsense_filter_rules": rules}
    if context is not None:
        document["opnsense_filter_rule_context"] = context
    validate_document("filter-rules", _plain(document))
    return True


class FilterModule:
    def filters(self):
        return {"opnsense_rule_safety": opnsense_rule_safety}
