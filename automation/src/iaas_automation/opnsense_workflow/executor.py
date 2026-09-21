"""Reviewed execution, independent checks and explicit inverse candidates."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
from typing import Any, cast

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.opnsense_validation import TOP_LEVEL, validate_document
from .contracts import RECOVERY_VERSION, RESULT_VERSION, key, save, selected_records, selection_keys, selectors, shape, validate_coverage
from .planning import interfaces_from, objects, overlay, plan, relevant, semantic, valid_state
from .admission import (management_semantics, require_configuration_observation,
                        require_independent, validate_classification)


def fingerprint(state: dict) -> dict:
    """Compare configuration, identity and expressibility, excluding telemetry."""
    return {marker: None if obj is None else {
        'configuration': semantic(obj['resource'], obj['configuration']) if obj.get('configuration') else None,
        'references': obj.get('references') if obj.get('configuration') is None else None,
        'recovery': obj.get('recovery', 'manual_required'),
        'management': management_semantics(obj.get('classification')),
        'reference_support': obj.get('reference_support'),
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
    comparison = deepcopy(expected)
    for item in candidate['selected']:
        marker = key(item['resource'], item['identity'])
        actual = current.get(marker)
        if actual is not None:
            require_independent(actual)
        previous = comparison.get(marker)
        if previous is not None and previous.get('creation_expected'):
            # There was no native before-classification for a reviewed create.
            # Admit only independently manageable actual state; never invent
            # management evidence in the candidate or accept a missing object.
            require(actual is not None, 'created resource is missing from configuration readback')
            previous['classification'] = deepcopy(cast(dict, actual)['classification'])
    require(fingerprint(current) == fingerprint(comparison), 'related configuration drift; review a new candidate')
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
        if (observation.get('observation_scope') == 'configuration'
                and observation.get('status') == 'complete' and len(matches) <= 1):
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
        if old is not None:
            require_independent(old)
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
                        'before_classification': deepcopy(old['classification']) if old else None,
                        'recovery': recoverable,
                        'desired': deepcopy(item['desired']), 'attempted': False,
                        'after_status': 'unknown', 'after': None, 'after_classification': None})
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
        entry.update(after_status='unknown', after=None, after_classification=None)
        if (observation.get('observation_scope') == 'configuration'
                and observation.get('status') == 'complete' and len(matches) <= 1):
            if not matches:
                entry['after_status'] = 'confirmed'
            elif matches[0].get('configuration') is not None:
                try:
                    classification = validate_classification(matches[0].get('classification'))
                except ValidationError:
                    continue
                entry.update(after_status='confirmed', after=matches[0]['configuration'],
                             after_classification=deepcopy(classification))


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
                    entry.update(attempted=True, after_status='unknown', after=None, after_classification=None)
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


def reverse_documents(recovery: dict, req: dict, observations: dict, target: dict,
                      *, allow_local_source: bool = False) -> dict:
    import re

    from iaas_automation.opnsense_validation import validate_documents
    from .contracts import RESOURCES, identity

    shape(recovery, {'schema_version', 'kind', 'target', 'runtime', 'candidate_sha256', 'execution_id', 'entries', 'stages'})
    require(type(recovery['schema_version']) is int and recovery['schema_version'] == RECOVERY_VERSION and recovery['kind'] == 'opnsense-recovery'
            and isinstance(recovery['target'], dict) and recovery['target'] == target,
            'incompatible recovery target or format; retain evidence, reconcile and prepare a new plan')
    runtime = recovery['runtime']
    image_runtime = (isinstance(runtime, dict)
                     and set(runtime) == {'image_digest', 'platform', 'interface_version'}
                     and isinstance(runtime['image_digest'], str)
                     and re.fullmatch(r'(?:[^@]+@)?sha256:[0-9a-f]{64}', runtime['image_digest'])
                     and runtime['platform'] in {'linux/amd64', 'linux/arm64'})
    local_runtime = (allow_local_source is True and isinstance(runtime, dict)
                     and set(runtime) == {'kind', 'source_sha256', 'platform', 'interface_version'}
                     and runtime['kind'] == 'local-source' and isinstance(runtime['source_sha256'], str)
                     and re.fullmatch(r'[0-9a-f]{64}', runtime['source_sha256'])
                     and runtime['platform'] in {'linux/amd64', 'linux/arm64', 'darwin/amd64', 'darwin/arm64'})
    require((image_runtime or local_runtime)
            and type(runtime['interface_version']) is int
            and runtime['interface_version'] == 1,
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
                      'attempted', 'after_status', 'after', 'before_classification', 'after_classification'})
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
            require(before is None and entry['before_classification'] is None,
                    'recovery absence marker has a before-state')
        elif before is not None:
            validate_classification(entry['before_classification'])
            require(isinstance(before, dict), 'malformed recovery before-state')
            validate_documents({resource: {TOP_LEVEL[resource]: [before]}})
            require(identity(resource, before) == identity_value,
                    'recovery before identity does not match its entry')
        else:
            validate_classification(entry['before_classification'])
            require(entry['recovery'] == 'manual_required',
                    'missing recovery before-state must be manual-required')
        after = entry['after']
        if entry['after_status'] == 'unknown':
            require(after is None and entry['after_classification'] is None,
                    'unknown recovery status needs reconciled evidence before recovery')
        elif after is not None:
            validate_classification(entry['after_classification'])
            require(isinstance(after, dict), 'malformed recovery after-state')
            validate_documents({resource: {TOP_LEVEL[resource]: [after]}})
            require(identity(resource, after) == identity_value,
                    'recovery after identity does not match its entry')
        else:
            require(entry['after_classification'] is None, 'absent recovery after-state has classification')
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
        require_configuration_observation(observation)
        matches = [obj for obj in observation.get('objects', []) if obj['identity'] == entry['identity']]
        require(observation.get('status') == 'complete' and len(matches) <= 1, 'current recovery scope is unknown')
        current = matches[0].get('configuration') if matches else None
        if not entry['before_absent']:
            require_independent({'classification': entry['before_classification']})
        if entry['after'] is not None:
            require_independent({'classification': entry['after_classification']})
        if matches:
            require_independent(matches[0])
            require(entry['after'] is not None
                    and management_semantics(matches[0].get('classification')) ==
                    management_semantics(entry['after_classification']),
                    'later resource management change prevents automatic recovery; reconcile and review')
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
