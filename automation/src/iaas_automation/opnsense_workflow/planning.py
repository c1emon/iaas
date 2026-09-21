"""Semantic differences and bounded dependency ordering over effective live state."""
from __future__ import annotations

from copy import deepcopy
import ipaddress
from typing import Any, cast

from iaas_automation.common.errors import ValidationError, require
from .contracts import PROVIDER, CANDIDATE_VERSION, identity, key, request, selected_records, selection_keys
from .admission import (reference_label, reference_support, require_configuration_observation,
                        require_independent, require_reference, validate_classification)

CONSUMERS = {'filter-rules', 'dnat', 'one-to-one-nat'}


def semantic(resource: str, record: dict | None) -> dict | None:
    if record is None:
        return None
    from .conversion import normalize_standard_record
    return normalize_standard_record(resource, record)


def coverage(selected: list[dict]) -> list[str]:
    resources = {item['resource'] for item in selected}
    if resources & CONSUMERS:
        resources |= {'aliases', 'gateways', 'interface-groups'}
    if resources & {'aliases', 'interface-groups'}:
        resources |= CONSUMERS | {'aliases', 'gateways', 'interface-groups'}
    if 'gateways' in resources:
        resources |= {'filter-rules', 'aliases', 'interface-groups'}
    return sorted(resources)


def objects(observations: dict) -> dict[str, dict]:
    result = {}
    for resource, observation in observations.items():
        require_configuration_observation(observation)
        require(observation.get('status') == 'complete', 'required configuration observation is unknown or incomplete')
        for obj in observation['objects']:
            validate_classification(obj.get('classification'))
            marker = key(resource, obj['identity'])
            require(marker not in result, 'ambiguous live identity')
            result[marker] = {**deepcopy(obj), 'resource': resource}
    return result


def label(resource: str, row: dict) -> str | None:
    if resource in {'aliases', 'interface-groups', 'gateways'}:
        return resource + ':' + row['name']
    return None


def references(resource: str, row: dict) -> set[str]:
    result: set[str] = set()
    if resource == 'aliases' and row.get('type') == 'networkgroup':
        return {'aliases:' + name for name in row['content']}
    if resource == 'interface-groups':
        return {'interface-groups:' + member for member in row.get('members', [])}
    if resource in {'gateways', 'vips'}:
        return {'interface-groups:' + row['interface']}
    if resource not in CONSUMERS:
        return result
    for field in ('source_net', 'destination_net', 'source_port', 'destination_port', 'target', 'external', 'local_port'):
        values = row.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            value = str(value)
            if not value or value in {'any', '(self)'} or value.isdecimal():
                continue
            try:
                ipaddress.ip_network(value, strict=False)
                continue
            except ValueError:
                pass
            if '-' in value and all(part.isdecimal() for part in value.split('-')):
                continue
            # Interface tokens are resolved against the observed interfaces below.
            result.add('aliases:' + value)
    if resource == 'filter-rules' and row.get('gateway') not in {None, '', 'default', '*'}:
        result.add('gateways:' + row['gateway'])
    interfaces = row.get('interface', [])
    if isinstance(interfaces, str):
        interfaces = [interfaces]
    result.update('interface-groups:' + item for item in interfaces)
    return result


def object_references(obj: dict) -> set[str]:
    config = obj.get('configuration')
    if config is not None:
        return references(obj['resource'], config)
    refs = obj.get('references')
    require(isinstance(refs, list), 'native reference coverage unavailable')
    return set(cast(list[str], refs))


def relevant(observations: dict, selected: list[dict]) -> dict[str, dict | None]:
    live = objects(observations)
    wanted = {key(item['resource'], item['identity']) for item in selected}
    labels = {label(item['resource'], item['desired']) for item in selected
              if item['desired'].get('state') != 'absent' or item['resource'] in {'aliases', 'interface-groups', 'gateways'}} - {None}
    needed = set().union(*(references(item['resource'], item['desired']) for item in selected)) if selected else set()
    changed = True
    while changed:
        previous = (len(wanted), len(needed))
        for marker, obj in live.items():
            config = obj.get('configuration')
            obj_label = label(obj['resource'], config) if config else reference_label(obj)
            refs = object_references(obj)
            if marker in wanted or obj_label in needed or refs & labels:
                wanted.add(marker)
                needed.update(refs)
        changed = previous != (len(wanted), len(needed))
    return {marker: live.get(marker) for marker in sorted(wanted)}


def interfaces_from(observations: dict) -> set[str]:
    # Reader exposes native interface choices from the fixed provider model.
    return set().union(*(set(value.get('interfaces', [])) for value in observations.values())) if observations else set()


def valid_state(state: dict[str, dict | None], interfaces: set[str]) -> None:
    labels = {}
    for marker, obj in state.items():
        if obj is None:
            continue
        config = obj.get('configuration')
        obj_label = label(obj['resource'], config) if config else reference_label(obj)
        if obj_label:
            require(obj_label not in labels, 'ambiguous dependency identity')
            labels[obj_label] = marker
    graph = {}
    for marker, obj in state.items():
        if obj is None:
            continue
        if obj.get('configuration') is None and reference_support(obj) is not None:
            require(obj['reference_support']['dependencies_complete'],
                    'system dependency coverage is incomplete')
        refs = object_references(obj)
        dependencies = set()
        for ref in refs:
            category, name = ref.split(':', 1)
            if category in {'aliases', 'interface-groups'} and name in interfaces and ref not in labels:
                continue
            if category == 'aliases' and name.endswith('ip') and name[:-2] in interfaces and ref not in labels:
                # Native NetworkAliasField exposes <interface>ip for addresses.
                continue
            require(ref in labels, 'missing dependency or unselected reference transition')
            dependency = state[labels[ref]]
            config = dependency.get('configuration') if dependency else None
            if config is None:
                # Only supported rule consumers may use the bounded native
                # reference description; it is not a reconstructed declaration.
                require(obj['resource'] in CONSUMERS and dependency is not None,
                        'required dependency configuration is unknown')
                role = 'interface-group' if category == 'interface-groups' else 'address'
                if category == 'aliases':
                    # Address/port compatibility is checked per field below.
                    support = reference_support(cast(dict, dependency))
                    require(support is not None and support['dependencies_complete'],
                            'required dependency configuration is unknown')
                else:
                    require_reference(cast(dict, dependency), role)
            if category == 'aliases' and obj['resource'] == 'aliases':
                require(config is not None and config['type'] in {'host', 'network', 'urltable', 'networkgroup'},
                        'incompatible alias dependency')
            dependencies.add(labels[ref])
        row = obj.get('configuration')
        if row is not None and obj['resource'] in CONSUMERS:
            for field in ('source_net', 'destination_net', 'target', 'external',
                          'source_port', 'destination_port', 'local_port'):
                values = row.get(field, [])
                if not isinstance(values, list):
                    values = [values]
                for token in values:
                    linked = labels.get('aliases:' + str(token))
                    if linked is not None:
                        dependency = state[linked]
                        config = dependency.get('configuration') if dependency else None
                        if config is None:
                            require_reference(cast(dict, dependency),
                                              'port' if field.endswith('port') else 'address',
                                              row.get('ip_protocol'))
                        else:
                            require((config['type'] == 'port') == field.endswith('port'),
                                    'effective alias reference has incompatible address/port type')
        graph[marker] = dependencies
    pending = deepcopy(graph)
    while pending:
        ready = {marker for marker, deps in pending.items() if not deps & pending.keys()}
        require(bool(ready), 'cyclic resource dependency')
        for marker in ready:
            del pending[marker]


def overlay(state: dict, item: dict) -> dict:
    updated = deepcopy(state)
    marker = key(item['resource'], item['identity'])
    updated[marker] = (None if item['desired']['state'] == 'absent' else
                       {**(state.get(marker) or {}), 'resource': item['resource'], 'identity': item['identity'],
                        'configuration': semantic(item['resource'], item['desired']), 'recovery': 'expressible'})
    if state.get(marker) is None and updated[marker] is not None:
        updated[marker]['creation_expected'] = True
    return updated


def stages_for(selected: list[dict], before: dict, differences: list[dict], interfaces: set[str], recovery: set[str]) -> list[dict]:
    effective = deepcopy(before)
    for item in selected:
        effective = overlay(effective, item)
    valid_state(effective, interfaces)
    changed = {key(row['resource'], row['identity']) for row in differences if row['action'] != 'unchanged'}
    pending = [item for item in selected if key(item['resource'], item['identity']) in changed | recovery]
    state = deepcopy(before)
    stages = []
    while pending:
        admitted = None
        for item in pending:
            try:
                next_state = overlay(state, item)
                valid_state(next_state, interfaces)
            except ValidationError:
                continue
            admitted = item
            break
        require(admitted is not None, 'cannot safely order selected writes; split the caller migration or select missing transitions')
        admitted = cast(dict, admitted)
        marker = key(admitted['resource'], admitted['identity'])
        mode = 'save' if marker in changed else 'activation_recovery'
        # Consecutive independent objects of one resource share one activation.
        if stages and stages[-1]['resource'] == admitted['resource'] and stages[-1]['mode'] == mode:
            stages[-1]['identities'].append(admitted['identity'])
        else:
            stages.append({'resource': admitted['resource'], 'mode': mode, 'identities': [admitted['identity']]})
        state = overlay(state, admitted)
        pending.remove(admitted)
    return stages


def plan(documents: dict, req: dict, observations: dict, target: dict, runtime: dict, source: dict) -> dict:
    req = request(req)
    selected = selected_records(documents, req['selection'])
    before = relevant(observations, selected)
    chosen = {key(item['resource'], item['identity']) for item in selected}
    managed, adopted = selection_keys(req.get('managed', {})), selection_keys(req.get('adopt', {}))
    recovery = selection_keys(req.get('activation_recovery', {}))
    require(managed | adopted | recovery <= chosen, 'management/adoption/recovery selection must be a subset of execution')
    differences = []
    for item in selected:
        marker = key(item['resource'], item['identity'])
        old = before[marker]
        if old is not None:
            require_independent(old)
        if marker in recovery:
            require(old is not None,
                    'activation recovery requires an existing observed identity')
        require(old is None or old.get('configuration') is not None, 'selected native configuration is unsupported')
        desired = item['desired']
        actual = old['configuration'] if old else None
        if old is not None:
            require(marker in managed | adopted, 'existing identity requires explicit managed or adoption selection')
        if desired['state'] == 'absent':
            action = 'delete' if old else 'unchanged'
        elif old is None:
            action = 'create'
        else:
            if item['resource'] == 'aliases':
                require(cast(dict, actual)['type'] == desired['type'], 'alias type changes require an explicit migration')
            action = 'unchanged' if semantic(item['resource'], actual) == semantic(item['resource'], desired) else 'update'
        differences.append({'resource': item['resource'], 'identity': item['identity'], 'action': action,
                            'before': actual, 'after': desired if desired['state'] == 'present' else None,
                            'adopted': marker in adopted,
                            'recovery': old.get('recovery', 'manual_required') if old else 'expressible'})
    stages = stages_for(selected, before, differences, interfaces_from(observations), recovery)
    from .confirmation import bind_stages, disposition
    stages = bind_stages(stages, differences, observations)
    return {'schema_version': CANDIDATE_VERSION, 'kind': 'opnsense-candidate', 'provider': PROVIDER,
            'target': target, 'runtime': runtime, 'source': source, 'request': req,
            'documents': deepcopy(documents), 'selected': selected, 'coverage': sorted(observations),
            'before': before, 'differences': differences, 'stages': stages, 'admission': disposition(stages)}
