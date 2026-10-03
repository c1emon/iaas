"""Bounded read-only acceptance plans; static check needs no credentials."""
from __future__ import annotations

from typing import Any
from pathlib import Path

from iaas.common.errors import require
from iaas.common.config_checks import checked_input
from iaas.pve_acceptance_contracts import AcceptancePreview, canonical_digest, load_strict_json, validate_acceptance_request


class ReadBudgetClient:
    """Keep each admission query within the same frozen work budget."""
    def __init__(self, client: Any, budget: Any):
        self.client, self.budget = client, budget
        self.token = getattr(client, 'token', None)
        self.principal = getattr(client, 'principal', None)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        require(method == 'GET', 'admission must be read-only')
        self.client.timeout = min(30, self.budget.remaining('work'))
        return self.client.request(method, path, **kwargs)


def build_preview(request: dict, observed: dict, *, image_digest: str) -> dict:
    request = validate_acceptance_request(request)
    require(request['runtime'] == {'image_digest': image_digest}, 'acceptance plan runtime conflicts')
    require(observed.get('readiness', {}).get('status') == 'ready', 'acceptance admission incomplete')
    preview = {'kind': 'pve-template-acceptance-preview', 'schema_version': 1,
               'fixed_input': request, 'request_digest': canonical_digest(request),
               'runtime': request['runtime'], 'target': request['target'],
               'observed': observed, 'facility_writes': 'none'}
    preview['preview_digest'] = canonical_digest(preview)
    return preview


def validate_preview(value: Any, *, request: dict | None = None) -> dict:
    try:
        AcceptancePreview.model_validate(value)
    except Exception:
        raise ValueError('invalid acceptance preview contract') from None
    require(isinstance(value, dict) and set(value) == {'kind', 'schema_version', 'fixed_input',
            'request_digest', 'runtime', 'target', 'observed', 'facility_writes', 'preview_digest'},
            'invalid acceptance preview')
    require(value['kind'] == 'pve-template-acceptance-preview' and type(value['schema_version']) is int
            and value['schema_version'] == 1 and value['facility_writes'] == 'none', 'invalid acceptance preview version/effects')
    fixed = validate_acceptance_request(value['fixed_input'])
    require(value['request_digest'] == canonical_digest(fixed) and value['target'] == fixed['target']
            and value['runtime'] == fixed['runtime'], 'acceptance preview input binding conflicts')
    require(value['preview_digest'] == canonical_digest({k: v for k, v in value.items() if k != 'preview_digest'}),
            'acceptance preview digest conflicts')
    require(isinstance(value['observed'], dict) and value['observed'].get('readiness', {}).get('status') == 'ready',
            'acceptance preview admission incomplete')
    if request is not None:
        require(canonical_digest(request) == value['request_digest'], 'acceptance preview selected request conflicts')
    return value


def run_plan(selected: Any, execution: Any, operation: str, image_digest: str) -> None:
    from . import runtime, acceptance_snippets
    from .admission import admit_acceptance
    from .deadlines import DeadlineBudget
    from .acceptance_execution import save

    require(operation in {'check', 'plan'}, 'invalid acceptance planning operation')
    path = selected.files.get('acceptance_request')
    require(path is not None, 'acceptance_request required')
    document = load_strict_json(Path(path))
    request = checked_input(selected, 'acceptance_request', document, validate_acceptance_request)
    require(request['runtime'] == {'image_digest': image_digest}, 'acceptance runtime conflicts')
    if operation == 'check':
        execution.finish({'component': 'pve-template', 'operation': 'check', 'action': 'accept',
                          'request_digest': canonical_digest(request), 'facility_writes': 'none'})
        return
    budget = DeadlineBudget(request['deadlines'])
    budget.admit()
    budget.limit('work', request['timeouts']['work_seconds'])
    client = runtime._client(selected, execution, request['target'])
    client.timeout = min(30, budget.remaining('work'))
    helpers = acceptance_snippets.Snippets(selected, execution, request['timeouts']['work_seconds'],
                                          request['cloud_init']['ssh'], budget=budget, phase='work')
    observed = admit_acceptance(ReadBudgetClient(client, budget), request, helpers=helpers)
    budget.remaining('work')
    preview = build_preview(request, observed, image_digest=image_digest)
    save(execution.outputs.path('plan') / 'acceptance-preview.json', preview)
    execution.finish({'component': 'pve-template', 'operation': 'plan', 'action': 'accept',
                      'preview_digest': preview['preview_digest'], 'facility_writes': 'none'})
