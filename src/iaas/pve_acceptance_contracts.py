"""Current bounded request/result contracts for PVE acceptance and snippet cleanup.

These validators establish structure and local bindings; original evidence and
execution admission still require validation by the runtime before mutation.
"""
from __future__ import annotations

from ipaddress import ip_address
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from iaas.image.contracts import canonical_digest as canonical_digest
from iaas.image.contracts import load_strict_json as load_strict_json
from iaas.pve_template.contracts import validate_template_record_v2

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
RelativePath = Annotated[str, Field(pattern=r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*\\)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")]
Seconds = Annotated[int, Field(gt=0, le=86400)]
VMID = Annotated[int, Field(ge=100, le=999999999)]
CheckID = Literal['full_clone', 'disk_boot', 'guest_agent', 'cloud_init', 'injected_hostname', 'source_unchanged']
REQUIRED_CHECKS = ('full_clone', 'disk_boot', 'guest_agent', 'cloud_init', 'injected_hostname', 'source_unchanged')
Reason = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,95}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, regex_engine='python-re')


class Target(Contract):
    api_endpoint: str
    node: Identifier
    tls_verify: Literal[True]

    @model_validator(mode='before')
    @classmethod
    def strict_tls(cls, value):
        if isinstance(value, dict) and value.get('tls_verify') is not True:
            raise ValueError('TLS verification must be true')
        return value

    @model_validator(mode='after')
    def valid_endpoint(self):
        if self.tls_verify is not True:
            raise ValueError('TLS verification must be enabled')
        parsed = urlsplit(self.api_endpoint)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise ValueError('target requires a fixed HTTPS endpoint')
        return self


class EvidenceRef(Contract):
    path: RelativePath
    sha256: SHA256


class OriginalVM(Contract):
    node: Identifier
    vmid: VMID
    smbios_uuid: str

    @model_validator(mode='after')
    def valid_uuid(self):
        UUID(self.smbios_uuid)
        return self


class TemporaryVM(Contract):
    node: Identifier
    vmid: VMID
    storage: Identifier
    bridge: Identifier
    vlan_tag: Annotated[int, Field(ge=1, le=4094)] | None
    ip_config: Annotated[str, Field(min_length=1, max_length=512, pattern=r'^[^\r\n\x00]+$')]
    cpus: Annotated[int, Field(ge=1, le=128)]
    memory_mib: Annotated[int, Field(ge=128, le=1048576)]
    disk_limit_bytes: Annotated[int, Field(gt=0, le=1099511627776)]
    boot: Annotated[str, Field(pattern=r'^(?:scsi|virtio|sata)[0-9]+$')]
    firmware: Literal['bios', 'uefi']


class CloudInit(Contract):
    hostname: Annotated[str, Field(pattern=r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$')]


class Timeouts(Contract):
    work_seconds: Seconds
    guest_seconds: Seconds
    cleanup_seconds: Seconds

    @model_validator(mode='after')
    def bounded_guest(self):
        if self.guest_seconds > self.work_seconds:
            raise ValueError('guest deadline exceeds work deadline')
        return self


class Authorization(Contract):
    create_temporary_vm: Literal[True]
    delete_temporary_resources: Literal[True]

    @model_validator(mode='before')
    @classmethod
    def explicit_authorization(cls, value):
        if not isinstance(value, dict) or any(value.get(key) is not True for key in ('create_temporary_vm', 'delete_temporary_resources')):
            raise ValueError('explicit create/delete authorization is required')
        return value


class AcceptanceRequest(Contract):
    kind: Literal['pve-template-acceptance-request']
    schema_version: Literal[1]
    target: Target
    template_record: dict[str, Any]
    temporary_vm: TemporaryVM
    cloud_init: CloudInit
    required_checks: list[CheckID]
    timeouts: Timeouts
    authorization: Authorization

    @model_validator(mode='after')
    def bindings(self):
        record = validate_template_record_v2(self.template_record)
        if record['origin'] != 'publication' or record['target'] != self.target.model_dump():
            raise ValueError('acceptance requires matching published template')
        if record['node'] != self.target.node or record['vmid'] == self.temporary_vm.vmid:
            raise ValueError('template placement or temporary VM identity conflicts')
        UUID(record['smbios_uuid'])
        baseline = record['configuration'].get('name')
        if not isinstance(baseline, str) or not baseline:
            raise ValueError('template hostname baseline is required')
        if self.cloud_init.hostname == baseline:
            raise ValueError('injected hostname must differ from template baseline')
        if len(self.required_checks) != len(REQUIRED_CHECKS) or set(self.required_checks) != set(REQUIRED_CHECKS):
            raise ValueError('all fixed acceptance checks are required exactly once')
        return self


class DeletePlan(Contract):
    plan_id: Identifier
    plan_digest: Digest
    execution_id: Identifier
    metadata: EvidenceRef
    admission: EvidenceRef


class ExecutionMaterials(Contract):
    execution_id: Identifier
    request_digest: Digest
    request: EvidenceRef
    journal: EvidenceRef
    result: EvidenceRef | None


class StateBackend(Contract):
    bucket: Annotated[str, Field(min_length=1)]
    key: Annotated[str, Field(min_length=1)]
    region: Annotated[str, Field(min_length=1)]
    endpoint: str | None
    endpoints: dict[Literal["s3", "S3"], str]
    workspace: Identifier
    workspace_key_prefix: str
    tls_verify: bool
    path_style: bool
    use_lockfile: Literal[True]


class StatePersistence(Contract):
    backend: StateBackend
    root_id: Identifier
    workspace: Identifier
    lineage: str | None
    serial: Annotated[int, Field(ge=0)] | None
    result: EvidenceRef

    @model_validator(mode='after')
    def state_identity(self):
        if (self.lineage is None) != (self.serial is None):
            raise ValueError('state lineage and serial must be supplied together')
        return self


class DeletionEvidence(Contract):
    execution_id: Identifier
    native_task: Annotated[str, Field(min_length=1)]
    result: EvidenceRef
    vm_absence: EvidenceRef
    state_persistence: StatePersistence | None


class OwnershipRecords(Contract):
    manifest: EvidenceRef
    upload: EvidenceRef


class Snippet(Contract):
    node: Identifier
    storage: Identifier
    file_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*:snippets/[A-Za-z0-9][A-Za-z0-9_.-]*$')]
    file_name: Identifier
    sha256: SHA256
    record_ref: Identifier

    @model_validator(mode='after')
    def exact_identity(self):
        if self.file_id != f'{self.storage}:snippets/{self.file_name}':
            raise ValueError('snippet identity conflicts')
        return self


class SSHConnection(Contract):
    host: Annotated[str, Field(min_length=1, max_length=253, pattern=r'^[A-Za-z0-9:][A-Za-z0-9.:-]*$')]
    user: Annotated[str, Field(min_length=1, max_length=32, pattern=r'^[a-z_][a-z0-9_-]*$')]
    port: Annotated[int, Field(ge=1, le=65535)]

    @model_validator(mode='after')
    def fixed_connection(self):
        if self.user == 'root':
            raise ValueError('snippet helper requires an unprivileged SSH account')
        try:
            ip_address(self.host)
        except ValueError:
            if ':' in self.host or all(c in '0123456789.' for c in self.host):
                raise ValueError('SSH host must be a DNS name or IP address') from None
            labels = self.host.rstrip('.').split('.')
            if any(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) is None for label in labels):
                raise ValueError('SSH host must be a DNS name or IP address') from None
        return self


class CleanupRequest(Contract):
    kind: Literal['pve-snippet-cleanup-request']
    schema_version: Literal[1]
    ssh: SSHConnection
    origin: Literal['deployment', 'acceptance']
    target: Target
    original_vm: OriginalVM
    original_execution_id: Identifier
    delete_plan: DeletePlan | None
    acceptance_evidence: ExecutionMaterials | None
    deletion_evidence: DeletionEvidence
    ownership_records: OwnershipRecords
    snippets: Annotated[list[Snippet], Field(min_length=1, max_length=256)]
    timeout_seconds: Seconds
    retry_of: Identifier | None
    retry_materials: ExecutionMaterials | None

    @model_validator(mode='after')
    def bindings(self):
        if self.origin == 'deployment':
            if self.delete_plan is None or self.acceptance_evidence is not None or self.deletion_evidence.state_persistence is None:
                raise ValueError('deployment requires delete plan and state persistence only')
            if self.delete_plan.execution_id != self.deletion_evidence.execution_id:
                raise ValueError('delete execution conflicts')
        else:
            if self.delete_plan is not None or self.acceptance_evidence is None or self.deletion_evidence.state_persistence is not None:
                raise ValueError('acceptance requires original acceptance materials without plan/state')
            if (self.acceptance_evidence.execution_id != self.original_execution_id
                    or self.deletion_evidence.execution_id != self.original_execution_id):
                raise ValueError('acceptance execution conflicts')
        if (self.retry_of is None) != (self.retry_materials is None):
            raise ValueError('retry association must be supplied together')
        if self.retry_materials is not None and self.retry_materials.execution_id != self.retry_of:
            raise ValueError('retry execution conflicts')
        identities = [(x.node, x.file_id) for x in self.snippets]
        if len(set(identities)) != len(identities):
            raise ValueError('snippet identities must be unique')
        return self


class Outcome(Contract):
    status: Literal['passed', 'failed', 'unknown', 'not_attempted', 'not_required']
    reason_code: Reason
    evidence_ref: RelativePath | None


class Check(Contract):
    id: CheckID
    status: Literal['passed', 'failed', 'unknown', 'not_attempted']
    reason_code: Reason
    evidence_ref: RelativePath | None


class Resource(Contract):
    kind: Literal['vm', 'volume', 'snippet']
    node: Identifier
    identity: Annotated[str, Field(min_length=1, max_length=512)]
    created_by: Identifier
    ownership: Literal['owned', 'not_owned', 'unknown']


class Residual(Resource):
    existence: Literal['present', 'unknown']
    reason_code: Reason


class Residuals(Contract):
    inventory_complete: bool
    items: list[Residual]


class Collection(Contract):
    status: Literal['complete', 'failed', 'unknown']
    reason_code: Reason


class CleanupOutcomes(Contract):
    vm: Outcome
    volumes: Outcome
    snippets: Outcome


class RuntimeIdentity(Contract):
    image_digest: Annotated[str, Field(pattern=r'^(?:[^@\s]+@)?sha256:[0-9a-f]{64}$')]


class TemplateIdentity(Contract):
    record_id: Identifier
    execution_id: Identifier
    artifact_digest: Digest
    node: Identifier
    vmid: VMID
    smbios_uuid: str


class ResultBase(Contract):
    schema_version: Literal[1]
    execution_id: Identifier
    request_digest: Digest
    runtime: RuntimeIdentity
    residuals: Residuals
    overall: Literal['passed', 'failed', 'unknown']
    collection: Collection


class AcceptanceResult(ResultBase):
    kind: Literal['pve-template-acceptance-result']
    template: TemplateIdentity
    temporary_resources: list[Resource]
    checks: list[Check]
    failure_stage: Identifier | None
    cleanup: CleanupOutcomes

    @model_validator(mode='after')
    def conclusion(self):
        if len(self.checks) != 6 or {x.id for x in self.checks} != set(REQUIRED_CHECKS):
            raise ValueError('result must include all required checks')
        cleanup = [self.cleanup.vm, self.cleanup.volumes, self.cleanup.snippets]
        unknown = (self.collection.status != 'complete' or not self.residuals.inventory_complete
                   or any(x.status == 'unknown' for x in [*self.checks, *cleanup])
                   or any(x.ownership == 'unknown' for x in self.temporary_resources)
                   or any(x.existence == 'unknown' for x in self.residuals.items))
        passed = (all(x.status == 'passed' for x in self.checks)
                  and all(x.status in ('passed', 'not_required') for x in cleanup)
                  and not self.residuals.items and self.failure_stage is None)
        expected = 'unknown' if unknown else 'passed' if passed else 'failed'
        if self.overall != expected:
            raise ValueError('acceptance overall conflicts with recorded facts')
        return self


class ScopeCheck(Contract):
    status: Literal['passed', 'failed', 'unknown']
    nodes: list[Identifier]
    storages: list[Identifier]
    permissions_complete: bool
    inventory_complete: bool
    reason_code: Reason


class CleanupItem(Snippet):
    status: Literal['deleted', 'already_absent', 'referenced', 'mismatch', 'failed', 'unknown']
    reason_code: Reason


class CleanupResult(ResultBase):
    kind: Literal['pve-snippet-cleanup-result']
    origin: Literal['deployment', 'acceptance']
    original_vm: OriginalVM
    original_execution_id: Identifier
    delete_plan_digest: Digest | None
    acceptance_request_digest: Digest | None
    deletion_execution_id: Identifier
    retry_of: Identifier | None
    scope_check: ScopeCheck
    items: Annotated[list[CleanupItem], Field(min_length=1, max_length=256)]

    @model_validator(mode='after')
    def conclusion(self):
        if ((self.origin == 'deployment' and (self.delete_plan_digest is None or self.acceptance_request_digest is not None))
                or (self.origin == 'acceptance' and (self.delete_plan_digest is not None or self.acceptance_request_digest is None))):
            raise ValueError('cleanup result origin bindings conflict')
        if self.retry_of == self.execution_id:
            raise ValueError('cleanup cannot retry itself')
        identities = [(x.node, x.file_id) for x in self.items]
        if len(set(identities)) != len(identities):
            raise ValueError('cleanup result has duplicate files')
        unknown = (self.collection.status != 'complete' or not self.residuals.inventory_complete
                   or self.scope_check.status == 'unknown' or any(x.status == 'unknown' for x in self.items)
                   or any(x.existence == 'unknown' for x in self.residuals.items))
        passed = (self.scope_check.status == 'passed' and self.scope_check.permissions_complete
                  and self.scope_check.inventory_complete and not self.residuals.items
                  and all(x.status in ('deleted', 'already_absent') for x in self.items))
        if self.overall != ('unknown' if unknown else 'passed' if passed else 'failed'):
            raise ValueError('cleanup overall conflicts with recorded facts')
        return self


def _validate(model: type[Contract], value: Any) -> dict[str, Any]:
    try:
        if not isinstance(value, dict):
            raise ValueError('contract must be an object')
        result = model.model_validate(value)
        # Literal[1]/Literal[True] otherwise compare equal to bool/int in Pydantic.
        if type(value.get('schema_version')) is not int:
            raise ValueError('unsupported schema version')
        return result.model_dump()
    except ValidationError:
        # Never expose rejected values, guest configuration or caller credentials.
        raise ValueError(f'invalid {model.__name__} contract') from None


def validate_acceptance_request(value: Any) -> dict[str, Any]:
    return _validate(AcceptanceRequest, value)


def validate_snippet_cleanup_request(value: Any, *, execution_id: str | None = None) -> dict[str, Any]:
    result = _validate(CleanupRequest, value)
    if execution_id is not None and result['retry_of'] == execution_id:
        raise ValueError('cleanup cannot retry itself')
    return result


def validate_acceptance_result(value: Any) -> dict[str, Any]:
    return _validate(AcceptanceResult, value)


def validate_snippet_cleanup_result(value: Any) -> dict[str, Any]:
    return _validate(CleanupResult, value)


def contract_schemas() -> dict[str, dict[str, Any]]:
    """Export structural schemas; runtimes also enforce original-material bindings."""
    models = {
        'pve-template-acceptance-request': AcceptanceRequest,
        'pve-template-acceptance-result': AcceptanceResult,
        'pve-snippet-cleanup-request': CleanupRequest,
        'pve-snippet-cleanup-result': CleanupResult,
    }
    schemas = {}
    for name, model in models.items():
        schema = model.model_json_schema()
        schema.update({'$schema': 'https://json-schema.org/draft/2020-12/schema',
                       '$id': f'https://iaas.invalid/schemas/pve-acceptance/v1/{name}.schema.json'})
        if model is AcceptanceRequest:
            schema['properties']['required_checks'].update(minItems=6, maxItems=6, uniqueItems=True)
        if model is CleanupRequest:
            schema['allOf'] = [
                {'if': {'properties': {'origin': {'const': 'deployment'}}},
                 'then': {'properties': {'delete_plan': {'$ref': '#/$defs/DeletePlan'},
                                         'acceptance_evidence': {'type': 'null'},
                                         'deletion_evidence': {'properties': {'state_persistence': {'$ref': '#/$defs/StatePersistence'}}}}},
                 'else': {'properties': {'delete_plan': {'type': 'null'},
                                         'acceptance_evidence': {'$ref': '#/$defs/ExecutionMaterials'},
                                         'deletion_evidence': {'properties': {'state_persistence': {'type': 'null'}}}}}},
                {'if': {'properties': {'retry_of': {'type': 'null'}}},
                 'then': {'properties': {'retry_materials': {'type': 'null'}}},
                 'else': {'properties': {'retry_materials': {'$ref': '#/$defs/ExecutionMaterials'}}}},
            ]
        schemas[name] = schema
    return schemas
