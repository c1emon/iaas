"""Validate actual Ansible values before credentials and provider writes."""
import json
from pathlib import Path
import sys
from typing import Any

_SOURCE = str(Path(__file__).resolve().parents[2] / 'src')
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from iaas_automation.opnsense_validation import TOP_LEVEL, validate_document
from iaas_automation.opnsense_validation.lifecycle import resource_arguments, resource_preflight


_PROVIDER_COLLECTION = 'oxlorg.opnsense'
_PROVIDER_VERSION = '26.1.11'
_PROVIDER_MODULES = {
    'dnat': 'nat_destination',
    'one-to-one-nat': 'nat_one_to_one',
    'interface-groups': 'rule_interface_group',
}


def _plain(value: Any) -> Any:
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


def opnsense_resource_admission(records, resource, context=None):
    document = {TOP_LEVEL[resource]: _plain(records)}
    if context is not None:
        document['opnsense_filter_rule_context'] = _plain(context)
    validate_document(resource, document)
    return True


def opnsense_resource_arguments(record, resource):
    return resource_arguments(_plain(record), resource)


def opnsense_resource_preflight(records, existing, resource):
    return resource_preflight(_plain(records), _plain(existing), resource)


def opnsense_provider_readiness(resource):
    """Verify the loaded Collection version and selected provider module locally."""
    import importlib.util
    from ansible.utils.collection_loader import AnsibleCollectionRef

    module_name = _PROVIDER_MODULES.get(resource)
    if module_name is None:
        raise ValueError(f'unsupported OPNsense provider resource: {resource}')
    module_paths: dict[str, str] = {}
    for candidate in dict.fromkeys((module_name, 'nat_destination')):
        try:
            ref = AnsibleCollectionRef.from_fqcr(
                f'{_PROVIDER_COLLECTION}.{candidate}', 'modules')
            module_spec = importlib.util.find_spec(
                f'{ref.n_python_package_name}.{ref.resource}')
            candidate_path = module_spec.origin if module_spec is not None else None
        except (ImportError, ModuleNotFoundError, ValueError):
            candidate_path = None
        if (isinstance(candidate_path, str) and candidate_path not in {'built-in', 'frozen'}
                and Path(candidate_path).is_file()):
            module_paths[candidate] = candidate_path
    if module_name not in module_paths:
        raise ValueError(
            f'OPNsense provider readiness failed for {resource}: '
            f'{_PROVIDER_COLLECTION}.{module_name} is unavailable; '
            'reinstall the locked collection from automation/ansible/requirements.yml'
        )
    if 'nat_destination' not in module_paths:
        raise ValueError(
            f'OPNsense provider readiness failed for {resource}: '
            f'{_PROVIDER_COLLECTION}.nat_destination is unavailable; '
            'reinstall the locked collection from automation/ansible/requirements.yml'
        )

    manifest_path = next(
        (parent / 'MANIFEST.json' for parent in Path(module_paths[module_name]).parents
         if (parent / 'MANIFEST.json').is_file()),
        None,
    )
    if manifest_path is None:
        raise ValueError(
            f'OPNsense provider readiness failed for {resource}: '
            f'{_PROVIDER_COLLECTION}.{module_name} has no standard MANIFEST.json; '
            'reinstall the locked collection from automation/ansible/requirements.yml'
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        version = manifest['collection_info']['version']
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        version = None
    if version != _PROVIDER_VERSION:
        raise ValueError(
            f'OPNsense provider readiness failed for {resource}: '
            f'{_PROVIDER_COLLECTION} must be version {_PROVIDER_VERSION}; '
            f'found {version!r}; reinstall the locked collection from '
            'automation/ansible/requirements.yml'
        )
    return True


class FilterModule:
    def filters(self):
        return {'opnsense_resource_admission': opnsense_resource_admission,
                'opnsense_resource_arguments': opnsense_resource_arguments,
                'opnsense_resource_preflight': opnsense_resource_preflight,
                'opnsense_provider_readiness': opnsense_provider_readiness}
