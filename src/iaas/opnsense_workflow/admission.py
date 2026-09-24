"""Classification admission and reference evidence for reviewed observations."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from iaas.common.errors import require
from .classification import SUPPORTED_BASIS


def validate_classification(value: Any) -> dict:
    require(isinstance(value, dict)
            and {'origin', 'management', 'basis'} <= value.keys(),
            'missing resource classification; re-read and re-plan with this runtime')
    require(value['origin'] in ('user_config', 'system_builtin', 'derived', 'unknown')
            and value['management'] in ('independent', 'via_source', 'read_only', 'unknown')
            and isinstance(value['basis'], list)
            and all(isinstance(item, str) and item in SUPPORTED_BASIS for item in value['basis']),
            'invalid resource classification; re-read and re-plan')
    require(value['management'] == 'unknown' or bool(value['basis']),
            'resource management evidence is missing')
    return value


def require_independent(obj: dict) -> None:
    classification = validate_classification(obj.get('classification'))
    management = classification['management']
    reason = {
        'via_source': 'selected resource must be managed through its source configuration',
        'read_only': 'selected resource is read-only and cannot be independently managed',
        'unknown': 'selected resource management capability is unknown or only partially supported',
    }
    if management == 'via_source' and classification.get('source'):
        reason['via_source'] += f" ({classification['source']})"
    require(management == 'independent', reason.get(management, 'resource is not independently manageable'))


def management_semantics(value: Any) -> dict:
    classification = validate_classification(value)
    # A corrected origin label is not a change in permission. Evidence and
    # source association, however, are part of the reviewed admission boundary.
    return {'management': classification['management'],
            'basis': sorted(classification['basis']),
            'source': deepcopy(classification.get('source'))}


def reference_support(obj: dict) -> dict | None:
    support = obj.get('reference_support')
    if support is None:
        return None
    classification = validate_classification(obj.get('classification'))
    require(classification['origin'] in {'system_builtin', 'derived'},
            'system reference support requires evidenced system origin')
    require(isinstance(support, dict)
            and isinstance(support.get('label'), str)
            and isinstance(support.get('roles'), list) and bool(support['roles'])
            and all(role in ('address', 'port', 'interface-group') for role in support['roles'])
            and isinstance(support.get('basis'), list) and bool(support['basis'])
            and all(isinstance(item, str) and item in SUPPORTED_BASIS for item in support['basis'])
            and type(support.get('dependencies_complete')) is bool,
            'system reference evidence is incomplete')
    resource = obj.get('resource')
    require(resource in {'aliases', 'interface-groups'}
            and obj.get('identity') and support['label'] == resource + ':' + obj['identity'][0],
            'system reference identity is inconsistent')
    allowed_roles = {'interface-group'} if resource == 'interface-groups' else {'address', 'port'}
    require(set(support['roles']) <= allowed_roles, 'system reference role is incompatible')
    require('address' not in support['roles'] or support.get('ip_protocol') in ('inet', 'inet6', 'inet46'),
            'system reference address family is unknown')
    return support


def reference_label(obj: dict) -> str | None:
    support = reference_support(obj)
    return support['label'] if support else obj.get('label')


def require_reference(obj: dict, role: str, ip_protocol: str | None = None) -> None:
    support = reference_support(obj)
    require(support is not None and support['dependencies_complete'] is True
            and role in support['roles'], 'required dependency reference evidence is missing or incompatible')
    if role == 'address' and ip_protocol:
        family = cast(dict, support)['ip_protocol']
        require(family == 'inet46' or family == ip_protocol,
                'effective alias reference has incompatible address family')


def require_configuration_observation(observation: dict) -> None:
    require(observation.get('observation_scope') == 'configuration',
            'execution requires complete configuration observations, not a display view')
