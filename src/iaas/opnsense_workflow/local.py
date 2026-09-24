"""Development-only native workflow, without building/publishing a runtime image.

Run from the checkout with ``PYTHONPATH=src uv run python -m
iaas.opnsense_workflow.local --help``.
Inject OPNSENSE_API_KEY/SECRET through the environment (for example op run).
The input YAML contains target, request and documents using existing contracts.
Outputs must be a new directory outside the checkout. Review candidate.json
before apply; an activation-check JSON must bind its digest, target and current
execution ID. Recovery is an explicit new plan using --recovery, never automatic.
Local results are development evidence, not release-image acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys

import yaml

from iaas.common.errors import require
from iaas.runtime_config.selection import runtime_platform
from iaas.runtime_execution.execution import Execution
from iaas.runtime_execution.outputs import TaskOutputs
from .contracts import RESULT_VERSION, load_candidate, request, save, selected_records
from .executor import apply, reverse_documents, verify
from .planning import coverage, plan
from .presentation import CONFIGURATION_SCOPE, display_result_metadata, project_observations
from .reader import Reader
from .writer import Writer


def source_identity(root: Path) -> dict:
    """Bind development candidates to the local implementation, including dirty edits."""
    digest = hashlib.sha256()
    paths = [root / 'pyproject.toml', root / 'uv.lock']
    for directory in ('src', 'automation/ansible'):
        paths.extend(path for path in (root / directory).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
    for path in sorted(paths):
        relative = str(path.relative_to(root)).encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, 'big') + relative)
        digest.update(len(data).to_bytes(8, 'big') + data)
    return {'kind': 'local-source', 'source_sha256': digest.hexdigest(),
            'platform': platform.system().lower() + '/' + runtime_platform().split('/')[-1],
            'interface_version': 1}


def run_local(args: argparse.Namespace) -> dict:
    root = Path(__file__).resolve().parents[3]
    spec = yaml.safe_load(args.input.read_text())
    require(isinstance(spec, dict) and not spec.keys() - {'target', 'request', 'documents'},
            'local input must contain only target, request and documents')
    runtime = source_identity(root)
    target = spec['target']
    include_system = getattr(args, 'include_system', False)
    require(type(include_system) is bool, 'local include_system must be a boolean')
    require(not include_system or args.operation == 'read',
            'include_system is only supported for read')
    candidate = {}
    digest = ''
    if args.operation in {'apply', 'verify'}:
        require(args.candidate is not None, 'candidate required')
        require(args.operation != 'apply' or bool(args.candidate_sha256), 'reviewed candidate digest required')
        candidate, digest = load_candidate(args.candidate, args.candidate_sha256)
        require(candidate['runtime'] == runtime and candidate['target'] == target,
                'local source or target changed; re-plan')
    if args.operation == 'apply':
        require(args.allow_test_writes, 'apply requires --allow-test-writes for the test device')
        require(isinstance(args.execution_id, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', args.execution_id),
                'current execution ID required')
        require(args.activation_check is not None, 'bound activation check required')
    inputs = [args.input, *[path for path in (args.candidate, args.activation_check, args.recovery) if path]]
    outputs = TaskOutputs.create(args.output, root, inputs)
    environ = dict(os.environ)
    environ['PYTHONPATH'] = str(root / 'src')
    environ['ANSIBLE_CONFIG'] = str(root / 'automation/ansible/ansible.cfg')
    # connection=local otherwise discovers a system Python without uv dependencies.
    environ['ANSIBLE_PYTHON_INTERPRETER'] = sys.executable
    environ['ANSIBLE_COLLECTIONS_PATH'] = str(root / 'automation/ansible/collections')
    environ['ANSIBLE_ROLES_PATH'] = str(root / 'automation/ansible/roles')
    environ['ANSIBLE_LOCAL_TEMP'] = str(outputs.path('work') / 'ansible-tmp')
    execution = Execution(outputs, environ)
    reader = Reader(target, environ)
    try:
        result = {'schema_version': RESULT_VERSION, 'kind': 'opnsense-result',
                  'operation': args.operation, 'target': target, 'runtime': runtime,
                  'candidate_sha256': digest, 'status': 'running',
                  'business_acceptance': 'not_performed'}
        if args.operation == 'read':
            req = request(spec['request'])
            complete = reader.read(list(req['selection']))
            save(outputs.path('diagnostics') / 'observations.json', complete)
            observations = project_observations(complete, req['selection'], include_system=include_system)
            result.update(status='complete' if all(x['status'] == 'complete' for x in complete.values()) else 'failed',
                          observations=observations, **display_result_metadata(observations))
        elif args.operation == 'plan':
            req = request(spec['request'])
            documents = spec.get('documents', {})
            if args.recovery:
                require(not documents, 'recovery and desired documents are mutually exclusive')
                documents = reverse_documents(json.loads(args.recovery.read_text()), req,
                                              reader.read(list(req['selection'])), target,
                                              allow_local_source=True)
            chosen = selected_records(documents, req['selection'])
            observations = reader.read(coverage(chosen))
            save(outputs.path('diagnostics') / 'observations.json', observations)
            result.update(observation_scope=CONFIGURATION_SCOPE, display_projection=False,
                          observations=observations)
            candidate = plan(documents, req, observations, target, runtime, {'inputs': [], 'mode': 'local-test'})
            digest = save(outputs.path('plan') / 'candidate.json', candidate)
            result.update(status='blocked' if candidate['admission']['status'] == 'blocked' else 'planned',
                          candidate_sha256=digest, differences=candidate['differences'],
                          admission=candidate['admission'])
        elif args.operation == 'verify':
            result.update(verify(candidate, reader), observation_scope=CONFIGURATION_SCOPE,
                          display_projection=False)
        else:
            result.update(apply(candidate, digest, reader, Writer(execution, target, documents=candidate['documents']),
                                args.execution_id, json.loads(args.activation_check.read_text()),
                                outputs.path('recovery'), check_mode=args.check_mode),
                          schema_version=RESULT_VERSION, kind='opnsense-result',
                          observation_scope=CONFIGURATION_SCOPE, display_projection=False)
        save(outputs.path('diagnostics') / 'result.json', result)
        outputs.summary({'status': result['status'], 'operation': args.operation, 'mode': 'local-test'})
        return result
    finally:
        reader.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('operation', choices=('read', 'plan', 'apply', 'verify'))
    parser.add_argument('--input', type=Path, required=True, help='YAML: target, request, documents')
    parser.add_argument('--output', type=Path, required=True, help='new private directory outside checkout')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--candidate-sha256')
    parser.add_argument('--execution-id')
    parser.add_argument('--activation-check', type=Path)
    parser.add_argument('--recovery', type=Path)
    parser.add_argument('--allow-test-writes', action='store_true')
    parser.add_argument('--check-mode', action='store_true')
    parser.add_argument('--include-system', action='store_true',
                        help='include confirmed system and derived objects in read output')
    args = parser.parse_args()
    try:
        require(args.recovery is None or args.operation == 'plan', 'recovery only supports plan')
        result = run_local(args)
    except Exception as error:
        # Parser, provider and validation exceptions can include private input values.
        parser.exit(2, f'local workflow failed ({type(error).__name__}); inspect private outputs\n')
    print(json.dumps({'status': result['status'], 'mode': 'local-test'}))
    if result['status'] in {'failed', 'blocked'}:
        parser.exit(1)


if __name__ == '__main__':
    main()
