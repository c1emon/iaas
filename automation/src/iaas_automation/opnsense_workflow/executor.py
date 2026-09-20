"""Reviewed execution, independent checks and explicit inverse candidates."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.opnsense_validation import TOP_LEVEL, validate_document
from .contracts import RECOVERY_VERSION, RESULT_VERSION, key, save, selected_records, selection_keys, selectors, shape, validate_coverage
from .planning import interfaces_from, objects, overlay, plan, relevant, semantic, valid_state


def fingerprint(state: dict) -> dict:
    """Compare configuration, identity and expressibility, excluding telemetry."""
    return {marker: None if obj is None else {
        'configuration': semantic(obj['resource'], obj['configuration']) if obj.get('configuration') else None,
        'references': obj.get('references') if obj.get('configuration') is None else None,
        'recovery': obj.get('recovery', 'manual_required'),
    } for marker, obj in state.items()}


def checked_live(candidate: dict, reader: Any, expected: dict) -> tuple[dict, dict]:
    required = validate_coverage(candidate['selected'], candidate['coverage'])
    observations = reader.read(required)
    current = relevant(observations, candidate['selected'])
    # Reference switches can shrink the current dependency closure. Keep every
    # previously observed identity under drift checks through this execution,
    # while relevant() still discovers new dependencies and reverse references.
    live = objects(observations)
    for marker in expected:
        current.setdefault(marker, live.get(marker))
    require(fingerprint(current) == fingerprint(expected), 'related configuration drift; review a new candidate')
    return observations, current


def activation_admission(reader: Any, candidate: dict, digest: str, execution_id: str, conclusion: dict) -> dict:
    observation = reader.pending_changes() if hasattr(reader, 'pending_changes') else {'status': 'unknown'}
    require(observation.get('status') != 'conflict', 'unrelated pending activation conflict')
    require(observation.get('status') in {'clear', 'unknown'}, 'pending activation observation failed')
    shape(conclusion, {'target', 'candidate_sha256', 'execution_id', 'checked_no_pending', 'serialized'})
    require(conclusion['target'] == candidate['target'] and conclusion['candidate_sha256'] == digest
            and conclusion['execution_id'] == execution_id and conclusion['checked_no_pending'] is True
            and conclusion['serialized'] is True, 'current execution requires a bound caller activation check')
    return {'automated': observation, 'caller': deepcopy(conclusion)}


def verify(candidate: dict, reader: Any, *, identities: set[str] | None = None) -> dict:
    observations = reader.read(sorted({item['resource'] for item in candidate['selected']}))
    results = []
    for item in candidate['selected']:
        marker = key(item['resource'], item['identity'])
        if identities is not None and marker not in identities:
            continue
        observation = observations.get(item['resource'], {})
        matches = [obj for obj in observation.get('objects', []) if obj['identity'] == item['identity']]
        config = 'unknown'
        if observation.get('status') == 'complete' and len(matches) <= 1:
            if item['desired']['state'] == 'absent':
                config = 'verified' if not matches else 'failed'
            elif not matches:
                config = 'failed'
            elif matches[0].get('configuration') is not None:
                config = ('verified' if semantic(item['resource'], matches[0]['configuration']) ==
                          semantic(item['resource'], item['desired']) else 'failed')
        active = {'status': 'not_attempted', 'reason': 'use_optional_inspect_tool'}
        results.append({'resource': item['resource'], 'identity': item['identity'],
                        'configuration': config, 'active': active})
    failed = any(item['configuration'] != 'verified' for item in results)
    return {'status': 'failed' if failed else 'fully_verified', 'objects': results,
            'scope': 'saved_configuration',
            'historical_actions': {'activation': 'not_provided', 'content_update': 'not_provided'},
            'business_acceptance': 'not_performed'}


def recovery_document(candidate: dict, digest: str, execution_id: str, current: dict) -> dict:
    selected = {key(item['resource'], item['identity']): item for item in candidate['selected']}
    affected = {key(stage['resource'], ident) for stage in candidate['stages'] for ident in stage['identities']}
    entries = []
    for marker in sorted(affected):
        item, old = selected[marker], current[marker]
        recoverable = old.get('recovery', 'manual_required') if old else 'expressible'
        if old and recoverable == 'expressible':
            try:
                validate_document(item['resource'], {TOP_LEVEL[item['resource']]: [old['configuration']]})
            except (ValueError, TypeError, KeyError):
                # Observing a live rule does not supply the declaration safety
                # context needed to recreate it. Preserve the value, but require review.
                recoverable = 'manual_required'
        entries.append({'resource': item['resource'], 'identity': item['identity'],
                        'before': old.get('configuration') if old else None,
                        'before_absent': old is None,
                        'recovery': recoverable,
                        'desired': deepcopy(item['desired']), 'attempted': False,
                        'after_status': 'unknown', 'after': None})
    return {'schema_version': RECOVERY_VERSION, 'kind': 'opnsense-recovery', 'target': candidate['target'],
            'runtime': candidate['runtime'], 'candidate_sha256': digest, 'execution_id': execution_id,
            'entries': entries, 'stages': []}


def readback(recovery: dict, candidate: dict, reader: Any) -> None:
    try:
        observations = reader.read(sorted({entry['resource'] for entry in recovery['entries']}))
    except Exception:
        observations = {}
    for entry in recovery['entries']:
        observation = observations.get(entry['resource'], {})
        matches = [obj for obj in observation.get('objects', []) if obj['identity'] == entry['identity']]
        entry.update(after_status='unknown', after=None)
        if observation.get('status') == 'complete' and len(matches) <= 1:
            if not matches:
                entry['after_status'] = 'confirmed'
            elif matches[0].get('configuration') is not None:
                entry.update(after_status='confirmed', after=matches[0]['configuration'])


def apply(candidate: dict, digest: str, reader: Any, writer: Any, execution_id: str,
          conclusion: dict, output: Path, *, check_mode: bool = False) -> dict:
    result = {'schema_version': RESULT_VERSION, 'kind': 'opnsense-result', 'operation': 'apply',
              'target': candidate['target'], 'runtime': candidate['runtime'], 'candidate_sha256': digest,
              'execution_id': execution_id, 'selected': [{'resource': item['resource'], 'identity': item['identity']}
                                                       for item in candidate['selected']],
              'status': 'running', 'stages': [], 'warnings': [], 'business_acceptance': 'not_performed',
              'recovery_file': str(output / 'recovery.json')}
    save(output / 'result.json', result)
    recovery = None
    try:
        observations, current = checked_live(candidate, reader, candidate['before'])
        from .confirmation import recheck
        recheck(candidate, observations)
        # Recheck declaration and effective state locally, without changing the fixed stages.
        selected_records(candidate['documents'], candidate['request']['selection'])
        effective = deepcopy(current)
        for item in candidate['selected']:
            effective = overlay(effective, item)
        valid_state(effective, interfaces_from(observations))
        if candidate['stages']:
            result['activation_admission'] = activation_admission(reader, candidate, digest, execution_id, conclusion)
        recovery = recovery_document(candidate, digest, execution_id, current)
        save(output / 'recovery.json', recovery)
        if check_mode:
            result.update(status='checked', configuration='not_attempted', activation='not_attempted')
            save(output / 'result.json', result)
            return result
        expected = current
        for stage in candidate['stages']:
            observations, _ = checked_live(candidate, reader, expected)
            recheck(candidate, observations)
            activation_admission(reader, candidate, digest, execution_id, conclusion)
            markers = {key(stage['resource'], ident) for ident in stage['identities']}
            items = [item for item in candidate['selected'] if key(item['resource'], item['identity']) in markers]
            stage_state = deepcopy(expected)
            for item in items:
                stage_state = overlay(stage_state, item)
            valid_state(stage_state, interfaces_from(observations))
            outcome = {**deepcopy(stage), 'attempted': True, 'save': 'not_attempted',
                       'activation': 'not_attempted', 'configuration': 'not_attempted', 'active': 'not_attempted',
                       'content_update': [{**action, 'status': 'not_attempted'} for action in stage['content_actions']]}
            result['stages'].append(outcome)
            recovery['stages'].append(outcome)
            for entry in recovery['entries']:
                if key(entry['resource'], entry['identity']) in markers:
                    entry.update(attempted=True, after_status='unknown', after=None)
            # Invalidate any old confirmed post-state durably BEFORE the next write.
            save(output / 'recovery.json', recovery)
            save(output / 'result.json', result)
            if stage['mode'] == 'save':
                outcome['save'] = 'unknown'
                saved = writer.save(stage['resource'], [item['desired'] for item in items])
                outcome['save'] = saved['status']
                require(saved['status'] in {'saved', 'unchanged'}, 'resource save failed or is unknown')
            else:
                outcome['save'] = 'unchanged'
            readback(recovery, candidate, reader)
            save(output / 'recovery.json', recovery)
            # Saved configuration is verified independently of activation.
            checks = verify(candidate, reader, identities=markers)
            outcome['configuration'] = ('verified' if all(row['configuration'] == 'verified' for row in checks['objects']) else 'failed')
            require(outcome['configuration'] == 'verified', 'saved configuration verification failed')
            checked_live(candidate, reader, stage_state)
            activation_admission(reader, candidate, digest, execution_id, conclusion)
            outcome['activation'] = 'unknown'
            from .confirmation import native_content_results, response_warnings
            outcome['warnings'] = response_warnings(stage['resource'])
            result['warnings'].extend(outcome['warnings'])
            for warning in outcome['warnings']:
                print(f"WARNING {warning['code']} [{warning['resource']}]: {warning['message']}",
                      file=sys.stderr, flush=True)
            save(output / 'result.json', result)
            activation = writer.activate(stage['resource'])
            outcome['activation'] = activation['status']
            outcome['activation_detail'] = activation
            outcome['activation_basis'] = 'native_response'
            outcome['content_update'] = native_content_results(stage, activation)
            checks = verify(candidate, reader, identities=markers)
            outcome['active'] = checks['objects']
            require(outcome['activation'] == 'confirmed', 'activation failed or unconfirmed; dependent stages stopped')
            require(all(row['status'] == 'provider_managed' for row in outcome['content_update']),
                    'native content processing reported failure; dependent stages stopped')
            require(checks['status'] != 'failed', 'post-activation verification failed')
            # Refresh only our selected post-state; unrelated drift is still compared at the next boundary.
            _, observed = checked_live(candidate, reader, stage_state)
            expected = observed
            readback(recovery, candidate, reader)
            save(output / 'recovery.json', recovery)
            save(output / 'result.json', result)
        result['verification'] = verify(candidate, reader)
        result['status'] = result['verification']['status']
    except Exception as exc:
        result['status'] = 'failed'
        # Private result only; no raw provider response or exception is printed publicly.
        result['reason'] = str(exc) if isinstance(exc, ValidationError) else 'execution or evidence capture failed'
        if recovery is not None:
            readback(recovery, candidate, reader)
            try:
                save(output / 'recovery.json', recovery)
            except OSError:
                result['recovery_collection'] = 'unknown'
                result['retain_storage'] = True
    save(output / 'result.json', result)
    return result


def reverse_documents(recovery: dict, req: dict, observations: dict, target: dict) -> dict:
    import re

    from iaas_automation.opnsense_validation import validate_documents
    from .contracts import RESOURCES, identity

    shape(recovery, {'schema_version', 'kind', 'target', 'runtime', 'candidate_sha256', 'execution_id', 'entries', 'stages'})
    require(type(recovery['schema_version']) is int and recovery['schema_version'] in {1, RECOVERY_VERSION} and recovery['kind'] == 'opnsense-recovery'
            and isinstance(recovery['target'], dict) and recovery['target'] == target,
            'incompatible recovery target or format')
    require(isinstance(recovery['runtime'], dict)
            and set(recovery['runtime']) == {'image_digest', 'platform', 'interface_version'}
            and isinstance(recovery['runtime']['image_digest'], str)
            and re.fullmatch(r'(?:[^@]+@)?sha256:[0-9a-f]{64}', recovery['runtime']['image_digest'])
            and recovery['runtime']['platform'] in {'linux/amd64', 'linux/arm64'}
            and type(recovery['runtime']['interface_version']) is int
            and recovery['runtime']['interface_version'] == 1,
            'incompatible recovery runtime identity')
    require(isinstance(recovery['candidate_sha256'], str)
            and re.fullmatch(r'[0-9a-f]{64}', recovery['candidate_sha256']),
            'incompatible recovery candidate digest')
    require(isinstance(recovery['execution_id'], str)
            and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', recovery['execution_id']),
            'incompatible recovery execution identity')
    require(isinstance(recovery['entries'], list) and isinstance(recovery['stages'], list),
            'malformed recovery document')

    available = {}
    for entry in recovery['entries']:
        shape(entry, {'resource', 'identity', 'before', 'before_absent', 'recovery', 'desired',
                      'attempted', 'after_status', 'after'})
        resource = entry['resource']
        identity_value = entry['identity']
        require(resource in RESOURCES and isinstance(identity_value, list),
                'malformed recovery identity')
        selectors({resource: [identity_value]}, allow_all=False)
        marker = key(resource, identity_value)
        require(marker not in available, 'duplicate recovery identity')
        require(type(entry['before_absent']) is bool and type(entry['attempted']) is bool
                and entry['recovery'] in {'expressible', 'manual_required'}
                and entry['after_status'] in {'unknown', 'confirmed'},
                'malformed recovery status')
        desired = entry['desired']
        require(isinstance(desired, dict), 'malformed recovery desired declaration')
        validate_documents({resource: {TOP_LEVEL[resource]: [desired]}})
        require(identity(resource, desired) == identity_value,
                'recovery desired identity does not match its entry')
        before = entry['before']
        if entry['before_absent']:
            require(before is None, 'recovery absence marker has a before-state')
        elif before is not None:
            require(isinstance(before, dict), 'malformed recovery before-state')
            validate_documents({resource: {TOP_LEVEL[resource]: [before]}})
            require(identity(resource, before) == identity_value,
                    'recovery before identity does not match its entry')
        else:
            require(entry['recovery'] == 'manual_required',
                    'missing recovery before-state must be manual-required')
        after = entry['after']
        if entry['after_status'] == 'unknown':
            require(after is None, 'unknown recovery status needs reconciled evidence before recovery')
        elif after is not None:
            require(isinstance(after, dict), 'malformed recovery after-state')
            validate_documents({resource: {TOP_LEVEL[resource]: [after]}})
            require(identity(resource, after) == identity_value,
                    'recovery after identity does not match its entry')
        available[marker] = entry

    staged = set()
    for stage in recovery['stages']:
        shape(stage, {'resource', 'mode', 'identities', 'attempted', 'save', 'activation',
                      'configuration', 'active'}, {'activation_detail', 'activation_basis', 'warnings',
                                                  'confirmation', 'content_actions', 'content_update'})
        require(stage['mode'] in {'save', 'activation_recovery'}
                and type(stage['attempted']) is bool and stage['attempted'],
                'malformed recovery stage')
        selectors({stage['resource']: stage['identities']}, allow_all=False)
        markers = {key(stage['resource'], ident) for ident in stage['identities']}
        require(markers <= available.keys() and not markers & staged,
                'recovery stage exceeds or repeats affected scope')
        if 'activation_detail' in stage:
            require(isinstance(stage['activation_detail'], dict), 'malformed recovery activation detail')
        staged.update(markers)

    selectors(req['selection'])
    wanted = set()
    for resource, selection in req['selection'].items():
        resource_markers = {marker for marker, entry in available.items() if entry['resource'] == resource}
        if selection == 'all':
            require(resource_markers, 'recovery all selection has no recorded resource entries')
            wanted.update(resource_markers)
        else:
            wanted.update(marker for marker in resource_markers if available[marker]['identity'] in selection)
            require({key(resource, ident) for ident in selection} <= available.keys(), 'recovery identity is not in this execution')
    documents = {resource: {TOP_LEVEL[resource]: []} for resource in req['selection']}
    for marker in sorted(wanted):
        entry = available[marker]
        require(entry['attempted'] is True and entry['recovery'] == 'expressible'
                and entry['after_status'] == 'confirmed',
                'recovery needs reconciled evidence or manual recovery')
        observation = observations.get(entry['resource'], {})
        matches = [obj for obj in observation.get('objects', []) if obj['identity'] == entry['identity']]
        require(observation.get('status') == 'complete' and len(matches) <= 1, 'current recovery scope is unknown')
        current = matches[0].get('configuration') if matches else None
        require(not matches or current is not None, 'current recovery state is unsupported')
        require(semantic(entry['resource'], current) == semantic(entry['resource'], entry['after']),
                'later configuration change prevents automatic recovery; reconcile and review')
        if entry['before_absent']:
            record = deepcopy(entry['desired'])
            record['state'] = 'absent'
            if entry['resource'] in {'dnat', 'one-to-one-nat'}:
                record = {field: record[field] for field in ('scope', 'slug', 'state')}
            elif entry['resource'] == 'interface-groups':
                record = {'name': record['name'], 'state': 'absent'}
        else:
            require(entry['before'] is not None, 'missing actual before-state')
            record = deepcopy(entry['before'])
        documents[entry['resource']][TOP_LEVEL[entry['resource']]].append(record)
    validate_documents(documents)
    return documents
