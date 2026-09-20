"""Fixed operation evidence contracts; observations never imply action completion."""
from __future__ import annotations

from copy import deepcopy
import math
import ipaddress
import time

from iaas_automation.common.errors import require

WAIT_POLICY = {'deadline_seconds': 60, 'max_attempts': 30, 'interval_seconds': 2, 'request_timeout_seconds': 15}
SYNC_RESOURCES = {'filter-rules', 'dnat', 'one-to-one-nat', 'vips'}
SOURCE_FIELDS = ('type', 'content', 'updatefreq_days', 'interface', 'counters')
LIMITED_RESPONSE_RESOURCES = {'aliases', 'gateways', 'interface-groups'}


def response_warnings(resource: str) -> list[dict]:
    if resource not in LIMITED_RESPONSE_RESOURCES:
        return []
    return [{'code': 'IAAS-OPNSENSE-RESULT-LIMITATION', 'resource': resource,
             'message': 'Native success is trusted; upstream does not return all internal step results. '
                        'Internal completion and active state are not independently confirmed.'}]


def validate_wait(value: dict) -> dict:
    require(isinstance(value, dict) and set(value) == set(WAIT_POLICY), 'invalid confirmation wait policy')
    for field, maximum in WAIT_POLICY.items():
        number = value[field]
        require(type(number) in {int, float} and math.isfinite(number)
                and (number >= 0 if field == 'interval_seconds' else number > 0) and number <= maximum,
                'confirmation wait exceeds fixed limits')
    require(type(value['max_attempts']) is int, 'confirmation attempts must be an integer')
    return deepcopy(value)


def dynamic_alias(record: dict) -> bool:
    if record.get('type') in {'urltable', 'urljson', 'dynipv6host'}:
        return True
    if record.get('type') == 'host':
        for entry in record.get('content', []):
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                return True
    return False


def content_actions(stage: dict, differences: list[dict]) -> list[dict]:
    if stage['resource'] != 'aliases':
        return []
    actions = []
    for diff in differences:
        if diff['resource'] != 'aliases' or diff['identity'] not in stage['identities']:
            continue
        after, before = diff['after'], diff['before']
        if not after or not after.get('enabled') or not dynamic_alias(after):
            continue
        source = {field: deepcopy(after[field]) for field in SOURCE_FIELDS if field in after}
        previous = {field: before[field] for field in SOURCE_FIELDS if field in before} if before else None
        recovery = stage['mode'] == 'activation_recovery'
        if before and before.get('enabled') and source == previous and not recovery:
            continue
        trigger = ('activation_recovery' if recovery else 'created' if not before else
                   'source_changed' if source != previous else 're_enabled')
        actions.append({'identity': deepcopy(diff['identity']), 'source': source,
                        'trigger': trigger, 'action': 'initialize' if not before else 'update',
                        'execution': 'native_activation',
                        'cache': {'policy': 'provider_native'},
                        'required_evidence': ['native_response']})
    return actions


def stage_contract(stage: dict, differences: list[dict], observation: dict) -> dict:
    resource = stage['resource']
    actions = content_actions(stage, differences)
    gaps = []
    if observation.get('status') != 'complete':
        gaps.append({'evidence': 'configuration_read', 'status': 'unknown',
                     'reason': 'required_configuration_observation_incomplete'})
    return {'rule': 'opnsense-provider-response-' + resource + '-v2',
            'required_evidence': ['native_response', 'configuration_readback'], 'supplementary_checks': [],
            'capability': 'available' if not gaps else 'unknown',
            'basis': 'fixed Collection native response; configuration readback', 'gaps': gaps,
            'warnings': response_warnings(resource), 'content_actions': actions}


def bind_stages(stages: list[dict], differences: list[dict], observations: dict) -> list[dict]:
    return [{**deepcopy(stage), 'confirmation': stage_contract(stage, differences, observations.get(stage['resource'], {})),
             'content_actions': content_actions(stage, differences)} for stage in stages]


def disposition(stages: list[dict]) -> dict:
    blocked = [stage for stage in stages if stage['confirmation']['capability'] != 'available']
    return {'status': 'blocked' if blocked else 'ready',
            'gaps': [{'resource': stage['resource'], 'identities': stage['identities'],
                      'missing': stage['confirmation']['gaps']} for stage in blocked],
            'recovery': ('manual_required' if any(stage['mode'] == 'activation_recovery' for stage in blocked) else 'not_required'),
            'guidance': ('Required configuration could not be read completely. Resolve the read failure '
                         'and review a new plan before writing.' if blocked else None)}


def native_content_results(stage: dict, activation: dict) -> list[dict]:
    """Disclose provider-managed content without inventing cache or load evidence."""
    evidence = activation.get('content_update', [])
    explicit_failure = any(isinstance(row, dict) and (
        row.get('status') in {'failed', 'error'} or row.get('loading') in {'failed', 'error'})
        for row in evidence) if isinstance(evidence, list) else False
    require(not explicit_failure or stage['content_actions'],
            'native content processing reported failure; dependent stages stopped')
    return [{'identity': action['identity'], 'action': action['action'], 'source': action['source'],
             'status': 'failed' if explicit_failure else
                       'provider_managed' if activation.get('status') == 'confirmed' else 'unknown',
             'cache': 'provider_native', 'loading': 'not_independently_checked'}
            for action in stage['content_actions']]


def recheck(candidate: dict, observations: dict) -> None:
    require(candidate['admission']['status'] == 'ready', 'blocked candidate cannot authorize writes; inspect capability gaps')
    for stage in candidate['stages']:
        current = stage_contract(stage, candidate['differences'], observations.get(stage['resource'], {}))
        require(current['capability'] == 'available', f"necessary confirmation capability lost for {stage['resource']}; zero further writes")
        require(current == stage['confirmation'], 'confirmation conditions changed; review a new plan')
        require(stage['content_actions'] == current['content_actions'], 'candidate content actions differ from reviewed contract')


def action_results(stage: dict, activation: dict) -> list[dict]:
    """Require per-source processing/loading evidence, even for equal members."""
    results = []
    for action in stage['content_actions']:
        evidence = [row for row in activation.get('content_update', [])
                    if row.get('identity') == action['identity']]
        row = evidence[0] if len(evidence) == 1 else {}
        status = row.get('status', 'unknown')
        if status != 'failed' and (status != 'confirmed' or row.get('source') != action['source']
                                   or row.get('loading') != 'confirmed'):
            status = 'unknown'
        results.append({'identity': action['identity'], 'action': action['action'],
                        'status': status, 'source': action['source'],
                        'loading': row.get('loading', 'unknown')})
    return results


def complete_action(stage: dict, activation: dict, reader, boundary, *,
                    clock=time.monotonic, sleep=time.sleep) -> dict:
    """Observe an identified unfinished action through a fixed read; never resubmit it."""
    if activation.get('status') not in {'processing', 'accepted', 'unconfirmed'}:
        return activation
    observe = getattr(reader, 'observe_confirmation', None)
    action_id = activation.get('action_id')
    if not callable(observe) or not isinstance(action_id, str) or not action_id:
        if activation.get('status') != 'processing':
            return activation
        return {**activation, 'status': 'unknown', 'reason': 'correlated_completion_observation_unavailable'}
    from .reader import observation_budget
    from .waiting import WaitPolicy, wait_for_confirmation

    policy = WaitPolicy(**stage['confirmation']['wait'])
    transport = getattr(reader, 'transport', None)
    if transport is not None:
        from .reader import FixedCollectionTransport
        if not isinstance(transport, FixedCollectionTransport):
            return {**activation, 'status': 'unknown', 'reason': 'bounded_reader_unavailable'}

    with observation_budget(policy.deadline_seconds, clock=clock,
                            request_timeout_seconds=policy.request_timeout_seconds) as budget:
        def read(timeout: float) -> dict:
            boundary()
            remaining = budget.remaining()
            if remaining <= 0:
                return {'status': 'timeout', 'reason': 'observation_deadline_exhausted', 'action_id': action_id}
            result = observe(stage, action_id, timeout=min(timeout, remaining))
            if not isinstance(result, dict) or result.get('action_id') != action_id:
                return {'status': 'unknown', 'reason': 'uncorrelated_completion_observation'}
            return result

        waited = wait_for_confirmation(read, policy=policy, clock=clock, sleep=sleep)
    return {**activation, **(waited.last_observation or {}), 'status': waited.status,
            'observation_wait': waited.as_dict()}
