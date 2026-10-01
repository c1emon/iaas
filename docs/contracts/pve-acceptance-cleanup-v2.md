# PVE acceptance v3 and snippet cleanup v2

The implementation branch uses acceptance request/result v3 and publication
record/result/preview v3 (publish request v2). This change is not yet released;
its acceptance plan/start is implemented; recovery entrypoints are still being integrated.
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
values. Acceptance admission v2 binds `request_digest`, runtime and
`plan_digest` = preview digest without the `sha256:` prefix. Standalone snippet
admission v1 continues binding its request digest as `plan_digest`.
The launcher execution ID binds admission,
reservation, pending record and journal. Request/result validators also enforce
origin/retry relationships and truthful overall conclusions beyond structural
JSON schema validation. Generated examples are synthetic, not live results.

## One-shot execution and observation

`options.execution_mode` must explicitly be `start` or `observe`. Start requires
the fixed request and complete `files.execution_admission`; acceptance additionally
requires `files.acceptance_preview`. `check` with action `accept` is offline;
`plan` repeats the full read-only API/SSH/helper admission and writes
`plan/acceptance-preview.json` without consuming approval. The caller holds the
complete serialization context and atomically records dispatch before invocation.
IaaS does not inspect the caller's ledger or provide global deduplication between
Runners. A copied reservation or a new output path never authorizes replay.

Before mutation, the runtime creates a private `diagnostics/execution` directory
with `request.json`, `preview.json` (acceptance) and `journal.json`. The acceptance
journal retains the full validated preview and digest. It records mutation intent before each
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

Acceptance request/result is v3; standalone snippet request/result is v2.
`deadlines.work_deadline_at` and
`deadlines.cleanup_deadline_at` are required UTC `YYYY-MM-DDTHH:mm:ssZ` calendar
values (seconds, no offset/fraction/leap second), with work <= cleanup. The same
object is required in acceptance admission/v2 and standalone snippet admission/v1 and binds
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

The request fixes a published `pve-template-record/v3`, temporary node/VMID/pool,
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

Acceptance requires a nonempty existing pool and a concrete VMID inside the
caller interval. The native full clone specifies that pool; claim, start and
cleanup check actual membership and current effective permissions. A moved VM
is retained. The interval, pool and VMID bind request, preview, admission and
result; the caller's `vmid_reservation` uses the same reservation/context IDs.
Storage capacity is checked before cloning and actual owned disk capacity after
cloning/configuration. The total includes cloud-init/EFI/TPM disks: 40 GiB plus
4 MiB is 42,953,867,264 bytes and exceeds a 40 GiB total limit. The limit is never
automatically increased. Preview/result capacity contains the limit, total and
slot/volume/size details; unavailable sizes or space refuse cloning.

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

Online admission queries effective permissions for the authenticated token.
It does not infer authority from role names, ACL presence, or the owning user's
permissions alone. A present privilege with propagation value `0` or `1`
(including API booleans) is granted. Missing privilege, invalid value, query
failure and insufficient scope are respectively `permission_missing`,
`permission_value_invalid`, `permission_query_failed` and
`permission_evidence_insufficient`.

| Operation | Effective permission condition |
| --- | --- |
| Read source / clone source | `VM.Audit` / `VM.Clone` on `/vms/SOURCE_VMID`. |
| Allocate clone in existing pool | `VM.Allocate` on `/vms/NEW_VMID` **OR** `/pool/POOL`; both are not required. Pool existence must also be observable. |
| Explicit existing VM pool membership change | `Pool.Allocate` on each modified pool, plus `Permissions.Modify` **OR** `VM.Allocate` on `/vms/VMID`. Removing then adding membership uses both pool scopes. |
| Configure temporary VM | `VM.Config.CPU`, `VM.Config.Memory`, `VM.Config.Disk`, `VM.Config.Network`, `VM.Config.Options`, `VM.Config.HWType`, `VM.Config.Cloudinit` on its effective prospective/current VM scope. |
| Read / start / stop / delete temporary VM | `VM.Audit` / `VM.PowerMgmt` / `VM.PowerMgmt` / `VM.Allocate` on its current VM scope. |
| Agent ping / get-host-name | `VM.GuestAgent.Audit` **OR** `VM.GuestAgent.Unrestricted`. |
| Agent exec / exec-status | `VM.GuestAgent.Unrestricted`; acceptance requires this, so an extra independent Audit grant is unnecessary. |
| Target node status | `Sys.Audit` on `/nodes/NODE`; node CPU/memory totals and online status must satisfy the request. |
| Storage status / capacity and allocation | `Datastore.Audit` and `Datastore.AllocateSpace` on each selected image/snippet storage. |
| Local bridge without VLAN / with VLAN | `SDN.Use` on `/sdn/zones/localnetwork/BRIDGE` / `/sdn/zones/localnetwork/BRIDGE/TAG`; clone-inherited network attachments are checked too. |
| Read own native task status | Authenticated task-owner path; admission does not add unrelated global task privileges. The dispatched UPID must remain bound to this execution. |

Acceptance uses the existing restricted SSH helper to compile prospective
permissions when current direct grants cannot establish future pool authority.
Native PVE ACL parsing/compilation operates on an in-memory membership copy and
retains NoAccess and separated-token intersection. The helper principal is
derived from the actual API credential; its current direct/pool grants must
match API evidence and its prospective response must bind the exact VMID/pool.
No token value or ACL contents are transmitted in diagnostics. Missing compiler
capability or unverifiable identity/scope refuses admission. Ordinary VM and
publication paths do not install or automatically add this SSH compiler:
complete direct grants, or sufficient full pool grants with nonempty direct
effective evidence, must establish authority; otherwise they refuse with
`permission_evidence_insufficient` rather than union arbitrary ACLs or assume
pool inheritance. Creating into a pool does not require `Pool.Allocate` merely
because a pool is selected; explicit changes to existing pool membership follow
the separate native pool update permission condition. The fixed provider family
is `bpg/proxmox ~> 0.111.0`, with `0.111.1` used by the checked lock; its
[v0.111.1 VM pool update](https://github.com/bpg/terraform-provider-proxmox/blob/v0.111.1/proxmoxtf/resource/vm/vm.go#L5854)
removes from the original pool before adding a nonempty new pool. Native
[pool update](https://github.com/proxmox/pve-manager/blob/master/PVE/API2/Pool.pm)
requires `Pool.Allocate` and checks object permission modification;
[RPCEnvironment](https://github.com/proxmox/pve-access-control/blob/master/src/PVE/RPCEnvironment.pm)
implements the VM predicate as `Permissions.Modify OR VM.Allocate`. This is
different from creating directly into a pool. The provider's existing
pool-to-empty update returns without removing membership: omitted/null selects
no pool for new VMs, but must not be described as an implemented in-place
membership removal for an already pooled VM. Current admission rejects that
in-place pool-to-null update before execution. Creating a new VM with null pool
remains supported. Existing moves between two nonempty pools check both pool
permissions and the VM permission alternative before dispatch; no extra pool
mutation is performed outside the reviewed provider operation.

The current acceptance network admission covers active local Linux/OVS bridges
and VLAN-aware Linux bridges. It checks the exact localnetwork permission path.
An SDN VNet requires its real zone's native permission path; this implementation
does not resolve or qualify that zone and must not be presented as SDN VNet
readiness. SDN qualification remains a separately scoped extension.

Both online plan and start check source UUID/configuration/volumes, exact pool
and VMID, complete cluster occupancy, node resources, boot/firmware, storage
content/activity/space, network permissions and mandatory helpers before clone.
An empty pool-filtered VM list cannot prove the VMID free. Acceptance instead
matches the delete helper's complete pmxcfs node/VMID inventory to the selected
API cluster and SSH local node. `files.ssh_key`, `files.known_hosts`, fixed SSH
target, `sudo -n`, and both capability declarations are mandatory even when an
ordinary preflight would treat SSH as optional. Online plan performs no clone,
upload, guest call or facility/state write; start independently rechecks current
prerequisites and does not replace the reviewed plan after a failure.

Strict TLS remains enabled;
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
execution/admission and the previous request/journal/available result, preserving
the unchanged full original list. Historical helper uncertainty or unrelated guest
outcomes do not block a freshly approved cleanup after confirmed VM deletion and
current complete reference checks. Only timeout, newly authorized deadlines and retry association
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
