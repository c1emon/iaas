"""Validate actual Ansible values before credentials and provider writes."""
from pathlib import Path
import sys

_SOURCE = str(Path(__file__).resolve().parents[2] / 'src')
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from iaas_automation.opnsense_validation import TOP_LEVEL, validate_document
from iaas_automation.opnsense_validation.lifecycle import resource_arguments, resource_preflight


def _plain(value):
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


def opnsense_resource_admission(records, resource):
    validate_document(resource, {TOP_LEVEL[resource]: _plain(records)})
    return True


def opnsense_resource_arguments(record, resource):
    return resource_arguments(_plain(record), resource)


def opnsense_resource_preflight(records, existing, resource):
    return resource_preflight(_plain(records), _plain(existing), resource)


class FilterModule:
    def filters(self):
        return {'opnsense_resource_admission': opnsense_resource_admission,
                'opnsense_resource_arguments': opnsense_resource_arguments,
                'opnsense_resource_preflight': opnsense_resource_preflight}
