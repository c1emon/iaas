"""Read-only, digest-bound reconciliation of retained acceptance executions.

No code in this module dispatches a mutation or rewrites original evidence.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID

from pydantic import create_model

from iaas.common.errors import ValidationError
from iaas.pve_acceptance_contracts import (
    Authorization, CloudInit, Deadlines, RuntimeIdentity, Target, Timeouts, canonical_digest, deadline_timestamp, load_strict_json,
    AcceptancePreview, AcceptanceResult, StopDiagnostics,
    validate_acceptance_request, validate_acceptance_result,
)
from .acceptance_execution import confined, validate_acceptance_materials
from .recovery_contracts import validate_recovery_request


class RecoveryEvidenceError(ValidationError):
    """A bounded diagnosis without native payloads or authenticated principals."""


def check(condition: Any, reason: str) -> None:
    if not condition:
        raise RecoveryEvidenceError(reason)


def material(root: Path, ref: dict) -> dict:
    path = confined(root, ref['path'])
    check(path.stat().st_size <= 4 * 1024 * 1024, 'recovery_material_too_large')
    raw = path.read_bytes()
    check(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'recovery_material_digest_conflict')
    value = load_strict_json(path)
    check(isinstance(value, dict), 'recovery_material_invalid')
    return value


# Validation-only historical models. They are never exported, serialized or
# admitted by a new start; original evidence bytes remain untouched.
RetainedPreviewV1 = create_model('RetainedPreviewV1', __base__=AcceptancePreview,
                                schema_version=(Literal[1], ...), clone_marker=(None, None))
RetainedResultV3 = create_model('RetainedResultV3', __base__=AcceptanceResult,
                               schema_version=(Literal[3], ...), stop_diagnostics=(StopDiagnostics | None, None))


def validate_retained_acceptance(request: dict, journal: dict, result: dict | None,
                                 original_execution_id: str) -> None:
    """Validate current snapshots; retained rc.19 parsing remains confined here."""
    if type(request.get('schema_version')) is int and request['schema_version'] == 3:
        validate_acceptance_request(request)
        check(journal.get('kind') == 'pve-one-shot-journal'
              and type(journal.get('schema_version')) is int and journal['schema_version'] == 1
              and journal.get('operation') == 'accept' and journal.get('execution_id') == original_execution_id
              and isinstance(journal.get('tasks'), list)
              and type(journal.get('mutation_active')) is bool
              and journal.get('status') in {'running', 'interrupted', 'finished'}, 'original_journal_binding_conflict')
        retained = journal.get('preview', {}).get('schema_version') == 1
        if retained:
            preview = journal['preview']
            check('clone_marker' not in preview, 'retained_preview_marker_conflict')
            RetainedPreviewV1.model_validate(preview)
            check(preview['request_digest'] == canonical_digest(request) and preview['fixed_input'] == request
                  and preview['preview_digest'] == canonical_digest({k: v for k, v in preview.items() if k != 'preview_digest'})
                  and journal['preview_digest'] == preview['preview_digest']
                  and journal['request_digest'] == preview['request_digest']
                  and journal['runtime'] == request['runtime'] == preview['runtime']
                  and journal['target'] == request['target'] == preview['target']
                  and journal['deadlines'] == request['deadlines'], 'retained_preview_binding_conflict')
            from .one_shot_admission import validate_one_shot_admission
            validate_one_shot_admission(journal['admission'], request=request, preview=preview,
                execution_id=original_execution_id, image_digest=request['runtime']['image_digest'],
                vmids=[request['temporary_vm']['vmid']])
        else:
            validate_acceptance_materials(request, journal)
        if result is not None:
            if retained:
                check('stop_diagnostics' not in result, 'retained_result_diagnostics_conflict')
                RetainedResultV3.model_validate(result)
            else:
                validate_acceptance_result(result)
            check(result.get('execution_id') == original_execution_id
                  and result.get('request_digest') == journal['request_digest']
                  and result.get('runtime') == journal['runtime'] and result.get('deadlines') == request['deadlines']
                  and result.get('facility_writes') == journal.get('facility_writes')
                  and result.get('preview_digest') == journal['preview_digest']
                  and result.get('cluster_scope') == request['cluster_scope']
                  and result.get('pool') == request['temporary_vm']['pool']
                  and result.get('vmid_policy') == request['vmid_policy']
                  and journal.get('result_digest') == canonical_digest(result), 'original_result_binding_conflict')
            check(result.get('overall') == 'unknown'
                  or journal['status'] == 'finished' and journal['mutation_active'] is False,
                  'original_result_activity_conflict')
            record, template = request['template_record'], result.get('template', {})
            check(all(template.get(key) == record.get(key) for key in
                      ('record_id', 'execution_id', 'artifact_digest', 'node', 'vmid', 'smbios_uuid')),
                  'original_result_source_conflict')
        return
    fields = {'kind', 'schema_version', 'target', 'template_record', 'temporary_vm',
              'cloud_init', 'required_checks', 'timeouts', 'authorization', 'deadlines'}
    check(set(request) == fields and request.get('kind') == 'pve-template-acceptance-request'
          and type(request.get('schema_version')) is int and request['schema_version'] == 2,
          'original_acceptance_contract_unsupported')
    Target.model_validate(request['target'])
    Deadlines.model_validate(request['deadlines'])
    CloudInit.model_validate(request['cloud_init'])
    Timeouts.model_validate(request['timeouts'])
    Authorization.model_validate(request['authorization'])
    required_checks = ('full_clone', 'disk_boot', 'guest_agent', 'cloud_init', 'injected_hostname', 'source_unchanged')
    check(isinstance(request['required_checks'], list) and len(request['required_checks']) == len(required_checks)
          and set(request['required_checks']) == set(required_checks), 'original_check_contract_invalid')
    record = request['template_record']
    check(isinstance(record, dict) and record.get('kind') == 'pve-template-record'
          and type(record.get('schema_version')) is int and record['schema_version'] == 2
          and record.get('origin') == 'publication' and record.get('target') == request['target']
          and record.get('node') == request['target']['node']
          and isinstance(record.get('volumes'), dict) and bool(record['volumes'])
          and isinstance(record.get('configuration'), dict), 'original_template_binding_conflict')
    check(isinstance(record.get('execution_id'), str) and isinstance(record.get('record_id'), str)
          and isinstance(record.get('artifact_digest'), str)
          and record.get('verification', {}).get('template_config') == 'passed', 'original_template_evidence_invalid')
    try:
        UUID(record['smbios_uuid'])
        temporary = request['temporary_vm']
        check(isinstance(temporary, dict) and type(temporary.get('vmid')) is int
              and 100 <= temporary['vmid'] <= 999999999
              and temporary['node'] == request['target']['node']
              and temporary['vmid'] != record['vmid'], 'original_temporary_binding_conflict')
    except (KeyError, ValueError):
        raise RecoveryEvidenceError('original_identity_invalid') from None
    digest = canonical_digest(request)
    check(journal.get('kind') == 'pve-one-shot-journal' and journal.get('schema_version') == 1
          and journal.get('operation') == 'accept' and journal.get('execution_id') == original_execution_id
          and journal.get('request_digest') == digest and journal.get('target') == request['target']
          and journal.get('deadlines') == request['deadlines'] and isinstance(journal.get('tasks'), list),
          'original_journal_binding_conflict')
    RuntimeIdentity.model_validate(journal.get('runtime'))
    admission = journal.get('admission')
    check(isinstance(admission, dict) and admission.get('schema_version') == 1
          and admission.get('execution_id') == original_execution_id and admission.get('approved') is True
          and admission.get('plan_digest') == digest.removeprefix('sha256:')
          and admission.get('target') == request['target'] and admission.get('deadlines') == request['deadlines']
          and admission.get('consumption', {}).get('reserved') is True
          and admission.get('serialization', {}).get('held') is True,
          'original_admission_binding_conflict')
    if result is not None:
        check(result.get('kind') == 'pve-template-acceptance-result' and result.get('schema_version') == 2
              and result.get('execution_id') == original_execution_id and result.get('request_digest') == digest
              and result.get('runtime') == journal['runtime'] and result.get('deadlines') == request['deadlines']
              and result.get('facility_writes') == journal.get('facility_writes')
              and journal.get('result_digest') == canonical_digest(result), 'original_result_binding_conflict')
        template = result.get('template', {})
        check(all(template.get(key) == record.get(key) for key in
                  ('record_id', 'execution_id', 'artifact_digest', 'node', 'vmid', 'smbios_uuid')),
              'original_result_source_conflict')


def load_original(request: dict, original_root: Path, evidence_root: Path) -> dict:
    request = validate_recovery_request(request)
    refs = request['original_materials']
    original = material(original_root, refs['request'])
    journal = material(original_root, refs['journal'])
    result = material(original_root, refs['result']) if refs.get('result') else None
    validate_retained_acceptance(original, journal, result, request['original_execution_id'])
    check(original['target'] == request['target'], 'recovery_target_conflict')
    caller = material(evidence_root, request['caller_association']['material'])
    association = request['caller_association']
    check(all(caller.get(key) == association[key] for key in
              ('plan_id', 'execution_id', 'pending_record_id', 'reservation_id'))
          and caller.get('native_execution_id') == request['original_execution_id']
          and caller.get('request_digest') == journal['request_digest']
          and caller.get('runtime') == journal['runtime'], 'original_caller_association_conflict')
    admission = journal['admission']
    check(admission.get('pending', {}).get('record_id') == association['pending_record_id']
          and admission.get('consumption', {}).get('reservation_id') == association['reservation_id'],
          'original_consumption_association_conflict')
    full = request['full_original_resources']
    vm = full['vm']
    owned = journal.get('temporary_vm')
    actual_mode = 'registered' if owned is not None else 'pre_registration'
    check(request.get('evidence_mode') in (None, actual_mode), 'recovery_evidence_mode_conflict')
    if owned is None:
        candidate = journal.get('clone_candidate', {})
        marker = journal.get('clone_marker')
        clones = [t for t in journal['tasks'] if t.get('phase') == 'clone']
        admission_observed = journal.get('admission_observed', {})
        check(candidate.get('complete') is True and marker
              and journal.get('preview', {}).get('clone_marker') == marker
              and candidate.get('clone_marker') == marker
              and len(clones) == 1 and clones[0].get('status') == 'succeeded'
              and clones[0].get('upid') and clones[0].get('clone_marker') == marker
              and clones[0].get('method') == 'POST'
              and clones[0].get('request_fields', {}).get('description') == marker
              and clones[0].get('request_fields', {}).get('newid') == original['temporary_vm']['vmid']
              and clones[0].get('request_fields', {}).get('target') == original['temporary_vm']['node']
              and clones[0].get('request_fields', {}).get('full') == 1
              and clones[0].get('request_fields', {}).get('pool') == original['temporary_vm']['pool']
              and clones[0].get('request_fields', {}).get('storage') == original['temporary_vm']['storage']
              and clones[0].get('path') == f"/api2/json/nodes/{original['template_record']['node']}/qemu/{original['template_record']['vmid']}/clone"
              and admission_observed.get('readiness', {}).get('vmid_free') is True,
              'pre_registration_needs_evidence')
        slots = candidate.get('slots', {})
        from .acceptance import attachments
        check(isinstance(slots, dict) and set(slots) == set(attachments(original['template_record']['configuration']))
              and set(slots.values()).isdisjoint(original['template_record']['volumes'].values())
              and all(v.startswith(original['temporary_vm']['storage'] + ':') for v in slots.values()),
              'pre_registration_scope_conflict')
        owned = {**candidate, 'volumes': sorted(slots.values())}
    check(isinstance(owned, dict) and all(owned.get(key) == vm[key] for key in ('node', 'vmid', 'smbios_uuid'))
          and owned['vmid'] == original['temporary_vm']['vmid']
          and sorted(owned.get('volumes', [])) == sorted(full['volumes']), 'original_resource_list_conflict')
    # Missing historical pool means no fabricated pool ownership requirement.
    historical_pool = original['temporary_vm'].get('pool')
    check(('pool' in vm) == ('pool' in original['temporary_vm'])
          and vm.get('pool') == historical_pool, 'historical_pool_binding_conflict')
    snippets = journal.get('snippets', [] if journal.get('temporary_vm') is None else None)
    if not isinstance(snippets, list):
        raise RecoveryEvidenceError('original_snippet_evidence_missing')
    expected = sorted((s['node'], s['file_id'], s['sha256']) for s in full['snippets'])
    actual = sorted((s.get('node'), s.get('file_id'), s.get('sha256')) for s in snippets)
    check(actual == expected and all(s.get('vmid') == vm['vmid'] for s in snippets),
          'original_snippet_list_conflict')
    if result is not None:
        expected_resources = {('vm', vm['node'], str(vm['vmid']))} | {
            ('volume', vm['node'], v) for v in full['volumes']} | {
            ('snippet', s['node'], s['file_id']) for s in full['snippets']}
        rows = result.get('temporary_resources', [])
        if not isinstance(rows, list):
            raise RecoveryEvidenceError('original_result_resource_conflict')
        check(all(isinstance(r, dict)
                  and (r.get('kind'), r.get('node'), r.get('identity')) in expected_resources
                  and r.get('created_by') in (None, request['original_execution_id'])
                  and r.get('ownership') in (None, 'owned', 'unknown') for r in rows),
              'original_result_resource_conflict')
    previous = []
    for item in request['previous_recoveries']:
        old = material(evidence_root, item['materials']['request'])
        old = validate_recovery_request(old)
        old_journal = material(evidence_root, item['materials']['journal'])
        check(old['original_execution_id'] == request['original_execution_id']
              and old['original_materials'] == request['original_materials']
              and old['caller_association'] == request['caller_association']
              and old['full_original_resources'] == full
              and old_journal.get('execution_id') == item['execution_id']
              and old_journal.get('request_digest') == canonical_digest(old), 'previous_recovery_binding_conflict')
        old_result = material(evidence_root, item['materials']['result']) if item['materials'].get('result') else None
        if old_result:
            check(old_result.get('execution_id') == item['execution_id']
                  and old_result.get('request_digest') == canonical_digest(old)
                  and old_journal.get('result_digest') == canonical_digest(old_result),
                  'previous_recovery_result_conflict')
        previous.append({'request': old, 'journal': old_journal, 'result': old_result})
    return {'request': original, 'journal': journal, 'result': result, 'caller': caller, 'previous': previous}


def _dispatch(original: dict, task: dict, index: int, caller: dict) -> dict | None:
    # rc.19 guest intent has only phase/status. The fixed endpoint comes from
    # its retained request; authenticated principal/time come from caller trace.
    rows = caller.get('dispatches', [])
    matches = [row for row in rows if isinstance(row, dict) and row.get('task_index') == index]
    if len(matches) != 1:
        return None
    dispatch = matches[0]
    vm = original['temporary_vm']
    endpoint = f"/api2/json/nodes/{quote(vm['node'], safe='')}/qemu/{vm['vmid']}/agent/exec"
    if (task.get('phase') != 'guest_exec' or dispatch.get('method') != 'POST'
            or dispatch.get('path') != endpoint or dispatch.get('node') != vm['node']
            or dispatch.get('vmid') != vm['vmid'] or not dispatch.get('authenticated_principal')
            or type(dispatch.get('dispatch_sequence')) is not int):
        return None
    try:
        deadline_timestamp(dispatch['dispatched_at'])
    except (KeyError, ValueError, TypeError):
        return None
    return dispatch


def _rejected(task: dict, index: int, original: dict, caller: dict, exports: list[dict]) -> bool:
    dispatch = _dispatch(original, task, index, caller)
    if dispatch is None:
        return False
    matches = []
    for export in exports:
        for row in export.get('records', []):
            if not isinstance(row, dict):
                continue
            keys = ('method', 'path', 'node', 'vmid', 'authenticated_principal', 'dispatch_sequence', 'dispatched_at')
            if all(row.get(key) == dispatch.get(key) for key in keys):
                matches.append(row)
    return (len(matches) == 1 and matches[0].get('http_status') == 403
            and matches[0].get('rejected_before_execution') is True)


def _task_activity(client: Any, task: dict, node: str) -> tuple[str, str]:
    upid = task.get('upid')
    if isinstance(upid, str) and upid:
        from .runtime import _normalize_upid
        try:
            upid = _normalize_upid(upid, task.get('node', node))
            row = client.request('GET', f"/api2/json/nodes/{quote(task.get('node', node), safe='')}/tasks/{quote(upid, safe='')}/status")
            if isinstance(row, dict):
                if row.get('status') == 'stopped':
                    return 'inactive', 'task_stopped'
                if row.get('status') == 'running':
                    return 'active', 'task_running'
        except Exception:
            pass
        return 'unknown', 'task_activity_unknown'
    if task.get('phase') == 'guest_exec' and type(task.get('pid')) is int:
        vmid = task.get('vmid')
        if vmid is None:
            match = re.fullmatch(r'/api2/json/nodes/[^/]+/qemu/(\d+)/agent/exec', task.get('path', ''))
            vmid = int(match[1]) if match else None
        if vmid is None:
            return 'unknown', 'guest_process_association_missing'
        try:
            row = client.request('GET', f"/api2/json/nodes/{quote(task.get('node', node), safe='')}/qemu/{vmid}/agent/exec-status", fields={'pid': task['pid']})
            if isinstance(row, dict) and row.get('exited') in (True, 1):
                return 'inactive', 'guest_process_exited'
            if isinstance(row, dict) and row.get('exited') in (False, 0):
                return 'active', 'guest_process_running'
        except Exception:
            pass
        return 'unknown', 'guest_process_activity_unknown'
    if task.get('status') == 'running':
        return 'active', 'retained_running_task'
    if task.get('status') in {'not_sent', 'rejected'}:
        return 'inactive', 'retained_terminal_request'
    if task.get('status') in {'succeeded', 'failed'} and (task.get('phase') != 'guest_exec' or type(task.get('pid')) is int):
        return 'inactive', 'retained_terminal_request'
    if task.get('phase') == 'guest_exec' and task.get('status') in {'intent', 'unknown'} and task.get('pid') is None:
        return 'unknown', 'historical_guest_exec_unlinked'
    return 'unknown', 'request_outcome_unknown'


def reconcile_original(request: dict, original_root: Path, evidence_root: Path, client: Any,
                       snippets: Any, *, trusted_rejection_exports: dict[str, dict] | None = None,
                       approved_frozen_proof: dict | None = None) -> dict:
    """Read-only GET/helper inspection; return facts used by plan and start.

    trusted_rejection_exports is derived from declarations bound by the approved
    recovery request. Plan may use the declarations; start rechecks approval.
    """
    request = validate_recovery_request(request)
    originals = load_original(request, original_root, evidence_root)
    old, journal, caller = originals['request'], originals['journal'], originals['caller']
    trusted = trusted_rejection_exports or {}
    exports = []
    for declaration in request['rejection_evidence']:
        grant = trusted.get(declaration['source_id'])
        if not grant or grant.get('sha256') != declaration['material']['sha256'] or grant.get('provenance') != declaration['provenance']:
            continue
        export = material(evidence_root, declaration['material'])
        if (export.get('source_id') == declaration['source_id']
                and export.get('provenance') == declaration['provenance']
                and export.get('original_execution_id') == request['original_execution_id']
                and export.get('authenticated_principal') == declaration['authenticated_principal']
                and isinstance(export.get('records'), list)
                and all(isinstance(row, dict) and row.get('authenticated_principal') == declaration['authenticated_principal']
                        for row in export['records'])):
            exports.append(export)
    requests = []
    for index, task in enumerate(journal['tasks']):
        check(isinstance(task, dict), 'original_task_evidence_invalid')
        activity, reason = _task_activity(client, task, old['temporary_vm']['node'])
        if reason == 'historical_guest_exec_unlinked' and _rejected(task, index, old, caller, exports):
            activity, reason = 'inactive', 'request_rejected'
        requests.append({'task_index': index, 'phase': task.get('phase'), 'original_status': task.get('status'),
                         'activity': activity, 'reason_code': reason,
                         'historical_write': 'none' if task.get('status') == 'not_sent' or reason == 'request_rejected'
                         else 'unknown' if activity in {'unknown', 'active'} else 'issued'})
    helper_unknown = any(s.get('uploaded') is not True or s.get('cleanup', {}).get('status') == 'unknown'
                         for s in journal.get('snippets', []))
    previous_unknown = False
    active = any(r['activity'] == 'active' for r in requests)
    unresolved = helper_unknown or any(r['activity'] == 'unknown' and r['reason_code'] != 'historical_guest_exec_unlinked'
                                       for r in requests)
    for previous in originals['previous']:
        prior = previous['journal']
        rows = prior.get('tasks', [])
        activities = [_task_activity(client, row, request['target']['node'])[0] for row in rows] if isinstance(rows, list) else ['unknown']
        active = active or 'active' in activities
        if 'unknown' in activities or 'active' in activities:
            previous_unknown = True
        if prior.get('mutation_active') is True and not rows:
            previous_unknown = True
        if any(isinstance(row, dict) and row.get('phase') == 'snippet_delete'
               and row.get('status') not in {'succeeded', 'not_sent', 'rejected'} for row in rows):
            previous_unknown = True
    activity = 'unknown' if active or helper_unknown or previous_unknown or any(r['activity'] == 'unknown' for r in requests) else 'inactive'
    unresolved = unresolved or previous_unknown
    writes = 'unknown' if any(r['historical_write'] == 'unknown' for r in requests) or helper_unknown else (
        'issued' if any(r['historical_write'] == 'issued' for r in requests) or journal.get('snippets') else 'none')
    # No global mutation_active flag can clear a missing per-request fact.
    if journal.get('mutation_active') is True and not requests and not journal.get('snippets'):
        activity, writes = 'unknown', 'unknown'
        unresolved = True
    current = inspect_resources(request, client, snippets)
    candidate = journal.get('clone_candidate') if journal.get('temporary_vm') is None else None
    proof = {'mode': 'pre_registration' if candidate else 'registered',
             'request_digest': journal['request_digest'],
             'scope_digest': canonical_digest(request['full_original_resources'])}
    if candidate:
        proof.update(clone_marker=journal['clone_marker'], smbios_uuid=candidate['smbios_uuid'],
                     slots=candidate['slots'], clone_upid=next(t['upid'] for t in journal['tasks'] if t['phase'] == 'clone'))
        if current['vm']['existence'] == 'present':
            config = client.request('GET', f"/api2/json/nodes/{quote(old['temporary_vm']['node'], safe='')}/qemu/{old['temporary_vm']['vmid']}/config")
            from .acceptance import attachments
            from .runtime import _config_uuid
            check(isinstance(config, dict) and config.get('description') == proof['clone_marker']
                  and _config_uuid(config) == proof['smbios_uuid'] and attachments(config) == proof['slots'],
                  'pre_registration_identity_conflict')
        else:
            check(approved_frozen_proof == proof or any(p['journal'].get('proof_bindings') == proof
                      and any(t.get('phase') == 'delete' and t.get('status') == 'succeeded' for t in p['journal'].get('tasks', []))
                      for p in originals['previous']), 'pre_registration_absent_needs_frozen_scope')
    source = old['template_record']
    try:
        from .runtime import _config_uuid
        from .acceptance import attachments, stable
        configuration = client.request('GET', f"/api2/json/nodes/{quote(source['node'], safe='')}/qemu/{source['vmid']}/config")
        if not isinstance(configuration, dict):
            source_observation = {'status': 'unavailable'}
        else:
            identity_matches = _config_uuid(configuration) == source['smbios_uuid']
            source_observation = {'status': 'unchanged' if identity_matches and stable(configuration) == stable(source['configuration']) else 'changed',
                                  'identity_matches': identity_matches}
    except Exception:
        source_observation = {'status': 'unavailable'}
    # Historical uncertainty is disclosed in the reviewed preview. The existing
    # new cleanup approval authorizes disposition; no reconstructed trace is
    # required for unlinked legacy guest exec. Failed current task observations
    # cannot be replaced by an administrator approval.
    safe = not active and not unresolved and current['ownership'] == 'confirmed'
    if candidate:
        safe = safe and source_observation['status'] == 'unchanged'
        if current['vm']['existence'] == 'present':
            safe = safe and all(v['existence'] == 'present' for v in current['volumes'])
    return {'status': 'eligible' if safe else 'unknown', 'cleanup_eligible': safe,
            'disposition': 'blocked' if not safe else 'administrator_decision' if activity == 'unknown' else 'automatic',
            'active_tasks': active,
            'task_activity_unresolved': unresolved,
            'original_activity': activity, 'original_facility_writes': writes,
            'requests': requests, 'helper_activity': 'unknown' if helper_unknown else 'inactive',
            'previous_activity': 'unknown' if previous_unknown else 'inactive',
            'original_runtime': journal['runtime'], 'original_deadlines': journal['deadlines'],
            'original_acceptance': originals['result'].get('overall') if originals['result'] else 'unknown',
            'resources': current, 'source_observation': source_observation, 'proof_bindings': proof, 'facility_writes': 'none'}


def inspect_resources(request: dict, client: Any, snippets: Any) -> dict:
    """Independent clone ownership; source drift is reported, never adopted."""
    from .acceptance import attachments
    from .runtime import _config_uuid
    from .admission import Permissions
    full = request['full_original_resources']
    vm = full['vm']
    node = quote(vm['node'], safe='')
    permissions = Permissions(client)
    permissions.require(f"/vms/{vm['vmid']}", ('VM.Audit',), operation='recovery_inspect')
    snapshot = snippets.inspect()
    check(isinstance(snapshot, dict) and snapshot.get('complete') is True
          and snapshot.get('local_node') == vm['node'] and isinstance(snapshot.get('nodes'), list)
          and isinstance(snapshot.get('vmids'), list) and isinstance(snapshot.get('references'), list),
          'recovery_visibility_insufficient')
    nodes = client.request('GET', '/api2/json/nodes')
    check(isinstance(nodes, list) and {row.get('node') for row in nodes if isinstance(row, dict)} <= set(snapshot['nodes']),
          'recovery_cluster_visibility_conflict')
    resources = client.request('GET', '/api2/json/cluster/resources', fields={'type': 'vm'})
    check(isinstance(resources, list) and all(isinstance(row, dict) for row in resources),
          'recovery_vm_inventory_insufficient')
    external_volumes: set[str] = set()
    external_snippets: set[str] = set()
    if isinstance(snapshot.get('volume_references'), list) and isinstance(snapshot.get('snippet_references'), list):
        for row in snapshot['volume_references']:
            check(isinstance(row, dict) and type(row.get('vmid')) is int and isinstance(row.get('volid'), str),
                  'recovery_reference_evidence_invalid')
            if row['vmid'] != vm['vmid'] or row.get('node') != vm['node']:
                external_volumes.add(row['volid'])
        for row in snapshot['snippet_references']:
            check(isinstance(row, dict) and type(row.get('vmid')) is int and isinstance(row.get('file_name'), str),
                  'recovery_reference_evidence_invalid')
            if row['vmid'] != vm['vmid'] or row.get('node') != vm['node']:
                external_snippets.add(row['file_name'])
    else:
        check({row.get('vmid') for row in resources} == set(snapshot['vmids']),
              'recovery_vm_inventory_incomplete')
        for row in resources:
            if row.get('vmid') == vm['vmid']:
                continue
            check(row.get('type') in {'qemu', 'lxc'}, 'recovery_reference_type_unknown')
            config = client.request('GET', f"/api2/json/nodes/{quote(row['node'], safe='')}/{row['type']}/{row['vmid']}/config")
            check(isinstance(config, dict), 'recovery_reference_visibility_insufficient')
            for value in config.values():
                if isinstance(value, str):
                    external_volumes.update(v for v in full['volumes'] if v in value.split(','))
                    external_snippets.update(s['file_id'].split('/', 1)[1] for s in full['snippets']
                                             if s['file_id'].split('/', 1)[1] in value)
    present = vm['vmid'] in snapshot['vmids']
    observed_pool = None
    owned = True
    if present:
        permissions.require(f"/vms/{vm['vmid']}", ('VM.Allocate', 'VM.PowerMgmt'), operation='recovery_cleanup')
        config = client.request('GET', f'/api2/json/nodes/{node}/qemu/{vm["vmid"]}/config')
        check(isinstance(config, dict), 'recovery_vm_query_insufficient')
        owned = (_config_uuid(config) == vm['smbios_uuid'] and sorted(attachments(config).values()) == sorted(full['volumes'])
                 and not config.get('lock'))
        resources = client.request('GET', '/api2/json/cluster/resources', fields={'type': 'vm'})
        rows = [row for row in resources if isinstance(row, dict) and row.get('vmid') == vm['vmid']] if isinstance(resources, list) else []
        check(len(rows) == 1 and rows[0].get('node') == vm['node'], 'recovery_vm_membership_insufficient')
        observed_pool = rows[0].get('pool') or None
        if 'pool' in vm:
            owned = owned and observed_pool == vm['pool']
    volumes = []
    for volid in full['volumes']:
        storage = volid.split(':', 1)[0]
        permissions.require('/storage/' + storage, ('Datastore.Audit',), operation='recovery_volume_inspect')
        rows = client.request('GET', f'/api2/json/nodes/{node}/storage/{quote(storage, safe="")}/content')
        check(isinstance(rows, list), 'recovery_volume_visibility_insufficient')
        matches = [row for row in rows if isinstance(row, dict) and row.get('volid') == volid]
        check(len(matches) <= 1, 'recovery_volume_inventory_ambiguous')
        if matches:
            permissions.require('/storage/' + storage, ('Datastore.AllocateSpace',), operation='recovery_volume_cleanup')
        matches_owned = not matches or str(matches[0].get('vmid')) == str(vm['vmid'])
        matches_owned = matches_owned and volid not in external_volumes
        owned = owned and matches_owned
        volumes.append({'identity': volid, 'existence': 'present' if matches else 'absent',
                        'ownership': 'confirmed' if matches_owned else 'mismatch'})
    snippet_rows = []
    for snippet in full['snippets']:
        name = snippet['file_id'].split('/', 1)[1]
        # Its own clone's reference is removable by the exact authorized VM
        # cleanup. Deletion adapter must recheck global references afterwards.
        referenced = name in external_snippets or (name in snapshot['references'] and not present)
        transport = {**snippet, 'storage': snippet['file_id'].split(':', 1)[0],
                     'file_name': name, 'vmid': vm['vmid']}
        content = snippets.inspect_file(transport) if hasattr(snippets, 'inspect_file') else {'existence': 'unknown'}
        matched = content.get('existence') == 'absent' or (content.get('existence') == 'present' and content.get('sha256') == snippet['sha256'])
        owned = owned and matched and not referenced
        snippet_rows.append({'identity': snippet['file_id'], 'existence': content.get('existence', 'unknown'),
                             'ownership': 'confirmed' if matched else 'unknown', 'referenced': referenced})
    return {'vm': {'identity': str(vm['vmid']), 'existence': 'present' if present else 'absent',
                   'ownership': 'confirmed' if owned else 'mismatch', 'observed_pool': observed_pool},
            'volumes': volumes, 'snippets': snippet_rows, 'ownership': 'confirmed' if owned else 'unknown'}
