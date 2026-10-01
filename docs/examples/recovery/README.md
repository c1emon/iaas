# Acceptance recovery input

These are sanitized **software fixtures**, modeled on `run-120-1`: source
`cohe/9004`, original clone `cohe/798`, two volumes and one snippet. They do not
prove any current facility state or authorize live cleanup. Original request v2
and journal v1 are retained exactly; no pool or new acceptance range is added.

Map `original/` as the read-only `original_execution_dir` and `evidence/` as the
read-only `cleanup_evidence_dir`. `recovery-request.json` contains SHA256 of the
actual bytes, not a reformatted/normalized replacement. The original absolute
cutoffs remain expired. Its new cutoffs are illustrative and must be selected
and approved for an actual recovery.

`evidence/caller.json` binds the original plan, caller/native execution,
pending/consumption reservation, request digest, original runtime and unique
protected dispatch trace in this fixture only. Trace and rejection evidence are
optional; historical executions without them need no reconstruction.
`evidence/rejection.json` is a sanitized administrator
export. The request explicitly declares the authorized source, principal and
provenance; file SHA256 alone is not trust. A real start must bind that declaration
to the current limited cleanup approval. An ambiguous log match stays unknown
for an administrator decision using the existing new approval. A confirmed
active task, incomplete core resource evidence or conflicting UUID/reference
still prevents cleanup.

Read-only reconciliation reports per-request inactivity and historical issued
writes separately. It can resolve the uniquely rejected guest exec without
turning the original acceptance into a passed result. The remaining clone,
configuration and start facts stay issued. Recovery never replays those actions.

`recovery-preview.json`, `recovery-admission.json` and `recovery-result.json`
illustrate the **fake API test**. The example result's passed cleanup is a
software simulation; original acceptance remains unknown. The example admission
uses a new execution, consumption reservation, serialization context and exact
VMID reservation. Its `recovery_of` is the native original acceptance execution;
`pending.execution_id` is the original caller execution.

A start saves request, preview, journal and result under its new protected
`work/pve-recovery/` directory. Once that execution has been dispatched, use
observe against that directory; use a new output parent with the same execution
basename. Observe uses no PVE/SSH credentials and never creates fresh budgets or
falls back to start. Missing/conflicting collection stays unknown.

A further cleanup needs a new execution and approval. Append each previous
recovery's request/journal/available-result references and actual-byte SHA256 to
`previous_recoveries` when retained; keep the unchanged full original VM, volume
and snippet list, including already absent items. No complete history chain is
required. Prior lost responses stay unknown and do not prevent an administrator
from approving the next limited cleanup. Current absence never proves historical
success; confirmed active tasks still block cleanup.

Both new relative limits tighten deadlines from the same start reference.
Entering cleanup does not refresh the cutoff. A stop/delete response loss stops
all dependent writes. Task termination, current existence and current execution
writes are reported separately. The source template, existing pools and ACLs are
never mutation targets.

The three `environment-plan/start/observe.yml` files show exact launcher file
aliases. Replace protected material/SSH paths in a caller-owned copy. Plan has no
execution mode or admission, start includes the actual plan preview and new v2
approval, and observe maps only the dispatched recovery directory. Formal
`run-120-1` commands and release boundaries are documented in
[the recovery operation guide](../../operations/pve-acceptance-recovery.md).
