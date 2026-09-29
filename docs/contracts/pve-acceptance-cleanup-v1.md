# PVE acceptance and snippet cleanup v1

Current source implementation adds `pve-template accept` and `pve snippet-cleanup`.
It has not been published as a runtime release. Scoped live validation of the
source path is separate from qualification of a release image.
Launcher interface remains v1; capabilities advertise acceptance request/result v1
and snippet cleanup request/result v1. Existing publication record/result versions
remain v2. Consumers must check advertised capabilities before invoking an image.

## Contract artifacts

- [JSON schemas](../../automation/schemas/pve-acceptance/v1/README.md): four current request/result schemas.
- [Shared fixtures](../examples/pve-acceptance/README.md): normal and rejected inputs, used by the Python contract tests.
- [Launcher examples](../runtime-launcher.md): file mappings and start/observe commands.
- [Cleanup helper installation and permissions](../operations/pve-snippet-cleanup.md): protocol v1, exact evidence references and platform limits.

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

## Template acceptance

The request fixes a published `pve-template-record/v2`, temporary node/VMID,
storage, bridge/VLAN/IP configuration, CPU/memory/total-disk limits, boot disk and
firmware, fresh hostname, all six checks, work/guest/cleanup deadlines, and
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

Cleanup has a separate budget and runs after check failure/timeouts. It verifies
ownership and native task inactivity, stops/deletes only the clone, checks exact
VM and owned-volume absence, and rechecks source identity/configuration. Unknown
native outcomes or changed ownership retain resources. A lost delete response
cannot be converted to historical success just because the VM is now absent.
The source comparison excludes transient lock/digest fields; it is not a disk-byte
integrity attestation. No guest SSH, external connectivity or business test runs.

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
inactivity and the unchanged full original list. Only timeout/retry association
may change. Read-only evidence references are confined paths with existing
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
