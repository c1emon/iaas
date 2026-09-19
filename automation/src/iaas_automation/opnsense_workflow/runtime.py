"""Runtime entrypoint using existing selected files, credentials and private outputs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

import yaml

from iaas_automation.common.errors import require
from iaas_automation.runtime_config.selection import runtime_platform
from iaas_automation.runtime_execution.execution import OperationFailed
from .contracts import RESULT_VERSION, load_candidate, request, save, selected_records, selectors
from .executor import apply, reverse_documents, verify
from .planning import coverage, plan


def target_from_inventory(inventory: dict, scope: str) -> dict:
    require(isinstance(inventory, dict) and re.fullmatch(r'[A-Za-z0-9_.-]+', scope)
            and scope not in {'all', 'localhost', 'ungrouped'}, 'workflow needs exactly one explicit target')
    matches = []

    def visit(node: dict, inherited: dict, inside: bool = False) -> None:
        require(isinstance(node, dict), 'invalid static inventory group')
        values = {**inherited, **node.get('vars', {})}
        if inside and scope in node.get('hosts', {}):
            matches.append({**values, **(node['hosts'][scope] or {})})
        for name, child in node.get('children', {}).items():
            visit(child, values, inside or name == 'opnsense')

    if 'all' in inventory:
        visit(inventory['all'], {})
    if 'opnsense' in inventory:
        visit(inventory['opnsense'], inventory.get('all', {}).get('vars', {}), True)
    require(len(matches) == 1, 'scope must resolve exactly one OPNsense inventory host')
    host = matches[0].get('opnsense_api_host')
    tls = matches[0].get('opnsense_ssl_verify', True)
    require(isinstance(host, str) and host and '{{' not in host and type(tls) is bool,
            'workflow requires a literal API endpoint and boolean TLS verification')
    endpoint = host if '://' in host else 'https://' + host
    parsed = urlsplit(endpoint)
    require(parsed.scheme in {'http', 'https'} and parsed.hostname and parsed.username is None
            and parsed.password is None and parsed.path in {'', '/'} and not parsed.query and not parsed.fragment,
            'invalid workflow API endpoint')
    _ = parsed.port
    return {'host': scope, 'endpoint': endpoint.rstrip('/'), 'ssl_verify': tls}


def provenance(selected) -> dict:
    records = []
    for name, path in sorted(selected.input_paths.items()):
        physical = selected.reader.locate(path)
        git = {'status': 'unavailable', 'head': None, 'dirty': None}
        try:
            head = subprocess.run(['git', '-C', str(physical.parent), 'rev-parse', 'HEAD'],
                                  capture_output=True, text=True, timeout=5)
            dirty = subprocess.run(['git', '-C', str(physical.parent), 'status', '--porcelain'],
                                   capture_output=True, text=True, timeout=5)
            if head.returncode == dirty.returncode == 0:
                git = {'status': 'available', 'head': head.stdout.strip(), 'dirty': bool(dirty.stdout.strip())}
        except (OSError, subprocess.TimeoutExpired):
            pass
        records.append({'resource': name, 'logical_path': str(path), 'runtime_path': str(physical), 'git': git})
    return {'inputs': records, 'environment': selected.environment, 'scenario': selected.scenario}


def runtime_identity(image_digest: str) -> dict:
    require(isinstance(image_digest, str) and re.search(r'(?:^|@)sha256:[0-9a-f]{64}$', image_digest),
            'workflow requires the actual resolved runtime digest')
    return {'image_digest': image_digest, 'platform': runtime_platform(), 'interface_version': 1}


def read_selected(req: dict, reader) -> dict:
    observations = reader.read(list(req['selection']))
    for resource, entries in req['selection'].items():
        if entries != 'all':
            observations[resource]['objects'] = [obj for obj in observations[resource].get('objects', [])
                                                 if obj['identity'] in entries]
            observations[resource]['selected_identities'] = entries
    return observations


def run(selected, operation: str, scope: str, execution, image_digest: str) -> None:
    from .reader import Reader
    from .writer import Writer

    inventory = yaml.safe_load(selected.files['inventory'].read_text())
    target = target_from_inventory(inventory, scope)
    runtime = runtime_identity(image_digest)
    allowed_options = {'candidate_sha256', 'execution_id', 'activation_check', 'check_mode'} if operation == 'apply' else set()
    require(not selected.options.keys() - allowed_options, 'unknown workflow operation option')
    require(type(selected.options.get('check_mode', False)) is bool, 'workflow check_mode must be a boolean')
    directory = execution.outputs.path('recovery' if operation == 'apply' else 'plan' if operation == 'plan' else 'diagnostics')
    candidate = {}
    candidate_digest = ''
    req = {}
    if operation in {'read', 'plan'}:
        req = request(yaml.safe_load(selected.files['request'].read_text()))
        if operation == 'plan' and 'recovery' not in selected.files:
            selected_records(selected.documents, req['selection'])
    else:
        candidate, candidate_digest = load_candidate(selected.files['candidate'],
                                                      selected.options.get('candidate_sha256') if operation == 'apply' else None)
        require(candidate['target'] == target and candidate['runtime'] == runtime, 'candidate target or runtime mismatch')
        if operation == 'apply':
            require(isinstance(selected.options.get('candidate_sha256'), str), 'apply needs a reviewed candidate digest')
    base = {'schema_version': RESULT_VERSION, 'kind': 'opnsense-result', 'operation': operation, 'target': target,
            'runtime': runtime, 'candidate_sha256': candidate_digest, 'status': 'running', 'business_acceptance': 'not_performed'}
    save(directory / 'result.json', base)
    reader = Reader(target, execution.environ)
    try:
        if operation == 'read':
            observations = read_selected(req, reader)
            base.update(observations=observations, status='complete' if all(
                value['status'] == 'complete' for value in observations.values()) else 'failed')
        elif operation == 'plan':
            documents = selected.documents
            if 'recovery' in selected.files:
                require(not documents, 'recovery and desired inputs are mutually exclusive')
                recovery = json.loads(selected.files['recovery'].read_bytes())
                selectors(req['selection'])
                observed = reader.read(list(req['selection']))
                documents = reverse_documents(recovery, req, observed, target)
            chosen = selected_records(documents, req['selection'])
            observations = reader.read(coverage(chosen))
            base['observations'] = observations
            try:
                candidate = plan(documents, req, observations, target, runtime, provenance(selected))
            except Exception:
                base.update(status='failed', differences=[{'resource': item['resource'], 'identity': item['identity'], 'action': 'unknown'}
                                                        for item in chosen])
                save(directory / 'result.json', base)
                raise
            candidate_digest = save(directory / 'candidate.json', candidate)
            from iaas_automation.common.io import write_text
            write_text(directory / 'candidate.sha256', candidate_digest + '\n', secure=True)
            base.update(status='blocked' if candidate['admission']['status'] == 'blocked' else 'planned',
                        admission=candidate['admission'], candidate_sha256=candidate_digest,
                        candidate_file=str(directory / 'candidate.json'), differences=candidate['differences'])
        elif operation == 'verify':
            base.update(verify(candidate, reader))
        else:
            execution_id = selected.options.get('execution_id')
            require(isinstance(execution_id, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', execution_id),
                    'apply needs an explicit current execution identity')
            writer = Writer(execution, target, documents=candidate['documents'])
            base = apply(candidate, candidate_digest, reader, writer, execution_id,
                         selected.options.get('activation_check', {}), directory,
                         check_mode=selected.options.get('check_mode', False))
        save(directory / 'result.json', base)
        execution.outputs.summary({'component': 'opnsense', 'operation': operation, 'scope': scope,
                                   'status': base['status'], 'result': str(directory / 'result.json'),
                                   'retain_storage': base.get('retain_storage', False), 'phases': execution.phases})
        if base['status'] in {'failed', 'blocked'}:
            if base.get('retain_storage'):
                execution.phases.append({'phase': 'opnsense-recovery', 'exit_code': 2,
                                         'retain_storage': True, 'capture_complete': False})
            raise OperationFailed('OPNsense workflow failed; inspect protected result and recovery')
    finally:
        reader.close()
