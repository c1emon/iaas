"""Current recovery contracts; retained acceptance v2 is evidence, never start input."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from iaas.pve_acceptance_contracts import (
    Contract, Deadlines, Digest, EvidenceRef, Identifier, RuntimeIdentity, SHA256,
    Target, VMID, canonical_digest,
)


class RecoveryTimeouts(Contract):
    work_seconds: int = Field(gt=0, le=86400)
    cleanup_seconds: int = Field(gt=0, le=86400)


class RecoveryAuthorization(Contract):
    cleanup_original_resources: Literal[True]


class RecoveryVM(Contract):
    node: Identifier
    vmid: VMID
    smbios_uuid: str
    created_by: Identifier
    pool: Identifier | None = None

    @model_validator(mode='after')
    def identity(self):
        UUID(self.smbios_uuid)
        return self


class RecoverySnippet(Contract):
    node: Identifier
    file_id: str = Field(pattern=r'^[A-Za-z0-9_.-]+:snippets/[A-Za-z0-9_.-]+$')
    sha256: SHA256
    created_by: Identifier


class FullOriginalResources(Contract):
    vm: RecoveryVM
    volumes: list[str] = Field(min_length=1)
    snippets: list[RecoverySnippet]

    @model_validator(mode='after')
    def complete(self):
        if len(self.volumes) != len(set(self.volumes)) or any(':' not in v or '..' in v or '\x00' in v for v in self.volumes):
            raise ValueError('original volume identities are invalid')
        if len({(s.node, s.file_id) for s in self.snippets}) != len(self.snippets):
            raise ValueError('duplicate original snippet')
        if any(s.created_by != self.vm.created_by or s.node != self.vm.node for s in self.snippets):
            raise ValueError('original resource ownership conflicts')
        return self


class OriginalMaterials(Contract):
    request: EvidenceRef
    journal: EvidenceRef
    result: EvidenceRef | None = None


class CallerAssociation(Contract):
    plan_id: Identifier
    execution_id: Identifier
    pending_record_id: Identifier
    reservation_id: Identifier
    material: EvidenceRef


class RejectionEvidence(Contract):
    material: EvidenceRef
    source_id: Identifier
    provenance: Literal['authoritative_service_record', 'administrator_export']
    authenticated_principal: str = Field(min_length=1, max_length=256)
    source_description: str = Field(min_length=1, max_length=1024)
    # An explicit declaration is bound by preview and the new cleanup approval.
    # A boolean in an arbitrary log file cannot substitute for this declaration.
    authorize_trusted_source: Literal[True]


class PreviousRecovery(Contract):
    execution_id: Identifier
    materials: OriginalMaterials


class RecoveryRequest(Contract):
    kind: Literal['pve-acceptance-recovery-request']
    schema_version: Literal[1]
    target: Target
    cluster_scope: Identifier
    runtime: RuntimeIdentity
    deadlines: Deadlines
    timeouts: RecoveryTimeouts
    authorization: RecoveryAuthorization
    original_execution_id: Identifier
    caller_association: CallerAssociation
    original_materials: OriginalMaterials
    rejection_evidence: list[RejectionEvidence]
    full_original_resources: FullOriginalResources
    previous_recoveries: list[PreviousRecovery]

    @model_validator(mode='after')
    def associations(self):
        if self.full_original_resources.vm.created_by != self.original_execution_id:
            raise ValueError('original created_by conflicts')
        if self.full_original_resources.vm.node != self.target.node:
            raise ValueError('original cleanup node conflicts')
        ids = [p.execution_id for p in self.previous_recoveries]
        if len(ids) != len(set(ids)) or self.original_execution_id in ids:
            raise ValueError('previous recovery association conflicts')
        if len({r.material.path for r in self.rejection_evidence}) != len(self.rejection_evidence):
            raise ValueError('duplicate rejection evidence')
        return self


class RecoveryPreview(Contract):
    kind: Literal['pve-acceptance-recovery-preview']
    schema_version: Literal[1]
    action: Literal['recover']
    fixed_input: RecoveryRequest
    request_digest: Digest
    preview_digest: Digest
    target: Target
    runtime: RuntimeIdentity
    reconciliation: dict[str, Any]

    @model_validator(mode='after')
    def digest(self):
        if self.target != self.fixed_input.target or self.runtime != self.fixed_input.runtime:
            raise ValueError('recovery preview placement/runtime conflicts')
        if canonical_digest(self.fixed_input.model_dump(exclude_none=True)) != self.request_digest:
            raise ValueError('recovery request digest conflicts')
        value = self.model_dump(exclude_none=True)
        value.pop('preview_digest')
        if canonical_digest(value) != self.preview_digest:
            raise ValueError('recovery preview digest conflicts')
        return self


class RecoveryResult(Contract):
    kind: Literal['pve-acceptance-recovery-result']
    schema_version: Literal[1]
    execution_id: Identifier
    original_execution_id: Identifier
    recovery_of: Identifier
    request_digest: Digest
    preview_digest: Digest
    runtime: RuntimeIdentity
    deadlines: Deadlines
    full_original_resources: FullOriginalResources
    caller_association: CallerAssociation
    original_materials: OriginalMaterials
    previous_recoveries: list[PreviousRecovery]
    original_request_digest: Digest
    original_runtime: RuntimeIdentity
    original_deadlines: Deadlines
    original_acceptance: Literal['passed', 'failed', 'unknown']
    original_activity: Literal['inactive', 'unknown']
    original_facility_writes: Literal['none', 'issued', 'unknown']
    facility_writes: Literal['none', 'issued', 'unknown']
    reconciliation: dict[str, Any]
    resources: list[dict[str, Any]]
    cleanup: dict[str, Any]
    collection: dict[str, Any]
    residuals: list[dict[str, Any]]
    overall: Literal['passed', 'failed', 'unknown']
    deadline_outcome: dict[str, Any]
    reason_code: str

    @model_validator(mode='after')
    def consistent(self):
        if self.execution_id == self.original_execution_id or self.recovery_of != self.original_execution_id:
            raise ValueError('recovery execution association conflicts')
        if self.full_original_resources.vm.created_by != self.original_execution_id:
            raise ValueError('recovery ownership conflicts')
        if self.overall == 'passed':
            full = self.full_original_resources
            expected = {('vm', full.vm.node, str(full.vm.vmid))} | {
                ('volume', full.vm.node, v) for v in full.volumes} | {
                ('snippet', s.node, s.file_id) for s in full.snippets}
            if (len(self.resources) != len(expected)
                    or {(r.get('kind'), r.get('node'), r.get('identity')) for r in self.resources} != expected
                    or any(r.get('existence') != 'absent' or r.get('status') not in {'deleted', 'already_absent'}
                           for r in self.resources)):
                raise ValueError('recovery success lacks full per-resource absence')
        if self.overall == 'passed' and (self.facility_writes == 'unknown' or self.reconciliation.get('active_tasks') is True
                or self.collection.get('status') != 'complete' or self.residuals
                or self.cleanup.get('status') != 'passed'):
            raise ValueError('recovery success lacks complete cleanup evidence')
        return self


def _validate(model, value: Any) -> dict[str, Any]:
    try:
        return model.model_validate(value).model_dump(exclude_none=True)
    except Exception:
        raise ValueError(f'invalid {model.__name__} contract') from None


def validate_recovery_request(value: Any) -> dict[str, Any]:
    return _validate(RecoveryRequest, value)


def build_recovery_preview(value: Any, reconciliation: dict[str, Any]) -> dict[str, Any]:
    request = validate_recovery_request(value)
    body = {'kind': 'pve-acceptance-recovery-preview', 'schema_version': 1, 'action': 'recover',
            'fixed_input': request, 'request_digest': canonical_digest(request), 'target': request['target'],
            'runtime': request['runtime'], 'reconciliation': reconciliation}
    body['preview_digest'] = canonical_digest(body)
    return body


def validate_recovery_preview(value: Any) -> dict[str, Any]:
    return _validate(RecoveryPreview, value)


def validate_recovery_result(value: Any) -> dict[str, Any]:
    return _validate(RecoveryResult, value)


def contract_schemas() -> dict[str, dict[str, Any]]:
    """Structural exports; provenance/byte/reference checks remain runtime work."""
    models = {'pve-acceptance-recovery-request': RecoveryRequest,
              'pve-acceptance-recovery-preview': RecoveryPreview,
              'pve-acceptance-recovery-result': RecoveryResult}
    schemas = {}
    for name, model in models.items():
        schema = model.model_json_schema()
        schema.update({'$schema': 'https://json-schema.org/draft/2020-12/schema',
                       '$id': f'https://iaas.invalid/schemas/pve-acceptance-recovery/v1/{name}.schema.json'})
        schemas[name] = schema
    return schemas
