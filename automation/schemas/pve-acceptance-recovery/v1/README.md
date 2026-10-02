# Acceptance recovery v1

Generated structural contracts from
`iaas.pve_template.recovery_contracts.contract_schemas()`:

- `pve-acceptance-recovery-request/v1`
- `pve-acceptance-recovery-preview/v1`
- `pve-acceptance-recovery-result/v1`

Current start approval uses the shared
`automation/schemas/pve-acceptance/v3/pve-one-shot-execution-admission.schema.json`
contract with `schema_version: 2`. Preview/request/runtime/deadlines,
cluster/VMID reservation and original caller/native identities must all match.

JSON Schema checks structure. Runtime also checks canonical request/preview
bindings, raw original-file SHA256, confined nonsymlink paths, explicitly trusted
optional rejection provenance/correlation, the full original resource list,
supplied prior recovery bindings, confirmed active tasks and current exact
ownership/references. Only unlinked legacy guest-exec intent without a UPID/PID
is disclosed for an administrator decision using the existing new approval.
Current task-status failures and unresolved helper/recovery activity block cleanup
(`task_activity_unresolved`); no reconstructed trace or complete
history chain is required. Cleanup success does not resolve historical unknown.
Schema validity is not cleanup approval or live acceptance.

Retained rc.19 acceptance request/result v2 and journal v1 are readable only as
original recovery evidence. They are never converted or accepted as a new
acceptance start.

Software fixtures: `docs/examples/recovery/`. Current export/example consistency
is tested by `tests/python/test_pve_acceptance_recovery_contracts.py`.
