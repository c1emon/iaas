"""Consume original protected records; do not infer ownership from filenames."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from iaas.common.errors import require
from iaas.pve_acceptance_contracts import (canonical_digest, load_strict_json,
    validate_acceptance_request, validate_snippet_cleanup_request)
from iaas.pve_template.acceptance_execution import confined, validate_acceptance_materials
from iaas.runtime_execution.pve_contracts import validate_execution_admission


def material(root: Path, ref: dict[str, Any]) -> dict[str, Any]:
    path = confined(root, ref['path'])
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'cleanup evidence digest conflict')
    value = load_strict_json(path)
    require(isinstance(value, dict), 'cleanup evidence must be an object')
    return value


def execution_materials(root: Path, refs: dict[str, Any], operation: str) -> tuple[dict, dict]:
    request, journal = material(root, refs['request']), material(root, refs['journal'])
    request = validate_acceptance_request(request) if operation == 'accept' else validate_snippet_cleanup_request(request)
    digest = canonical_digest(request)
    require(digest == refs['request_digest'] == journal.get('request_digest')
            and refs['execution_id'] == journal.get('execution_id')
            and journal.get('kind') == 'pve-one-shot-journal' and journal.get('schema_version') == 1
            and journal.get('deadlines') == request['deadlines']
            and journal.get('operation') == operation and journal.get('target') == request.get('target')
            and journal.get('mutation_active') is False, 'original execution binding or inactivity is unknown')
    if operation == 'accept':
        validate_acceptance_materials(request, journal)
    else:
        validate_execution_admission(journal.get('admission'), digest=digest.removeprefix('sha256:'),
                                     execution_id=refs['execution_id'], target=request['target'])
    require(journal['admission'].get('deadlines') == request['deadlines'],
            'original admission deadlines conflict')
    if refs['result'] is not None:
        result = material(root, refs['result'])
        require(journal.get('status') == 'finished' and journal.get('result_digest') == canonical_digest(result)
                and result.get('request_digest') == digest and result.get('execution_id') == refs['execution_id'],
                'original result binding conflicts')
        if operation == 'accept':
            require(result.get('preview_digest') == journal['preview_digest']
                    and result.get('runtime') == journal['runtime']
                    and result.get('cluster_scope') == request['cluster_scope']
                    and result.get('pool') == request['temporary_vm']['pool']
                    and result.get('vmid_policy') == request['vmid_policy'], 'original acceptance result snapshot conflicts')
    return request, journal


def _target_matches(actual: dict, expected: dict) -> bool:
    return (actual.get('api_endpoint') == expected['api_endpoint']
            # Deployment targets span nodes; the plan and snapshot bind the VM's node below.
            and ('node' not in actual or actual['node'] == expected['node'])
            and actual.get('tls_verify', not actual.get('insecure', True)) is True)


def validate_original(request: dict, root: Path) -> None:
    vm = request['original_vm']
    ownership = request['ownership_records']
    manifest, uploaded = material(root, ownership['manifest']), material(root, ownership['upload'])
    deletion = request['deletion_evidence']
    deleted, absent = material(root, deletion['result']), material(root, deletion['vm_absence'])
    original_id = request['original_execution_id']
    if request['origin'] == 'acceptance':
        original, journal = execution_materials(root, request['acceptance_evidence'], 'accept')
        require(original['authorization'] == {'create_temporary_vm': True, 'delete_temporary_resources': True}
                and original['target'] == request['target']
                and all(original['temporary_vm'].get(k) == vm[k] for k in ('node', 'vmid'))
                and all(journal.get('temporary_vm', {}).get(k) == v for k, v in vm.items()),
                'original acceptance ownership conflicts')
        expected_delete = journal.get('vm_delete', {})
        require(expected_delete.get('status') == 'deleted' and expected_delete.get('upid') == deletion['native_task']
                and expected_delete.get('execution_id') == original_id
                and all(expected_delete.get(k) == v for k, v in vm.items())
                and deleted == journal and absent == journal, 'acceptance deletion is unconfirmed')
        require(any(x.get('phase') == 'delete' and x.get('status') == 'succeeded'
                    and x.get('upid') == deletion['native_task'] for x in journal.get('tasks', []))
                and all(x.get('status') in {'succeeded', 'failed'} for x in journal.get('tasks', [])),
                'original acceptance task completion is unconfirmed')
        require(manifest == journal and uploaded == journal, 'acceptance ownership must reference original journal')
        records = journal.get('snippets', [])
        require(all(x.get('uploaded') is True for x in records), 'acceptance snippet upload is unconfirmed')
    else:
        plan = request['delete_plan']
        metadata = material(root, plan['metadata'])
        digest = plan['plan_digest'].removeprefix('sha256:')
        context = material(root, plan['admission'])
        require(context.get('execution_id') == deletion['execution_id'] and context.get('plan_sha256') == digest
                and context.get('target') == metadata.get('target'),
                'delete admission context conflicts')
        validate_execution_admission(context.get('execution_admission'), digest=digest,
                                     execution_id=deletion['execution_id'], target=metadata['target'])
        require(metadata.get('plan_digest') == digest and _target_matches(metadata.get('target', {}), request['target'])
                and deleted.get('plan_digest') == digest and deleted.get('execution_id') == deletion['execution_id']
                and deleted.get('target') == metadata['target']
                and deleted.get('native_execution', {}).get('status') == 'success'
                and deletion['native_task'] == 'opentofu-apply'
                and deleted.get('state_persistence', {}).get('status') == 'passed'
                and deleted.get('effects', {}).get('facility') == 'known'
                and deleted.get('collection', {}).get('status') == 'passed', 'original deployment deletion is unconfirmed')
        changes = [x for x in metadata.get('changes', []) if x.get('type') == 'proxmox_virtual_environment_vm'
                   and x.get('change', {}).get('actions') == ['delete']]
        candidates = [x['change']['before'] for x in changes if x['change']['before'].get('vm_id') == vm['vmid']
                      and x['change']['before'].get('node_name') == vm['node']]
        require(len(candidates) == 1 and any(x.get('uuid') == vm['smbios_uuid'] for x in candidates[0].get('smbios', [])),
                'delete plan native identity conflicts')
        require(absent == deleted and deleted.get('verification', {}).get('status') == 'passed'
                and any(x.get('node') == vm['node'] and x.get('vmid') == vm['vmid'] and x.get('absent') is True
                        and x.get('state_absent') is True and x.get('snapshot_complete') is True
                        for x in deleted.get('expectations', [])),
                'original VM absence is unconfirmed')
        state = deletion['state_persistence']
        require(material(root, state['result']) == deleted and deleted.get('backend') == state['backend']
                and deleted.get('backend') == metadata.get('backend')
                and deleted.get('root_id') == state['root_id'] == metadata.get('root_id')
                and deleted.get('state_after', {}).get('status') == 'present'
                and deleted.get('state_after', {}).get('workspace') == state['workspace']
                and all(deleted.get('state_after', {}).get(k) == state[k] for k in ('lineage', 'serial')),
                'original persisted state association conflicts')
        require(uploaded.get('execution_id') == original_id and uploaded.get('snippet_upload') == 'completed'
                and _target_matches(uploaded.get('target', {}), request['target'])
                and isinstance(manifest.get('plan_sha256'), str)
                and re.fullmatch(r'[0-9a-f]{64}', manifest['plan_sha256']) is not None
                and uploaded.get('plan_digest') == manifest['plan_sha256']
                and type(manifest.get('schema_version')) is int and manifest['schema_version'] == 1, 'original upload association conflicts')
        require(any(x.get('vmid') == vm['vmid'] and x.get('node') == vm['node']
                    and x.get('absent') is False and x.get('snapshot_complete') is True
                    and x.get('snapshot_identity') == 'passed'
                    and any(i.get('uuid') == vm['smbios_uuid'] for i in x.get('native_identity', []))
                    for x in uploaded.get('expectations', [])), 'original deployment native identity conflicts')
        require(all(snippet['storage'] == manifest.get('storage_id') for snippet in request['snippets']),
                'original manifest storage conflicts')
        records = manifest.get('snippets', [])
    require(isinstance(records, list), 'original ownership records missing')
    for snippet in request['snippets']:
        # Existing deployment manifests use file_name as a stable entry key.
        matches = [row for row in records if row.get('file_name') == snippet['record_ref']]
        require(len(matches) == 1, 'snippet original record is missing or ambiguous')
        row = matches[0]
        require(row.get('vmid') == vm['vmid'] and snippet['node'] == vm['node']
                and all(row.get(k) == snippet[k] for k in ('file_name', 'file_id', 'sha256')),
                'snippet original ownership conflicts')
    if request['retry_of'] is not None:
        previous, _ = execution_materials(root, request['retry_materials'], 'snippet-cleanup')
        # Path relocations are transport details: compare loaded evidence plus
        # original digests, while preserving every identity in the full list.
        ignored = {'timeout_seconds', 'retry_of', 'retry_materials', 'deadlines'}
        def resolved(value):
            if isinstance(value, dict):
                if set(value) == {'path', 'sha256'}:
                    return {'sha256': value['sha256'], 'material': material(root, value)}
                return {k: resolved(v) for k, v in value.items()}
            return [resolved(v) for v in value] if isinstance(value, list) else value
        require(resolved({k: v for k, v in previous.items() if k not in ignored}) ==
                resolved({k: v for k, v in request.items() if k not in ignored}), 'retry original scope conflicts')
