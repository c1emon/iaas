# PVE acceptance v3 and snippet cleanup v2

The implementation branch uses acceptance request/result v3 and publication
record/result/preview v3 (publish request v2). This change is not yet released;
its acceptance plan/start and recovery entrypoints are still being integrated.
Software fixtures are
separate from qualification of a released image or a real facility.
Launcher interface remains v1; snippet cleanup request/result remains v2.
Consumers must check the released image's advertised capabilities before invoking it.

## Contract artifacts

- [JSON schemas](../../automation/schemas/pve-acceptance/v3/README.md): current request/result and scoped admission schemas.
- [Shared fixtures](../examples/pve-acceptance/README.md): normal and rejected inputs, used by the Python contract tests.
- [Launcher examples](../runtime-launcher.md): file mappings and start/observe commands.
- [Cleanup helper installation and permissions](../operations/pve-snippet-cleanup.md): deadline protocol v2 and helper-capabilities/v1, exact evidence references and platform limits.

Request JSON rejects duplicate keys, unknown fields/versions, floats and nonfinite
values. The normalized request SHA-256 binds execution admission `plan_digest`
(without the `sha256:` prefix). The launcher execution ID binds admission,
reservation, pending record and journal. Request/result validators also enforce
origin/retry relationships and truthful overall conclusions beyond structural
JSON schema validation. Generated examples are synthetic, not live results.

## One-shot execution and observation

`options.execution_mode` must explicitly be `start` or `observe`. Start requires
the fixed request and complete `files.execution_admission`; the caller holds the
complete serialization context and atomically records dispatch before invocation.
IaaS does not inspect the caller's ledger or provide global deduplication between
Runners. A copied reservation or a new output path never authorizes replay.

Before mutation, the runtime creates a private `diagnostics/execution` directory
with `request.json` and `journal.json`. It records mutation intent before each
native operation, retains UPIDs and original ownership, and writes `result.json`.
The original directory must survive the temporary runtime. Pass this exact
directory as read-only `files.original_execution_dir` to observe, using the
original execution ID and a new output directory. `pve-template read` can also
observe this directory without a new execution ID. Observation makes no API,
helper, VM or state writes and receives no operation credentials. Missing core
materials return unknown/nonzero; a missing final result preserves the journal
without inventing success. A bound unknown result remains unknown even when the
original mutation may still be active.

## Frozen absolute deadlines

Both request/result contracts are v2. `deadlines.work_deadline_at` and
`deadlines.cleanup_deadline_at` are required UTC `YYYY-MM-DDTHH:mm:ssZ` calendar
values (seconds, no offset/fraction/leap second), with work <= cleanup. The same
object is required in execution-admission/v1 for these two operations and binds
through the canonical request digest, execution ID and private materials.
infra-ops computes and persists them from lawful target start and approved
policy. IaaS never grants a new window from arrival, retry or phase entry.

Start freezes both monotonic upper bounds from one UTC/monotonic reference.
Each stage and send rechecks remaining absolute and monotonic budget; relative
limits can only tighten calls. Acceptance clone/config/upload/start/guest uses
work; ownership-safe compensation uses cleanup. Standalone cleanup must finish
original-evidence and initial complete scope admission within work before
performing per-item cleanup within cleanup. UTC rollback cannot extend either
start-frozen bound; forward jumps tighten it. Runner/node UTC synchronization
remains an operational prerequisite.

Deadline-aware helper v2 requires a cutoff in explicit acceptance-upload and
snippet-delete modes, rechecking after locks/scans/content checks before actual
create/unlink. Ordinary VM cloud-init upload retains its existing mode semantics.
Acceptance cannot fall back to ordinary mode. Missing helper support rejects the
write. At cleanup cutoff no new write or active online polling starts; protected
local collection continues. Already dispatched API/guest/helper operations may
outlive the local call and remain unknown; timeout is not cancellation/rollback.

Results retain `deadlines`, `deadline_outcome` (phase admission/work/cleanup or
null; status rejected/exceeded/not_exceeded), and separate `facility_writes`
(none/issued/unknown) facts for this execution. Admission rejection returns
nonzero and records zero writes even when uninspected resource existence and
overall remain unknown. Resource unknown alone does not imply a possible write
by this execution. Phase failure, cleanup incompleteness and unknown effects
remain separate; cleanup success never promotes failed acceptance to passed.
Observe validates historical materials read-only, without constructing budgets.
New cleanup authority binds new deadlines and a new execution while preserving
the complete original resource scope and proving prior inactivity.

## Template acceptance

The request fixes a published `pve-template-record/v2`, temporary node/VMID,
storage, bridge/VLAN/IP configuration, CPU/memory/total-disk limits, boot disk and
firmware, fresh hostname, all six checks, relative work/guest/cleanup upper limits and absolute deadlines, and
explicit create/delete authorization. The hostname must differ from the known
template baseline. No arbitrary guest commands are accepted.

The runtime checks the source's stable config/UUID/volumes, performs one native
full clone, then binds the completed clone task to the fresh UUID and exact
storage-owned attached volumes. The ownership inventory includes generated
cloud-init and EFI/TPM volumes. All attached disk sizes, including cloud-init/EFI/TPM, count against the disk limit; missing size evidence is refused. Source volumes are never adopted. Unbounded host
passthrough, custom QEMU arguments and hooks are refused. The clone remains off
until its temporary resources and network are configured and checked.

The fixed guest checks use agent ping, `cloud-init status --format json`, and
agent hostname. Cloud-init must report enabled, completed, nondegraded execution
without errors; missing tools/output, unchanged hostname, failures and deadlines
do not pass. Raw output and hostname remain in protected execution materials.
The runtime generates an execution-owned user-data snippet with the injected
hostname and a `users` list preserving the template `ciuser` (or the image default).
Passwords are locked and package updates are disabled for this bounded technical
check. The request binds `cloud_init.snippet_storage` and `cloud_init.ssh`; start
requires isolated `files.ssh_key` and `files.known_hosts`. The upload helper must
support `--create-only`; an existing file is never overwritten. Inherited
`cicustom` is detached, not deleted. After confirmed VM deletion, the restricted
cleanup helper checks complete cluster references and the exact snippet digest.
Unknown upload/deletion outcomes retain evidence and fail closed.

Cleanup has a separate frozen deadline and relative upper limit, and runs after check failure/timeouts. It verifies
ownership and native task inactivity, stops/deletes only the clone, checks exact
VM and owned-volume absence, and rechecks source identity/configuration. Unknown
native outcomes or changed ownership retain resources. A lost delete response
cannot be converted to historical success just because the VM is now absent.
The source comparison excludes transient lock/digest fields; it is not a disk-byte
integrity attestation. No guest SSH, external connectivity or business test runs.

Source diagnostics retain the first failure stage and reason. A capacity failure
before the source baseline is saved reports `source_snapshot_missing` (unknown),
not a changed template. Recheck transport/API failure is `source_query_failed`,
and malformed evidence is `source_evidence_insufficient`, both unknown. Only a
confirmed baseline identity/configuration mismatch is `source_changed` (failed).
Overall aggregation gives unknown priority even when the original capacity
failure is known; the original check still reports `disk_limit_exceeded`.

The authenticated HTTPS boundary distinguishes `request_rejected` from
`request_outcome_unknown`. A native PVE 403 permission check for the exact VM,
with the native server marker and matching request URL, ends only that request's
active uncertainty. Guest ping fails immediately on that rejection. Guest exec
records method/path/status/HTTP code without copying the response or identity.
Earlier issued writes remain issued; another active unknown still prevents
cleanup. Generic 403, timeout, connection loss, or invalid response remain
unknown. This classification follows the native pre-dispatch permission
exception and response marker in PVE's
[exception implementation](https://github.com/proxmox/pve-common/blob/master/src/PVE/Exception.pm)
and [HTTP server](https://github.com/proxmox/pve-http-server/blob/master/src/PVE/APIServer/AnyEvent.pm).

The HTTPS token needs `VM.Audit` on source/temporary VM, `VM.Clone` on source,
`VM.Allocate`, `VM.Config.CPU`, `VM.Config.Memory`, `VM.Config.Network`,
`VM.Config.Options`, `VM.Config.Cloudinit`, `VM.PowerMgmt`, and
`VM.GuestAgent.Unrestricted` on the temporary VM, plus `Datastore.Audit` and
`Datastore.AllocateSpace` on its selected storage. Network SDN deployments may
also require the platform's bridge/VNet use privilege. Strict TLS remains enabled;
`files.api_ca` adds the caller CA alongside system trust and is retained privately.
See upstream [QEMU API](https://git.proxmox.com/?p=qemu-server.git;a=blob;f=src/PVE/API2/Qemu.pm;hb=HEAD),
[agent API](https://git.proxmox.com/?p=qemu-server.git;a=blob;f=src/PVE/API2/Qemu/Agent.pm;hb=HEAD),
and [cloud-init status](https://docs.cloud-init.io/en/latest/howto/status.html).

## Independent snippet cleanup

The cleanup request fixes `ssh.host`, `ssh.user` and `ssh.port` inside its digest;
ambient SSH target variables cannot redirect deletion. Strict known-host and key
files are mapped separately.

Deployment origin consumes the existing manifest, upload/deployment result,
approved saved delete plan, execution admission and confirmed deletion/state
result. The authoritative native plan identity is its digest; `plan_id` is the
caller's correlation label. Acceptance origin consumes the original acceptance
request/journal, exact snippet records and confirmed VM delete UPID, without a
plan or state backend. Insufficient original records are refused rather than
reconstructed. Acceptance journals retain the generated snippet record, upload confirmation
and cleanup result for this evidence branch.

A first cleanup sets `retry_of` and `retry_materials` to null. A retry uses a new
execution/admission and the previous request/journal/available result, proving
inactivity and the unchanged full original list. Only timeout, newly authorized deadlines and retry association
may change; the old execution window and result remain unchanged. Read-only evidence references are confined paths with existing
SHA-256 values under `files.cleanup_evidence_dir`; transport path relocation does
not change resource identity. Cleanup never mutates a VM, state, lock or original
acceptance result.

Each input yields deleted/already_absent/referenced/mismatch/failed/unknown.
Incomplete global reference visibility prevents all deletion. Independently safe
items can finish despite another item's failure. Every unknown existence remains
explicit in residuals. `passed` requires all input files deleted/already absent,
complete visibility and successful result collection.

## Promotion and validation boundary

Only acceptance `overall: passed`, all required checks passed, complete collection
and all cleanup passed/not_required permit the caller to consider promotion.
A later snippet-only cleanup success does not rewrite a failed/unknown acceptance
or hide VM/volume residue. IaaS does not update infra-ops `available` records.

Validation uses fake HTTPS/guest responses, real local temporary filesystem helper
fixtures, current deployment producer materials, and launcher local/DinD transport
fixtures. No live PVE, shared storage, actual DinD daemon, release or deployment is
implied. A real acceptance needs separately fixed node/VMID/storage and a bounded
creation/deletion authorization window.

The VM module assigns a fresh SMBIOS UUID at creation and ignores subsequent
UUID expression changes. The UUID is retained in native state, creation results
and deletion plans; missing historical UUID evidence is still refused. Deployment
targets are cluster-scoped: node binding comes from the matching plan and snapshot
VM records, rather than a nonexistent target.node field.
