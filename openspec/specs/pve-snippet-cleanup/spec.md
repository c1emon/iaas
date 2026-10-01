# pve-snippet-cleanup Specification

## Purpose
Define evidence-bound cleanup of exact VM-owned snippets after confirmed VM deletion, with complete reference checks and fail-closed recovery.

## Requirements

### Requirement: Cleanup consumes exact original VM ownership evidence
The runtime SHALL require an explicit evidence-bound origin of deployment or acceptance, original VM/execution identity, exact generation/upload records and confirmed VM deletion before deleting snippets. Deployment cleanup SHALL additionally retain the approved delete-plan and state-persistence associations; acceptance cleanup SHALL instead consume the original acceptance request/journal and create/delete authorization without inventing plan/state evidence.

#### Scenario: Cleanup valid original records
- **WHEN** records consistently bind the selected files to the deleted VM and its deployment/delete execution
- **THEN** the runtime SHALL independently confirm VM absence and restrict deletion to the exact original list
- **AND** it SHALL NOT infer ownership from filename prefixes, VMID alone, wildcard paths or caller assertions without associated evidence

#### Scenario: Cleanup a deleted acceptance VM's remaining snippets
- **WHEN** the original acceptance request/journal proves its temporary VM identity, authorization, exact snippet list and confirmed VM deletion
- **THEN** standalone cleanup SHALL accept that origin without plan/state evidence and SHALL apply the same ownership, reference, content, serialization and absence checks
- **AND** it SHALL NOT clone, delete the VM again, rewrite the acceptance result or accept an origin switch unsupported by the original materials

#### Scenario: VM still exists or records conflict
- **WHEN** the VMID is occupied, the original identity/evidence conflicts, or ownership is missing
- **THEN** the runtime SHALL refuse deletion and report the reason without deleting the VM or altering its state

### Requirement: Complete reference checks cover shared storage
The runtime SHALL hold the existing complete mutation serialization context and establish complete VM/template reference visibility for the relevant storage scope, including shared nodes and applicable pending/snapshot configurations, before concluding that a file is unreferenced.

#### Scenario: Another object references the snippet
- **WHEN** any relevant VM or template references the selected file, including through a shared storage scope
- **THEN** that file SHALL be retained and reported as referenced

#### Scenario: Reference scope cannot be established
- **WHEN** permissions are insufficient, a query fails, storage aliasing is unresolved or scope is incomplete
- **THEN** no absence-of-reference conclusion SHALL be made and affected files SHALL NOT be deleted
- **AND** an ACL-filtered empty inventory or local-node-only scan SHALL NOT stand in for complete visibility

### Requirement: Restricted deletion rechecks exact content
Snippet deletion SHALL use the established restricted execution and trust channels, validate exact file identity and original content digest immediately before deletion, and verify the resulting absence.

#### Scenario: File matches its original record
- **WHEN** ownership, reference scope, content digest, path safety and mutual exclusion checks pass
- **THEN** the helper SHALL delete only the listed regular file and return deleted only after confirming completion
- **AND** callers SHALL NOT need arbitrary SSH rm, shell commands or broad sudo rights

#### Scenario: File is already absent or changed
- **WHEN** a legitimate exact target is conclusively absent
- **THEN** that item SHALL return already_absent
- **AND** a present file with mismatched digest/ownership SHALL return mismatch without deletion; inaccessible files and unresolved paths SHALL NOT be treated as absent

### Requirement: Cleanup retries preserve original scope
The runtime SHALL allow a new admitted cleanup execution after failure, linked to the previous cleanup and original ownership list, without replaying the VM lifecycle. First standalone cleanup SHALL declare retry_of and retry_materials as null; retry SHALL provide the previous cleanup execution ID and protected request/journal/available-result references.

#### Scenario: Retry after partial cleanup
- **WHEN** the caller supplies the original list and associations with a new cleanup execution admission
- **THEN** the runtime SHALL validate retry_of, previous request digest, unchanged origin/target/VM/ownership/full-list associations and original mutation inactivity before rechecking all deletion predicates; already absent items SHALL complete idempotently and independently safe remaining items MAY be cleaned
- **AND** the runtime SHALL NOT add files, replace expected digests, delete the VM again, write state, force-unlock or change original results

#### Scenario: Retry evidence is invalid or incomplete
- **WHEN** retry_of refers to itself or another execution, core evidence is missing, the selected list differs or previous mutation activity remains unknown
- **THEN** the runtime SHALL refuse cleanup mutation and report the conflicting or unknown association
- **AND** a missing final result alone MAY be handled with an otherwise complete bound journal without fabricating original success

#### Scenario: Repeat the same cleanup execution ID
- **WHEN** an existing cleanup execution ID is resubmitted
- **THEN** the caller SHALL route it to observe with the read-only original execution directory; matching inputs SHALL only expose original observations, conflicts SHALL be refused and missing core material SHALL return unknown without PVE mutation

### Requirement: Cleanup returns per-file and residual outcomes
The runtime SHALL return versioned execution/origin/original-VM associations, the applicable delete-plan or acceptance-request digest, and per-file deleted, already_absent, referenced, mismatch, failed or unknown outcomes with bounded reasons and residual identities.

#### Scenario: Some files cannot be cleaned
- **WHEN** a reference, mismatch, check/delete failure or uncertain outcome affects any file
- **THEN** completed files SHALL retain their independent facts and the batch SHALL NOT report passed
- **AND** incomplete global visibility SHALL block batch mutation, and unknown residual existence SHALL remain explicit

### Requirement: Standalone cleanup uses a frozen authorized window
Snippet cleanup request/result v2 SHALL carry mandatory work and cleanup deadlines using valid UTC `YYYY-MM-DDTHH:mm:ssZ` with work not later than cleanup. Both SHALL be bound to request digest, operation-specific execution admission deadlines, execution identity and durable original materials. Start and initial evidence/scope admission SHALL complete within work cutoff; facility cleanup SHALL occur only within cleanup cutoff after valid work admission. Relative timeouts SHALL only tighten these limits.

#### Scenario: Cleanup admission is late or conflicts
- **WHEN** start is at or after either cutoff, initial admission cannot finish within work cutoff, or deadline materials conflict
- **THEN** cleanup SHALL refuse new deletion and report the deadline or binding reason without obtaining admission through the later cleanup window

#### Scenario: Expired admission leaves resource existence unknown
- **WHEN** a deadline rejects admission before any facility write and file existence was not inspected
- **THEN** result/journal SHALL record admission/rejected and facility_writes none, return a nonzero exit code and retain unknown file existence with unknown-first overall aggregation
- **AND** consumers SHALL NOT interpret unknown resource state as a possible write by this execution or fabricate complete inventory

#### Scenario: Work clock moves backward before cleanup
- **WHEN** start freezes both monotonic upper bounds from the same UTC/monotonic reference and UTC subsequently moves backward during admission
- **THEN** entry into cleanup SHALL retain the original cleanup upper bound and any tightening rather than recalculate a larger budget

#### Scenario: Work window ends after valid admission
- **WHEN** initial evidence and scope admission succeeded before work cutoff and cleanup window remains valid
- **THEN** cleanup MAY continue exact-list deletion within cleanup cutoff subject to renewed per-item ownership, digest, reference and serialization checks
- **AND** no new objects or VM/state mutations SHALL be introduced

### Requirement: Deletion is checked at the native write boundary
The runtime SHALL recheck cleanup cutoff before every helper deletion dispatch and bound each call, retry and wait by remaining absolute and non-extending monotonic budgets and relative limits. The restricted helper SHALL accept the frozen cutoff via deadline protocol v2 and independently check it after lock/reference/content validation immediately before unlink. A local SSH timeout SHALL NOT establish remote termination.

#### Scenario: Delete mode omits the cutoff
- **WHEN** the explicit snippet deletion mode receives no valid cleanup cutoff
- **THEN** the helper SHALL reject mutation rather than treat absence of the field as permission to skip deadline checks

#### Scenario: Expiry during a batch
- **WHEN** the cleanup cutoff is reached after some files completed but before another dispatch or unlink
- **THEN** no later deletion SHALL start; completed per-file facts SHALL remain recorded and remaining or unknown resources SHALL remain explicit
- **AND** the batch SHALL be non-success with cleanup deadline and residual reasons

#### Scenario: Delayed helper or old protocol
- **WHEN** a helper arrives late, expires while waiting for a lock or cannot enforce the deadline protocol
- **THEN** it SHALL NOT perform deletion after cutoff or downgrade to unchecked deletion

#### Scenario: Delete response is lost
- **WHEN** a dispatched delete times out or loses its response
- **THEN** the result SHALL preserve unknown activity/outcome and original ownership evidence without declaring cancellation or assuming already_absent

### Requirement: New cleanup authority does not extend old execution
A subsequent cleanup SHALL require a new execution ID, currently valid explicit deadline-bound admission and request, retaining the previous execution/material associations and unchanged full original ownership list. Retry comparison SHALL allow only deadlines, relative timeout and retry association changes. Old request/journal/result windows SHALL remain immutable; original activity must be established as stopped before new mutation.

#### Scenario: Retry with newly approved limited authority
- **WHEN** new valid admission and deadlines bind the unchanged original full list and previous execution is proven inactive
- **THEN** a new execution MAY repeat the safety checks and clean remaining exact items without extending or rewriting the old execution or acceptance result

#### Scenario: Reuse expired authority or observe
- **WHEN** the caller reuses expired start authority or observes an existing execution after cutoff
- **THEN** expired start SHALL refuse writes and observe SHALL remain read-only without recomputing budgets or replaying cleanup
- **AND** a new output path, Runner or copied admission SHALL NOT renew authorization
