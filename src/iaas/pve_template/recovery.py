"""Newly authorized exact cleanup; original acceptance is immutable evidence."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import quote

from iaas.common.errors import require
from iaas.observation import Decision, EvidenceSink, observe as observe_state, task_decision, safe_facts
from .responses import read_retry_decision
from iaas.pve_acceptance_contracts import canonical_digest, load_strict_json
from iaas.runtime_execution.execution import OperationFailed
from .acceptance_execution import confined, save
from .admission import AdmissionError
from .deadlines import DeadlineBudget, DeadlineExpired, LocalTimeout
from .one_shot_admission import validate_one_shot_admission
from .recovery_contracts import validate_recovery_request, validate_recovery_preview, validate_recovery_result
from .recovery_evidence import load_original, reconcile_original, inspect_resources, RecoveryEvidenceError
from . import runtime as pve


class RecoveryFailure(OperationFailed):
    pass


def trusted_sources(request: dict) -> dict:
    return {row['source_id']: {'sha256': row['material']['sha256'], 'provenance': row['provenance']}
            for row in request['rejection_evidence'] if row['authorize_trusted_source'] is True}


def resource_rows(request: dict) -> list[dict]:
    full, original = request['full_original_resources'], request['original_execution_id']
    vm = full['vm']
    identities = [('vm', vm['node'], str(vm['vmid']))] + [('volume', vm['node'], v) for v in full['volumes']]
    identities += [('snippet', s['node'], s['file_id']) for s in full['snippets']]
    return [{'kind': kind, 'node': node, 'identity': identity, 'created_by': original,
             'status': 'unknown', 'existence': 'unknown', 'reason_code': 'not_checked'}
            for kind, node, identity in identities]


class Recovery:
    def __init__(self, request: dict, preview: dict, journal: dict, originals: dict, root: Path,
                 original_root: Path, evidence_root: Path, client: Any, snippets: Any, budget: DeadlineBudget):
        self.inputs, self.preview, self.journal = request, preview, journal
        self.originals, self.root, self.original_root, self.evidence_root = originals, root, original_root, evidence_root
        self.client, self.snippets, self.budget = client, snippets, budget
        self.vm = request['full_original_resources']['vm']
        self.base = f"/api2/json/nodes/{quote(self.vm['node'], safe='')}/qemu/{self.vm['vmid']}"
        self.phase = 'work'
        self.observations = EvidenceSink()
        # Both relative bounds use this start reference; entering cleanup does
        # not grant fresh time or extend the absolute/monotonic bounds.
        budget.limit('work', request['timeouts']['work_seconds'])
        budget.limit('cleanup', request['timeouts']['cleanup_seconds'])
        self.configure_helper()
        old = originals['journal']
        self.result = {'kind': 'pve-acceptance-recovery-result', 'schema_version': 2,
                       'execution_id': journal['execution_id'], 'original_execution_id': request['original_execution_id'],
                       'recovery_of': request['original_execution_id'], 'request_digest': canonical_digest(request),
                       'preview_digest': preview['preview_digest'], 'runtime': request['runtime'], 'deadlines': request['deadlines'],
                       'full_original_resources': request['full_original_resources'],
                       'caller_association': request['caller_association'], 'original_materials': request['original_materials'],
                       'previous_recoveries': request['previous_recoveries'], 'original_request_digest': old['request_digest'],
                       'original_runtime': old['runtime'], 'original_deadlines': old['deadlines'],
                       'original_acceptance': originals['result'].get('overall', 'unknown') if originals['result'] else 'unknown',
                       'original_activity': 'unknown', 'original_facility_writes': old['facility_writes'],
                       'facility_writes': 'none', 'reconciliation': {}, 'resources': resource_rows(request),
                       'cleanup': {'status': 'unknown'}, 'collection': {'status': 'complete'},
                       'residuals': [], 'overall': 'unknown', 'deadline_outcome': dict(budget.outcome),
                       'reason_code': 'not_completed'}

    def configure_helper(self):
        self.snippets.budget, self.snippets.phase = self.budget, self.phase
        self.snippets.deadline = min(self.budget.bounds[self.phase], self.budget.local[self.phase])
        self.snippets.original_vmid = self.vm['vmid']

    def persist(self):
        save(self.root / 'journal.json', self.journal)

    def remaining(self):
        return self.budget.remaining(self.phase)

    def api(self, method, path, *, fields=None):
        remaining = self.remaining()
        if hasattr(self.client, 'timeout'):
            self.client.timeout = remaining
        return self.client.request(method, path, fields=fields)

    def inspect(self):
        self.remaining()
        self.configure_helper()
        # Every relevant ownership/reference query is GET-only. Deadline is
        # checked again before a dependent mutation is durably recorded.
        current = inspect_resources(self.inputs, self, self.snippets)
        proof = self.preview['proof_bindings']
        if proof['mode'] == 'pre_registration' and current['vm']['existence'] == 'present':
            from .acceptance import attachments
            config = self.api('GET', self.base + '/config')
            require(isinstance(config, dict) and config.get('description') == proof['clone_marker']
                    and pve._config_uuid(config) == proof['smbios_uuid']
                    and attachments(config) == proof['slots'], 'recovery_candidate_identity_changed')
        return current

    def request(self, method, path, *, fields=None):
        require(method == 'GET', 'recovery inspection forbids mutation')
        return self.api(method, path, fields=fields)

    def mutation(self, phase: str, method: str, path: str, *, fields=None):
        self.remaining()
        previous = self.journal['facility_writes']
        item = {'phase': phase, 'method': method, 'path': path, 'node': self.vm['node'], 'status': 'intent'}
        self.journal['tasks'].append(item)
        self.journal.update(mutation_active=True, facility_writes='unknown')
        self.persist()
        try:
            try:
                self.remaining()
            except (DeadlineExpired, LocalTimeout):
                item['status'] = 'not_sent'
                self.journal.update(mutation_active=False, facility_writes=previous)
                self.persist()
                raise
            response = self.api(method, path, fields=fields)
            item['upid'] = pve._normalize_upid(response, self.vm['node'])
            item['status'] = 'running'
            self.journal['facility_writes'] = 'unknown' if previous == 'unknown' else 'issued'
            self.persist()
            decision = observe_state(lambda timeout: self.api('GET', f"/api2/json/nodes/{quote(self.vm['node'], safe='')}/tasks/{quote(item['upid'], safe='')}/status"),
                                     task_decision, self.budget, self.phase, 'native_task', {'upid': item['upid']},
                                     self.observations, interval=.2, retry_error=read_retry_decision)
            if decision.status in {'ready', 'failed'}:
                item['status'] = 'succeeded' if decision.status == 'ready' else 'failed'
                self.journal['mutation_active'] = False
                self.persist()
            if decision.status != 'ready':
                raise RecoveryFailure('recovery_task_failed' if decision.status == 'failed' else 'recovery_task_unknown')
            return
        except pve.RequestRejected as exc:
            item.update(status='rejected', http_status=exc.http_status)
            self.journal.update(mutation_active=False, facility_writes=previous)
            self.persist()
            raise RecoveryFailure('request_rejected') from None
        except (RecoveryFailure, DeadlineExpired, LocalTimeout):
            # A cutoff while a submitted task is running does not cancel it.
            if item['status'] == 'running':
                item['status'] = 'unknown'
                self.journal.update(mutation_active=True, facility_writes='unknown')
                self.persist()
            raise
        except Exception:
            item['status'] = 'unknown'
            self.journal.update(mutation_active=True, facility_writes='unknown')
            self.persist()
            raise RecoveryFailure('recovery_request_outcome_unknown') from None

    def mark(self, kind: str, identity: str, status: str, existence: str, reason: str):
        row = next(r for r in self.result['resources'] if r['kind'] == kind and r['identity'] == identity)
        row.update(status=status, existence=existence, reason_code=reason)
        self.journal['resources'] = deepcopy(self.result['resources'])
        self.persist()

    def reconcile(self):
        self.remaining()
        self.configure_helper()
        reviewed = self.preview['reconciliation']
        frozen = self.preview['proof_bindings'] if (reviewed.get('cleanup_eligible') is True
            and reviewed.get('resources', {}).get('ownership') == 'confirmed'
            and reviewed.get('resources', {}).get('vm', {}).get('existence') == 'present'
            and all(v.get('existence') == 'present' for v in reviewed.get('resources', {}).get('volumes', []))
            and reviewed.get('source_observation', {}).get('status') == 'unchanged') else None
        facts = reconcile_original(self.inputs, self.original_root, self.evidence_root, self, self.snippets,
                                   trusted_rejection_exports=trusted_sources(self.inputs), approved_frozen_proof=frozen)
        require(facts.get('proof_bindings') == self.preview['proof_bindings'],
                'recovery_preview_proof_drift')
        self.journal['proof_bindings'] = facts['proof_bindings']
        self.result.update(reconciliation=facts, original_activity=facts['original_activity'],
                           original_facility_writes=facts['original_facility_writes'])
        self.journal['reconciliation'] = facts
        self.persist()
        if facts['cleanup_eligible'] is not True:
            raise RecoveryFailure('recovery_reconciliation_unknown')
        return facts

    def wait_absence(self, kind, identity):
        sampled = {}
        def classify(current):
            sampled.update(current)
            if current['ownership'] != 'confirmed':
                return Decision('failed', 'recovery_ownership_conflict')
            row = current['vm'] if kind == 'vm' else next(r for r in current[kind + 's'] if r['identity'] == identity)
            absent = row['existence'] == 'absent'
            return Decision('ready' if absent else 'pending', 'resource_absent' if absent else 'resource_still_present',
                            {'absent': absent, 'complete': True})
        decision = observe_state(lambda timeout: self.inspect(), classify, self.budget, self.phase,
                                 kind + '_absence', {'vmid': self.vm['vmid'], 'volid': identity} if kind == 'volume' else {'vmid': self.vm['vmid']},
                                 self.observations, interval=.2, retry_error=read_retry_decision)
        self.journal['observations'] = self.observations.rows()
        self.persist()
        if decision.status != 'ready':
            raise RecoveryFailure('recovery_absence_unknown' if decision.status == 'unknown' else decision.reason)
        return sampled

    def cleanup(self):
        self.phase = 'cleanup'
        self.configure_helper()
        current = self.inspect()
        require(current['ownership'] == 'confirmed', 'recovery_ownership_conflict')
        present = current['vm']['existence'] == 'present'
        attached_before_delete = {row['identity'] for row in current['volumes'] if row['existence'] == 'present'}
        vm_delete_confirmed = False
        if present:
            config = self.api('GET', self.base + '/config')
            require(isinstance(config, dict) and not config.get('lock'), 'recovery_vm_locked')
            state = self.api('GET', self.base + '/status/current')
            require(isinstance(state, dict) and state.get('status') in {'running', 'stopped'}, 'recovery_vm_status_unknown')
            if state['status'] == 'running':
                self.mutation('stop', 'POST', self.base + '/status/stop')
            # UUID, the complete disk set, historical pool and references are
            # rechecked after stop and before exact deletion.
            current = self.inspect()
            require(current['ownership'] == 'confirmed' and current['vm']['existence'] == 'present',
                    'recovery_ownership_conflict')
            self.mutation('delete', 'DELETE', self.base, fields={'purge': 0, 'destroy-unreferenced-disks': 0})
            current = self.wait_absence('vm', str(self.vm['vmid']))
            vm_delete_confirmed = True
            self.mark('vm', str(self.vm['vmid']), 'deleted', 'absent', 'new_execution_delete_confirmed')
        else:
            self.mark('vm', str(self.vm['vmid']), 'already_absent', 'absent', 'current_absence_observed')
        for volume in self.inputs['full_original_resources']['volumes']:
            current = self.inspect()
            require(current['ownership'] == 'confirmed' and current['vm']['existence'] == 'absent',
                    'recovery_volume_ownership_conflict')
            row = next(r for r in current['volumes'] if r['identity'] == volume)
            if row['existence'] == 'absent':
                if vm_delete_confirmed and volume in attached_before_delete:
                    self.mark('volume', volume, 'deleted', 'absent', 'vm_delete_volume_absence_confirmed')
                else:
                    self.mark('volume', volume, 'already_absent', 'absent', 'current_absence_observed')
                continue
            storage = volume.split(':', 1)[0]
            path = f"/api2/json/nodes/{quote(self.vm['node'], safe='')}/storage/{quote(storage, safe='')}/content/{quote(volume, safe='')}"
            self.mutation('volume_delete', 'DELETE', path)
            current = self.wait_absence('volume', volume)
            self.mark('volume', volume, 'deleted', 'absent', 'new_execution_delete_confirmed')
        for snippet in self.inputs['full_original_resources']['snippets']:
            current = self.inspect()
            require(current['ownership'] == 'confirmed' and current['vm']['existence'] == 'absent'
                    and all(v['existence'] == 'absent' for v in current['volumes']), 'recovery_snippet_predecessors_unconfirmed')
            row = next(r for r in current['snippets'] if r['identity'] == snippet['file_id'])
            require(row['referenced'] is False and row['ownership'] == 'confirmed', 'recovery_snippet_referenced')
            if row['existence'] == 'absent':
                self.mark('snippet', snippet['file_id'], 'already_absent', 'absent', 'current_absence_observed')
                continue
            transport = {**snippet, 'storage': snippet['file_id'].split(':', 1)[0],
                         'file_name': snippet['file_id'].split('/', 1)[1], 'vmid': self.vm['vmid']}
            self.remaining()
            previous = self.journal['facility_writes']
            task = {'phase': 'snippet_delete', 'status': 'intent', 'node': snippet['node'], 'identity': snippet['file_id']}
            self.journal['tasks'].append(task)
            self.journal.update(mutation_active=True, facility_writes='unknown')
            self.persist()
            try:
                self.remaining()
            except (DeadlineExpired, LocalTimeout):
                task['status'] = 'not_sent'
                self.journal.update(mutation_active=False, facility_writes=previous)
                self.persist()
                raise
            try:
                response = self.snippets.delete(transport)
                require(isinstance(response, dict) and response.get('status') in {'deleted', 'already_absent'},
                        'recovery_snippet_delete_unconfirmed')
                task['status'] = 'succeeded'
                self.journal.update(mutation_active=False, facility_writes=(previous if response['status'] == 'already_absent' else
                    'issued' if previous != 'unknown' else 'unknown'))
                self.persist()
            except Exception:
                task['status'] = 'unknown'
                self.persist()
                raise RecoveryFailure('recovery_snippet_outcome_unknown') from None
            current = self.wait_absence('snippet', snippet['file_id'])
            self.mark('snippet', snippet['file_id'], 'already_absent' if response['status'] == 'already_absent' else 'deleted',
                      'absent', 'current_absence_observed' if response['status'] == 'already_absent' else 'new_execution_delete_confirmed')

    def execute(self):
        try:
            self.budget.admit()
            self.reconcile()
            self.cleanup()
            self.result.update(overall='passed', cleanup={'status': 'passed'}, reason_code='recovery_cleanup_confirmed')
        except Exception as exc:
            if isinstance(exc, AdmissionError):
                self.result['reconciliation']['permission_diagnostic'] = dict(exc.diagnostic)
            uncertain = self.journal['facility_writes'] == 'unknown' or self.journal['mutation_active']
            uncertain = uncertain or str(exc) == 'recovery_reconciliation_unknown'
            self.result.update(overall='unknown' if uncertain else 'failed', cleanup={'status': 'unknown' if uncertain else 'failed'},
                               reason_code=exc.reason_code if isinstance(exc, AdmissionError) else
                               str(exc) if isinstance(exc, (RecoveryFailure, RecoveryEvidenceError, DeadlineExpired, LocalTimeout)) else 'recovery_cleanup_failed')
        self.result['facility_writes'] = self.journal['facility_writes']
        self.result['deadline_outcome'] = dict(self.budget.outcome)
        self.result['residuals'] = [deepcopy(r) for r in self.result['resources'] if r['existence'] != 'absent']
        self.result['stop_diagnostics'] = {
            'completed': [r['kind'] + ':' + r['identity'] for r in self.result['resources'] if r['existence'] == 'absent'],
            'stopping': None if self.result['overall'] == 'passed' else {'phase': self.phase, 'check': 'recovery_cleanup',
                        'status': self.result['overall'], 'reason_code': self.result['reason_code']},
            'facility_writes': self.journal['facility_writes'], 'activity': 'unknown' if self.journal['mutation_active'] else 'stopped',
            'ownership': 'registered-owned' if self.result['reconciliation'].get('cleanup_eligible') else 'candidate-unknown',
            'existence': next((r['existence'] for r in self.result['resources'] if r['kind'] == 'vm'), 'unknown'),
            'inventory_complete': all(r['existence'] != 'unknown' for r in self.result['resources']),
            'tasks': [safe_facts(t) for t in self.journal['tasks']], 'observations': self.observations.rows(),
            'recovery': {'supported': True, 'disposition': 'not_applicable' if self.result['overall'] == 'passed' else 'needs_evidence',
                         'reason_code': 'independent_recovery_inspection_required', 'required_evidence': [] if self.result['overall'] == 'passed' else ['previous_recovery_materials', 'current_activity', 'frozen_scope']}}
        self.result = validate_recovery_result(self.result)
        try:
            save(self.root / 'result.json', self.result)
            self.journal.update(status='finished', result_digest=canonical_digest(self.result))
            self.persist()
        except Exception:
            # Collection cannot manufacture cleanup success after a lost write.
            self.result.update(overall='unknown', collection={'status': 'incomplete'}, reason_code='recovery_collection_failed')
            self.journal.update(status='collection_failed', result_digest=None)
            try:
                self.persist()
            except Exception:
                pass
        return self.result


def start(root: Path, request: dict, preview: dict, admission: dict, execution_id: str,
          image_digest: str, original_root: Path, evidence_root: Path, client: Any, snippets: Any) -> dict:
    request = validate_recovery_request(request)
    preview = validate_recovery_preview(preview)
    require(preview['fixed_input'] == request, 'recovery preview request conflicts')
    admission = validate_one_shot_admission(admission, request=request, preview=preview,
                execution_id=execution_id, image_digest=image_digest, vmids=[request['full_original_resources']['vm']['vmid']],
                recovery_of=request['original_execution_id'])
    originals = load_original(request, original_root, evidence_root)
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    (root / 'started').touch(mode=0o600, exist_ok=False)
    journal = {'kind': 'pve-acceptance-recovery-journal', 'schema_version': 1, 'operation': 'recover',
               'execution_id': execution_id, 'original_execution_id': request['original_execution_id'],
               'request_digest': canonical_digest(request), 'preview_digest': preview['preview_digest'],
               'runtime': request['runtime'], 'deadlines': request['deadlines'], 'target': request['target'],
               'admission': admission, 'original_request_digest': originals['journal']['request_digest'],
               'original_runtime': originals['journal']['runtime'], 'original_deadlines': originals['journal']['deadlines'],
               'tasks': [], 'resources': resource_rows(request),
               'mutation_active': False, 'facility_writes': 'none', 'status': 'running'}
    for filename, value in [('request.json', request), ('preview.json', preview), ('journal.json', journal)]:
        save(root / filename, value)
    budget = DeadlineBudget(request['deadlines'])
    return Recovery(request, preview, journal, originals, root, original_root, evidence_root, client, snippets, budget).execute()


def observe(root: Path, execution_id: str, request: dict | None = None) -> tuple[dict, dict | None]:
    """Local collection only. No budgets, client, credentials or start fallback."""
    original = validate_recovery_request(load_strict_json(confined(root, 'request.json')))
    preview = validate_recovery_preview(load_strict_json(confined(root, 'preview.json')))
    journal = load_strict_json(confined(root, 'journal.json'))
    require(isinstance(journal, dict) and journal.get('kind') == 'pve-acceptance-recovery-journal'
            and journal.get('schema_version') == 1 and journal.get('operation') == 'recover'
            and journal.get('execution_id') == execution_id and preview['fixed_input'] == original
            and journal.get('request_digest') == canonical_digest(original)
            and journal.get('preview_digest') == preview['preview_digest']
            and journal.get('runtime') == original['runtime'] and journal.get('deadlines') == original['deadlines']
            and journal.get('original_execution_id') == original['original_execution_id'], 'recovery observation binding conflicts')
    if request is not None:
        require(validate_recovery_request(request) == original, 'recovery observation request conflicts')
    validate_one_shot_admission(journal['admission'], request=original, preview=preview,
               execution_id=execution_id, image_digest=original['runtime']['image_digest'],
               vmids=[original['full_original_resources']['vm']['vmid']], recovery_of=original['original_execution_id'])
    result = None
    if (root / 'result.json').exists():
        result = validate_recovery_result(load_strict_json(confined(root, 'result.json')))
        require(result['execution_id'] == execution_id and result['request_digest'] == journal['request_digest']
                and result['preview_digest'] == journal['preview_digest'] and result['runtime'] == journal['runtime']
                and result['deadlines'] == journal['deadlines'] and result['full_original_resources'] == original['full_original_resources']
                and result['original_execution_id'] == original['original_execution_id']
                and all(result[key] == original[key] for key in ('caller_association', 'original_materials', 'previous_recoveries'))
                and all(result[key] == journal[key] for key in ('original_request_digest', 'original_runtime', 'original_deadlines'))
                and result['facility_writes'] == journal['facility_writes']
                and journal.get('result_digest') == canonical_digest(result), 'recovery result observation conflicts')
    return journal, result


def plan(request: dict, original_root: Path, evidence_root: Path, client: Any, snippets: Any) -> dict:
    """Read-only online plan; it neither consumes approval nor creates a journal."""
    from .recovery_contracts import build_recovery_preview
    request = validate_recovery_request(request)
    budget = DeadlineBudget(request['deadlines'])
    budget.limit('work', request['timeouts']['work_seconds'])
    budget.admit()
    snippets.budget, snippets.phase = budget, 'work'
    snippets.deadline = min(budget.bounds['work'], budget.local['work'])
    snippets.original_vmid = request['full_original_resources']['vm']['vmid']
    class Reader:
        def request(self, method, path, *, fields=None):
            require(method == 'GET', 'recovery plan forbids mutation')
            remaining = budget.remaining('work')
            if hasattr(client, 'timeout'):
                client.timeout = remaining
            return client.request(method, path, fields=fields)
    facts = reconcile_original(request, original_root, evidence_root, Reader(), snippets,
                               trusted_rejection_exports=trusted_sources(request))
    budget.remaining('work')
    return build_recovery_preview(request, facts)


def run(selected: Any, operation: str, scope: str, execution: Any,
        image_digest: str, execution_id: str = '') -> None:
    """Launcher adapter. Observe never creates clients, helpers or budgets."""
    files, options = selected.files, selected.options
    request_path = files.get('recovery_request')
    request = validate_recovery_request(load_strict_json(Path(request_path))) if request_path else None
    if request is not None:
        require(not scope or scope == request['target']['node'], 'recovery scope conflicts')
    if operation == 'check':
        require(request is not None, 'recovery_request is required')
        assert request is not None
        execution.finish({'component': 'pve-template', 'operation': 'check', 'action': 'recover',
                          'request_digest': canonical_digest(request), 'network': False, 'facility_writes': 'none',
                          'evidence_mode': request.get('evidence_mode', 'derived_online'),
                          'resource_ownership': 'not_observed', 'cleanup_eligible': 'not_observed'})
        return
    root = execution.outputs.path('work') / 'pve-recovery'
    mode = options.get('execution_mode')
    if operation == 'plan':
        require(request is not None, 'recovery_request is required')
        mode = 'plan'
    require(mode in {'plan', 'start', 'observe'}, 'explicit recovery execution_mode required')
    require('original_execution_dir' in files, 'original_execution_dir is required')
    original_root = Path(files['original_execution_dir'])
    output_root = execution.outputs.root.resolve()
    require(not output_root.is_relative_to(original_root.resolve()) and not original_root.resolve().is_relative_to(output_root),
            'recovery output must not overlap original protected evidence')
    if mode == 'observe':
        try:
            journal, result = observe(original_root, execution_id, request)
            require(not scope or scope == journal['target']['node'], 'recovery observation scope conflicts')
        except Exception:
            execution.outputs.summary({'component': 'pve-template', 'operation': 'recover', 'overall': 'unknown',
                                       'reason_code': 'recovery_observation_unavailable', 'facility_writes': 'none'})
            raise OperationFailed('recovery observation unavailable; no mutation performed') from None
        for name in ('request.json', 'preview.json'):
            save(root / name, load_strict_json(confined(original_root, name)))
        save(root / 'journal.json', journal)
        if result is None:
            execution.outputs.summary({'component': 'pve-template', 'operation': 'recover', 'overall': 'unknown',
                                       'reason_code': 'recovery_result_missing', 'facility_writes': journal['facility_writes']})
            raise OperationFailed('recovery result incomplete; no mutation performed')
        save(root / 'result.json', result)
    else:
        require(request is not None and 'cleanup_evidence_dir' in files, 'recovery bound materials required')
        assert request is not None
        require(request['runtime'] == {'image_digest': image_digest}, 'recovery runtime conflicts')
        evidence_root = Path(files['cleanup_evidence_dir'])
        require(not output_root.is_relative_to(evidence_root.resolve()) and not evidence_root.resolve().is_relative_to(output_root),
                'recovery output must not overlap cleanup evidence')
        try:
            originals = load_original(request, original_root, evidence_root)
        except RecoveryEvidenceError as exc:
            needs = str(exc) in {'pre_registration_needs_evidence', 'pre_registration_absent_needs_frozen_scope'}
            execution.outputs.summary({'component': 'pve-template', 'operation': operation, 'overall': 'unknown',
                'facility_writes': 'none', 'recovery': {'supported': True,
                'disposition': 'needs_evidence' if needs else 'blocked', 'reason_code': str(exc),
                'required_evidence': ['original_marker_and_clone_task', 'complete_candidate_scope'] if needs else ['consistent_original_materials']}})
            raise OperationFailed(str(exc)) from None
        client = pve._client(selected, execution, request['target'])
        from .acceptance_snippets import Snippets
        helper = Snippets(selected, execution, request['timeouts']['work_seconds'], originals['request']['cloud_init']['ssh'])
        if mode == 'plan':
            preview = plan(request, original_root, evidence_root, client, helper)
            save(execution.outputs.path('plan') / 'recovery-preview.json', preview)
            execution.finish({'component': 'pve-template', 'operation': 'plan', 'action': 'recover',
                              'preview_digest': preview['preview_digest'],
                              'disposition': preview['reconciliation']['disposition'],
                              'cleanup_eligible': preview['reconciliation']['cleanup_eligible'], 'facility_writes': 'none'})
            return
        require('recovery_preview' in files, 'recovery_preview is required')
        preview = load_strict_json(Path(files['recovery_preview']))
        admission_path = files.get('execution_admission')
        admission = load_strict_json(Path(admission_path)) if admission_path else options.get('admission')
        result = start(root, request, preview, admission, execution_id, image_digest,
                       original_root, evidence_root, client, helper)
    try:
        save(execution.outputs.path('diagnostics') / 'recovery-result.json', result)
    except Exception:
        result.update(overall='unknown', collection={'status': 'incomplete'}, reason_code='recovery_collection_failed')
        save(root / 'result.json', result)
        journal = load_strict_json(confined(root, 'journal.json'))
        journal.update(status='collection_failed', result_digest=canonical_digest(result))
        save(root / 'journal.json', journal)
        raise OperationFailed('recovery result collection failed; inspect protected evidence') from None
    execution.outputs.summary({'component': 'pve-template', 'operation': 'recover',
                               'execution_id': result['execution_id'], 'overall': result['overall'],
                               'stop_diagnostics': result['stop_diagnostics']})
    if result['overall'] != 'passed':
        raise OperationFailed('recovery cleanup remains failed or unknown; inspect protected result')
    execution.finish({'component': 'pve-template', 'operation': 'recover', 'execution_id': result['execution_id'],
                      'original_execution_id': result['original_execution_id'], 'overall': result['overall'],
                      'original_acceptance': result['original_acceptance'], 'facility_writes': result['facility_writes'],
                      'stop_diagnostics': result['stop_diagnostics']})
