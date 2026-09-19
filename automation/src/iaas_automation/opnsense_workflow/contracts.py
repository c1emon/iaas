"""Versioned workflow documents; standard resource declarations stay authoritative."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from typing import AbstractSet, Any

from iaas_automation.common.errors import require
from iaas_automation.common.io import write_text
from iaas_automation.opnsense_validation import TOP_LEVEL, VALIDATORS, validate_documents
from iaas_automation.opnsense_validation.aliases import ALIAS_NAME
from iaas_automation.opnsense_validation.interface_groups import GROUP_NAME

REQUEST_VERSION = 1
CANDIDATE_VERSION = 2
RESULT_VERSION = 2
RECOVERY_VERSION = 2
RESOURCES = tuple(TOP_LEVEL)
PROVIDER = "oxlorg.opnsense@1423500c29f88da9ba8147a23fc64006cf464159"


def shape(value: Any, required: set[str], optional: AbstractSet[str] = frozenset()) -> None:
    require(isinstance(value, dict), "workflow document must be a mapping")
    require(required <= value.keys() and not value.keys() - required - optional,
            "workflow document has missing or unknown fields")


def identity(resource: str, record: dict) -> list[str]:
    require(resource in RESOURCES, "unsupported workflow resource")
    if resource == "filter-rules":
        return [f"iaas:opnsense:filter:{record['scope']}:{record['slug']}"]
    return list(VALIDATORS[resource](record, resource))


def key(resource: str, value: list[str]) -> str:
    return json.dumps([resource, *value], separators=(",", ":"))


def selectors(value: Any, *, allow_all: bool = True) -> dict:
    require(isinstance(value, dict) and not set(value) - set(RESOURCES), "invalid resource selection")
    for resource, entries in value.items():
        if allow_all and entries == "all":
            continue
        require(isinstance(entries, list), "selection must be all or an explicit identity list")
        seen = set()
        size = 2 if resource in {"gateways", "vips"} else 1
        for entry in entries:
            require(isinstance(entry, list) and len(entry) == size
                    and all(isinstance(part, str) and part and not any(ord(c) < 32 for c in part) for part in entry),
                    "invalid stable resource identity")
            if resource in {'aliases', 'interface-groups'}:
                require(bool((ALIAS_NAME if resource == 'aliases' else GROUP_NAME).fullmatch(entry[0])),
                        'invalid stable resource identity')
            elif resource in {'filter-rules', 'dnat', 'one-to-one-nat'}:
                kind = 'filter' if resource == 'filter-rules' else resource
                require(bool(re.fullmatch(r'iaas:opnsense:' + kind + r':[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*', entry[0])),
                        'invalid managed rule identity')
            else:
                try:
                    if resource == 'vips':
                        require('/' in entry[0] and bool(re.fullmatch('[a-z][a-z0-9_]*', entry[1])), 'invalid VIP identity')
                        ipaddress.ip_interface(entry[0])
                    else:
                        require(bool(re.fullmatch('[A-Za-z0-9_][A-Za-z0-9_.-]*', entry[0])), 'invalid gateway identity')
                        ipaddress.ip_address(entry[1])
                except ValueError:
                    require(False, 'invalid stable resource address')
            marker = key(resource, entry)
            require(marker not in seen, "duplicate selected identity")
            seen.add(marker)
    return value


def request(value: Any) -> dict:
    shape(value, {"schema_version", "selection"}, {"managed", "adopt", "activation_recovery"})
    require(type(value['schema_version']) is int and value['schema_version'] == REQUEST_VERSION,
            "unsupported workflow request version")
    selectors(value['selection'])
    for field in ('managed', 'adopt', 'activation_recovery'):
        selectors(value.get(field, {}), allow_all=False)
    return deepcopy(value)


def selected_records(documents: dict, selection: dict) -> list[dict]:
    validate_documents(documents)
    selected = []
    for resource, entries in selection.items():
        require(resource in documents, "selected resource needs an explicit declaration file")
        records = documents[resource][TOP_LEVEL[resource]]
        available = {key(resource, identity(resource, row)): row for row in records}
        wanted = list(available) if entries == 'all' else [key(resource, entry) for entry in entries]
        require(set(wanted) <= available.keys(), "selected identity is not declared")
        selected.extend({'resource': resource, 'identity': identity(resource, available[item]),
                         'desired': deepcopy(available[item])} for item in wanted)
    return selected


def selection_keys(value: dict) -> set[str]:
    return {key(resource, ident) for resource, entries in value.items() for ident in entries}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, document: dict) -> str:
    data = json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + '\n'
    write_text(path, data, secure=True)
    return digest(data.encode())


def validate_coverage(selected: list[dict], supplied: Any) -> list[str]:
    from .planning import coverage
    require(isinstance(supplied, list)
            and all(isinstance(name, str) and name in RESOURCES for name in supplied)
            and len(supplied) == len(set(supplied))
            and set(coverage(selected)) <= set(supplied),
            'candidate coverage does not contain required supported reads')
    return supplied


def load_candidate(path: Path, reviewed: str | None = None) -> tuple[dict, str]:
    data = path.read_bytes()
    actual_digest = digest(data)
    if reviewed is not None:
        require(isinstance(reviewed, str) and re.fullmatch('[0-9a-f]{64}', reviewed)
                and actual_digest == reviewed, "reviewed candidate digest mismatch")
    value = json.loads(data)
    require(isinstance(value, dict) and type(value.get('schema_version')) is int
            and value['schema_version'] == CANDIDATE_VERSION,
            'incompatible workflow candidate; re-plan with this runtime')
    shape(value, {'schema_version', 'kind', 'target', 'runtime', 'provider', 'source', 'request',
                  'documents', 'selected', 'coverage', 'before', 'differences', 'stages', 'admission'})
    require(type(value['schema_version']) is int and value['schema_version'] == CANDIDATE_VERSION and value['kind'] == 'opnsense-candidate'
            and value['provider'] == PROVIDER, "incompatible workflow candidate; re-plan with this runtime")
    req = request(value['request'])
    expected = selected_records(value['documents'], req['selection'])
    require(value['selected'] == expected, "candidate selection does not match its declarations")
    validate_coverage(expected, value['coverage'])
    chosen_by_key = {key(item['resource'], item['identity']): item for item in expected}
    chosen = {key(item['resource'], item['identity']) for item in expected}
    for field in ('managed', 'adopt', 'activation_recovery'):
        require(selection_keys(req.get(field, {})) <= chosen,
                f'{field} selection must be a subset of execution')

    before = value['before']
    require(isinstance(before, dict), "malformed candidate before-state")
    require(all(isinstance(marker, str) for marker in before), "malformed candidate before-state")
    for marker in chosen:
        require(marker in before, "candidate before-state is missing selected identity")
    for marker, state in before.items():
        if state is None:
            continue
        require(isinstance(state, dict) and state.get('resource') in RESOURCES
                and isinstance(state.get('identity'), list)
                and isinstance(state.get('configuration'), (dict, type(None)))
                and state.get('recovery') in {'expressible', 'manual_required'},
                "malformed candidate before-state")

    differences = value['differences']
    require(isinstance(differences, list), "malformed candidate differences")
    difference_by_key = {}
    for difference in differences:
        shape(difference, {'resource', 'identity', 'action', 'before', 'after', 'adopted', 'recovery'})
        resource = difference['resource']
        identity_value = difference['identity']
        require(resource in RESOURCES and isinstance(identity_value, list),
                "malformed candidate difference identity")
        selectors({resource: [identity_value]}, allow_all=False)
        marker = key(resource, identity_value)
        require(marker in chosen and marker not in difference_by_key,
                "candidate differences must match selected identities exactly")
        require(difference['action'] in {'create', 'update', 'delete', 'unchanged'},
                "malformed candidate difference action")
        require(type(difference['adopted']) is bool
                and difference['recovery'] in {'expressible', 'manual_required'},
                "malformed candidate difference metadata")
        difference_by_key[marker] = difference
    require(set(difference_by_key) == chosen,
            "candidate differences must match selected identities exactly")

    # Recompute only the captured before/selected semantic comparison.  This is
    # an admission check, not a new plan: stage ordering remains the executor's
    # responsibility at each actual boundary.
    from .planning import semantic
    managed = selection_keys(req.get('managed', {}))
    adopted = selection_keys(req.get('adopt', {}))
    activation_recovery = selection_keys(req.get('activation_recovery', {}))
    changed = set()
    for marker, item in chosen_by_key.items():
        old = before[marker]
        old_configuration = old.get('configuration') if old else None
        require(old is None or old_configuration is not None,
                "selected native configuration is unsupported")
        desired = item['desired']
        if old is not None:
            require(marker in managed | adopted,
                    "existing identity requires explicit managed or adoption selection")
        if desired['state'] == 'absent':
            action = 'delete' if old else 'unchanged'
        elif old is None:
            action = 'create'
        else:
            actual = old_configuration if isinstance(old_configuration, dict) else {}
            require(isinstance(old_configuration, dict),
                    "selected native configuration is unsupported")
            if item['resource'] == 'aliases':
                require(actual['type'] == desired['type'],
                        'alias type changes require an explicit migration')
            action = ('unchanged' if semantic(item['resource'], actual) ==
                      semantic(item['resource'], desired) else 'update')
        expected_difference = difference_by_key[marker]
        require(expected_difference['action'] == action
                and expected_difference['before'] == old_configuration
                and expected_difference['after'] == (desired if desired['state'] == 'present' else None)
                and expected_difference['adopted'] is (marker in adopted)
                and expected_difference['recovery'] == (old.get('recovery', 'manual_required') if old else 'expressible'),
                "candidate differences do not match captured before-state")
        if action != 'unchanged':
            changed.add(marker)

    stages = value['stages']
    require(isinstance(stages, list), "malformed candidate stages")
    staged = set()
    for stage in stages:
        shape(stage, {'resource', 'mode', 'identities', 'confirmation', 'content_actions'})
        from .confirmation import content_actions, validate_wait
        confirmation = stage['confirmation']
        shape(confirmation, {'rule', 'required_evidence', 'supplementary_checks', 'capability',
                             'basis', 'gaps', 'wait', 'content_actions'})
        expected_actions = content_actions(stage, differences)
        require(stage['content_actions'] == confirmation['content_actions'] == expected_actions
                and validate_wait(confirmation['wait']) == confirmation['wait']
                and confirmation['rule'] == 'opnsense-native-' + stage['resource'] + '-v2'
                and confirmation['required_evidence'] == ['activation_completion'] + (
                    ['source_processing', 'content_loading'] if expected_actions else [])
                and confirmation['supplementary_checks'] == ['current_active_state']
                and confirmation['capability'] in {'available', 'unsupported', 'unknown'}
                and isinstance(confirmation['gaps'], list)
                and (confirmation['capability'] == 'available') == (not confirmation['gaps']),
                'invalid candidate stage confirmation contract')
        require(stage['mode'] in {'save', 'activation_recovery'} and bool(stage['identities']), 'invalid candidate stage')
        selectors({stage['resource']: stage['identities']}, allow_all=False)
        entries = {key(stage['resource'], ident) for ident in stage['identities']}
        require(entries <= chosen and not entries & staged, 'candidate stage exceeds or repeats selected scope')
        expected_mode = {marker: 'save' for marker in changed}
        expected_mode.update({marker: 'activation_recovery' for marker in activation_recovery - changed})
        require(all(expected_mode.get(marker) == stage['mode'] for marker in entries),
                'candidate stage mode does not match captured differences')
        if stage['mode'] == 'activation_recovery':
            require(entries <= activation_recovery, 'activation recovery must be explicit')
        staged.update(entries)
    expected_stages = changed | activation_recovery
    require(staged == expected_stages, 'candidate stages do not match captured differences')
    from .confirmation import disposition
    require(value['admission'] == disposition(stages), 'invalid candidate admission summary')
    return value, actual_digest
