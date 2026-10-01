"""One-shot evidence-bound cleanup. No VM mutation or backend initialization."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import subprocess
import time
from typing import Any

from iaas.common.errors import require
from iaas.pve_acceptance_contracts import (canonical_digest, load_strict_json,
    validate_snippet_cleanup_request, validate_snippet_cleanup_result)
from iaas.pve_template.acceptance_execution import begin, confined, observe, save
from iaas.runtime_execution.execution import OperationFailed
from iaas.runtime_execution.credentials import protected_file
from .evidence import validate_original
from iaas.pve_template.deadlines import DeadlineBudget, DeadlineExpired, LocalTimeout

HELPER = '/usr/local/sbin/iaas-pve-snippet-delete'


class Helper:
    original_vmid: int

    def __init__(self, selected: Any, execution: Any, timeout: int, ssh: dict[str, Any],
                 *, budget: DeadlineBudget | None = None, phase: str = "cleanup"):
        self.budget, self.phase = budget, phase
        self.deadline = time.monotonic() + timeout
        self.env = execution.environ
        files = selected.files
        require('known_hosts' in files and 'ssh_key' in files, 'cleanup requires isolated SSH trust and key')
        protected_file(Path(files['known_hosts']), secret=False)
        protected_file(Path(files['ssh_key']))
        host, user, port = ssh['host'], ssh['user'], ssh['port']
        require(re.fullmatch(r'[A-Za-z0-9:][A-Za-z0-9.:-]*', host) is not None
                and re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', user) is not None
                and type(port) is int and 1 <= port <= 65535, 'invalid cleanup SSH target')
        self.command = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
                        '-o', 'IdentityAgent=none',
                        '-o', 'StrictHostKeyChecking=yes', '-o', 'GlobalKnownHostsFile=/dev/null',
                        '-o', f'UserKnownHostsFile={files["known_hosts"]}', '-i', str(files['ssh_key']),
                        '-p', str(port), f'{user}@{host}']

    def call(self, args: list[str]) -> dict:
        remaining = self.deadline - time.monotonic()
        if self.budget is not None:
            remaining = min(remaining, self.budget.remaining(self.phase))
        if remaining <= 0:
            raise LocalTimeout(self.phase)
        try:
            result = subprocess.run([*self.command, shlex.join(['sudo', '-n', HELPER, *args])],
                                    env=self.env, capture_output=True, timeout=remaining, check=True, text=True)
            require(len(result.stdout) <= 4 * 1024 * 1024, 'cleanup helper result exceeds limit')
            payload = json.loads(result.stdout)
            require(isinstance(payload, dict) and payload.get('schema_version') == 2, 'invalid helper response')
            return payload
        except (OSError, subprocess.SubprocessError, ValueError):
            raise OperationFailed('cleanup helper outcome is unknown') from None

    def inspect(self) -> dict:
        require(self.budget is not None, 'snippet inspection requires a deadline budget')
        assert self.budget is not None
        cutoff = self.budget.deadlines[f'{self.phase}_deadline_at']
        return self.call(['--inspect-cluster', '--deadline-at', cutoff])

    def delete(self, snippet: dict) -> dict:
        require(self.budget is not None, 'snippet deletion requires a deadline budget')
        assert self.budget is not None
        cutoff = self.budget.deadlines[f'{self.phase}_deadline_at']
        return self.call(['--storage', snippet['storage'], '--filename', snippet['file_name'], '--sha256', snippet['sha256'],
                          '--node', snippet['node'], '--vmid', str(self.original_vmid), '--deadline-at', cutoff])


def initial_result(request: dict, execution_id: str, image_digest: str) -> dict:
    return {'kind': 'pve-snippet-cleanup-result', 'schema_version': 2, 'execution_id': execution_id,
            'deadlines': dict(request['deadlines']), 'deadline_outcome': {'phase': None, 'status': 'not_exceeded'},
            'facility_writes': 'none',
            'request_digest': canonical_digest(request), 'runtime': {'image_digest': image_digest},
            'origin': request['origin'], 'original_vm': request['original_vm'],
            'original_execution_id': request['original_execution_id'],
            'delete_plan_digest': request['delete_plan']['plan_digest'] if request['delete_plan'] else None,
            'acceptance_request_digest': request['acceptance_evidence']['request_digest'] if request['acceptance_evidence'] else None,
            'deletion_execution_id': request['deletion_evidence']['execution_id'], 'retry_of': request['retry_of'],
            'scope_check': {'status': 'unknown', 'nodes': [], 'storages': sorted({s['storage'] for s in request['snippets']}),
                            'permissions_complete': False, 'inventory_complete': False, 'reason_code': 'not_checked'},
            'items': [{**s, 'status': 'unknown', 'reason_code': 'not_checked'} for s in request['snippets']],
            'residuals': {'inventory_complete': False, 'items': []}, 'overall': 'unknown',
            'collection': {'status': 'complete', 'reason_code': 'result_collected'}}


def conclude(result: dict, *, ownership: str = 'owned') -> dict:
    result['residuals'] = {'inventory_complete': result['scope_check']['inventory_complete'], 'items': [
        {'kind': 'snippet', 'node': item['node'], 'identity': item['file_id'],
         'created_by': result['original_execution_id'], 'ownership': ownership,
         'existence': 'present' if item['reason_code'] in {'content_or_identity_changed', 'not_exclusive_regular_file'} else 'unknown',
         'reason_code': item['reason_code']} for item in result['items'] if item['status'] not in {'deleted', 'already_absent'}]}
    unknown = (result['collection']['status'] != 'complete'
               or not result['residuals']['inventory_complete'] or result['scope_check']['status'] == 'unknown'
               or any(x['status'] == 'unknown' for x in result['items'])
               or any(x['existence'] == 'unknown' for x in result['residuals']['items']))
    result['overall'] = ('unknown' if unknown else 'failed' if result['residuals']['items']
                         or result['deadline_outcome']['status'] != 'not_exceeded' else 'passed')
    return validate_snippet_cleanup_result(result)


def cleanup(request: dict, helper: Helper, result: dict, journal: dict, root: Path,
            budget: DeadlineBudget | None = None) -> dict:
    """All global visibility checks precede every exact deletion attempt."""
    try:
        if budget is not None:
            budget.remaining('work')
            helper.phase = 'work'
        snapshot = helper.inspect()
        if budget is not None:
            budget.remaining('work')
        if snapshot.get('reason_code') == 'cleanup_deadline_expired':
            result['deadline_outcome'] = {'phase': 'work', 'status': 'exceeded'}
            result['scope_check']['reason_code'] = 'work_deadline_expired'
            return conclude(result)
        require(snapshot.get('complete') is True and isinstance(snapshot.get('vmids'), list)
                and isinstance(snapshot.get('references'), list) and isinstance(snapshot.get('nodes'), list)
                and snapshot.get('reference_strategy') == 'all_storage_aliases_by_filename',
                'reference scope incomplete')
        require(request['original_vm']['node'] in snapshot['nodes'], 'original node is outside scope')
        require(snapshot.get('local_node') == request['original_vm']['node'], 'SSH helper node conflicts')
        helper.original_vmid = request['original_vm']['vmid']
        result['scope_check'].update(status='passed', nodes=snapshot['nodes'], permissions_complete=True,
                                      inventory_complete=True, reason_code='pmxcfs_complete')
        journal['scope_check'] = result['scope_check']
        if request['original_vm']['vmid'] in snapshot['vmids']:
            for item in result['items']:
                item.update(status='mismatch', reason_code='vmid_occupied')
            return conclude(result)
        save(root / 'scope.json', snapshot)
        if budget is not None:
            budget.remaining('work')
            budget.limit('cleanup', request['timeout_seconds'])
            helper.phase = 'cleanup'
            helper.deadline = time.monotonic() + request['timeout_seconds']
        save(root / 'journal.json', journal)
    except (DeadlineExpired, LocalTimeout) as expired:
        assert budget is not None
        result['deadline_outcome'] = dict(budget.outcome)
        result['scope_check']['reason_code'] = str(expired)
        return conclude(result)
    except Exception:
        result['scope_check']['reason_code'] = 'reference_scope_unconfirmed'
        return conclude(result)
    for item in result['items']:
        if item['file_name'] in snapshot['references']:
            item.update(status='referenced', reason_code='cluster_configuration_reference')
            continue
        try:
            if budget is not None:
                budget.remaining('cleanup')
        except (DeadlineExpired, LocalTimeout) as expired:
            assert budget is not None
            result['deadline_outcome'] = dict(budget.outcome)
            item.update(status='unknown', reason_code=str(expired))
            break
        previous_writes = journal.get('facility_writes', 'none')
        journal.update(mutation_active=True, current_file=item['file_id'], facility_writes='unknown')
        save(root / 'journal.json', journal)
        try:
            if budget is not None:
                budget.remaining('cleanup')
            answer = helper.delete(item)
            require(answer.get('status') in {'deleted', 'already_absent', 'referenced', 'mismatch', 'failed', 'unknown'}
                    and re.fullmatch(r'[a-z][a-z0-9_]{0,95}', answer.get('reason_code', '')) is not None,
                    'invalid helper outcome')
            item.update(status=answer['status'], reason_code=answer['reason_code'])
            if answer['reason_code'] == 'cleanup_deadline_expired':
                journal['facility_writes'] = previous_writes
                result['deadline_outcome'] = {'phase': 'cleanup', 'status': 'exceeded'}
            else:
                journal['facility_writes'] = 'issued'
            # A received terminal response proves the helper returned; an SSH
            # timeout/disconnect does not prove the remote process terminated.
            journal['mutation_active'] = False
        except (DeadlineExpired, LocalTimeout) as expired:
            journal.update(mutation_active=False, facility_writes=previous_writes)
            assert budget is not None
            result['deadline_outcome'] = dict(budget.outcome)
            item.update(status='unknown', reason_code=str(expired))
            save(root / 'journal.json', journal)
            break
        except Exception:
            item.update(status='unknown', reason_code='helper_outcome_unknown')
            save(root / 'journal.json', journal)
            break
        journal['items'] = result['items']
        save(root / 'journal.json', journal)
        if result['deadline_outcome']['status'] == 'exceeded':
            break
    result['facility_writes'] = journal.get('facility_writes', 'none')
    journal['deadline_outcome'] = result['deadline_outcome']
    return conclude(result)


def run(selected: Any, operation: str, scope: str, execution: Any,
        image_digest: str, execution_id: str = '') -> None:
    require(operation == 'snippet-cleanup', 'unsupported snippet operation')
    mode = selected.options.get('execution_mode')
    require(mode in {'start', 'observe'}, 'explicit cleanup execution_mode is required')
    request_path = selected.files.get('snippet_cleanup_request')
    try:
        if request_path is None:
            require(mode == 'observe', 'cleanup request is required')
            request_path = confined(Path(selected.files['original_execution_dir']), 'request.json')
        request = validate_snippet_cleanup_request(load_strict_json(Path(request_path)), execution_id=execution_id)
    except (OSError, ValueError, KeyError):
        if mode == 'observe':
            execution.outputs.summary({'component': 'pve', 'operation': operation, 'status': 'unknown',
                                       'execution_id': execution_id, 'mode': 'observe',
                                       'reason_code': 'original_material_unavailable'})
            raise OperationFailed('original cleanup material unavailable; no mutation performed') from None
        raise
    require(not scope or scope == request['target']['node'], 'cleanup scope conflicts with target node')
    root = execution.outputs.path('diagnostics') / 'execution'
    if mode == 'observe':
        original_root = Path(selected.files['original_execution_dir']).resolve()
        destination = execution.outputs.root.resolve()
        require(not destination.is_relative_to(original_root) and not original_root.is_relative_to(destination),
                'observe output must not overlap original execution material')
        result = None
        journal = None
        try:
            journal, result = observe(Path(selected.files['original_execution_dir']), operation, request, execution_id)
            if result is not None:
                result = validate_snippet_cleanup_result(result)
        except (OSError, ValueError, KeyError):
            pass
        if result is None:
            result = initial_result(request, execution_id, image_digest)
            result['collection'] = {'status': 'unknown', 'reason_code': 'original_result_unavailable'}
            result['facility_writes'] = 'unknown'
            if journal is not None:
                result['facility_writes'] = journal.get('facility_writes', 'unknown')
                result['deadline_outcome'] = journal.get('deadline_outcome', result['deadline_outcome'])
            if journal is not None and isinstance(journal.get('items'), list):
                original_items = journal['items']
                if (len(original_items) == len(request['snippets']) and
                        all(all(old.get(k) == snippet[k] for k in snippet)
                            for old, snippet in zip(original_items, request['snippets']))):
                    result['items'] = original_items
                    result['scope_check'] = journal.get('scope_check', result['scope_check'])
            result = conclude(result, ownership='unknown')
        save(execution.outputs.root / 'pve-snippet-cleanup-result.json', result)
        if result['overall'] == 'passed':
            execution.finish({'component': 'pve', 'operation': operation, 'overall': result['overall'],
                              'execution_id': execution_id, 'mode': 'observe'})
        else:
            execution.outputs.summary({'component': 'pve', 'operation': operation, 'status': result['overall'],
                                       'execution_id': execution_id, 'mode': 'observe'})
            raise OperationFailed('original cleanup result is incomplete; no mutation performed')
        return
    require('cleanup_evidence_dir' in selected.files and 'execution_admission' in selected.files,
            'cleanup evidence and admission are required')
    admission = load_strict_json(Path(selected.files['execution_admission']))
    # Freeze both windows before any potentially slow evidence work.
    budget = DeadlineBudget(request['deadlines'])
    journal = begin(root, operation, request, admission, execution_id, image_digest)
    result = initial_result(request, execution_id, image_digest)
    try:
        budget.admit()
        budget.remaining('work')
        validate_original(request, Path(selected.files['cleanup_evidence_dir']))
        budget.remaining('work')
        budget.limit('work', request['timeout_seconds'])
        helper = Helper(selected, execution, request['timeout_seconds'], request['ssh'], budget=budget, phase='work')
        result = cleanup(request, helper, result, journal, root, budget)
    except (DeadlineExpired, LocalTimeout) as expired:
        assert budget is not None
        result['deadline_outcome'] = dict(budget.outcome)
        result['scope_check']['reason_code'] = str(expired)
        result = conclude(result)
    except Exception:
        result = conclude(result)
    result['facility_writes'] = journal.get('facility_writes', 'none')
    journal['deadline_outcome'] = result['deadline_outcome']
    save(root / 'result.json', result)
    journal.update(status='finished' if journal.get('mutation_active') is False else 'interrupted',
                   result_digest=canonical_digest(result))
    save(root / 'journal.json', journal)
    save(execution.outputs.root / 'pve-snippet-cleanup-result.json', result)
    if result['overall'] != 'passed':
        execution.outputs.summary({'component': 'pve', 'operation': operation, 'status': result['overall'],
                                   'execution_id': execution_id})
        raise OperationFailed('snippet cleanup incomplete; inspect protected result')
    execution.finish({'component': 'pve', 'operation': operation, 'overall': result['overall'], 'execution_id': execution_id})
