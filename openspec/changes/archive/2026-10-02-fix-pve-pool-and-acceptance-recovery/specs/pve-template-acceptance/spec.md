## MODIFIED Requirements

### Requirement: Fixed one-shot template clone acceptance
The runtime SHALL accept an explicitly fixed published template identity, publication record, temporary VM placement/pool/storage/network/resource bounds, caller acceptance VMID interval, pinned runtime, fresh cloud-init injection, required checks, deadlines and create/delete authorization for one full-clone acceptance execution.

#### Scenario: Start an authorized acceptance
- **WHEN** the caller supplies valid current request/preview materials and a complete matching execution admission
- **THEN** the runtime SHALL persist execution and request association before mutation, confirm the template identity and free VMID, perform a full clone directly into the required pool, configure only the temporary VM and start it
- **AND** it SHALL enforce declared disk/boot expectations and resource bounds without modifying the source template or adopting existing resources

#### Scenario: Target identity or authorization is invalid
- **WHEN** the VMID is occupied, template identity differs, placement exceeds limits or create/delete authorization is missing
- **THEN** the runtime SHALL refuse dependent mutation without replacing any object or choosing another template/VMID

### Requirement: Absolute deadlines are execution-bound
Acceptance request/result v3 SHALL carry frozen `deadlines.work_deadline_at` and `deadlines.cleanup_deadline_at` in valid UTC `YYYY-MM-DDTHH:mm:ssZ` format with work not later than cleanup. The runtime SHALL bind both values into the canonical request and preview digests, matching operation-specific execution admission deadlines, execution identity and persisted request/admission/journal/result. Relative timeouts SHALL only impose stricter local limits.

#### Scenario: Deadline binding or format is invalid
- **WHEN** a required cutoff is missing, malformed, calendar-invalid, incorrectly ordered or conflicts with admission or original materials
- **THEN** the runtime SHALL refuse dependent facility mutation without deriving a replacement window

#### Scenario: Start has arrived too late
- **WHEN** start reaches admission at or after either frozen cutoff
- **THEN** it SHALL return a non-success deadline rejection with zero facility writes and preserve the execution association and rejection reason
- **AND** it SHALL record admission/rejected and facility_writes none separately from resource state; unchecked existence SHALL remain unknown and overall SHALL follow unknown-first aggregation without invented inventory

### Requirement: Acceptance cleanup respects ownership and task uncertainty
The runtime SHALL attempt cleanup after success, check failure or timeout within a separate cleanup budget, removing only confirmed execution-owned temporary resources after establishing relevant mutation inactivity.

#### Scenario: Clean a confirmed temporary VM
- **WHEN** native tasks are confirmed finished and the temporary VM and attached volumes belong to this execution
- **THEN** the runtime SHALL stop/delete that VM, verify absence of it and its owned volumes, and clean exclusively generated snippets with the controlled snippet safety checks
- **AND** inherited or shared source resources SHALL NOT be included merely because they are attached or share a VMID prefix

#### Scenario: Ownership or task outcome is unknown
- **WHEN** clone/start/delete may still run or resource ownership cannot be confirmed
- **THEN** the runtime SHALL retain affected resources, report exact known and potentially remaining identities and leave the conclusion unknown
- **AND** it SHALL NOT force-unlock, delete by prefix or blindly replay the lifecycle

#### Scenario: Only acceptance-owned snippets remain after VM deletion
- **WHEN** temporary VM deletion is confirmed but its exclusively generated snippets were not completely cleaned
- **THEN** a new standalone snippet-cleanup execution MAY consume the original acceptance request/journal, create/delete authorization, exact ownership list and deletion evidence without an OpenTofu plan or state
- **AND** it SHALL repeat the same safety checks without cloning, deleting the VM again, changing the original acceptance result or hiding other residuals

#### Scenario: Source template changes or cannot be rechecked
- **WHEN** a completed comparison against an established baseline confirms stable identity/configuration/volume differences, or an attempted query cannot be completed
- **THEN** source verification SHALL fail only for confirmed changes and otherwise remain unknown, preventing overall acceptance success
- **AND** the runtime SHALL NOT attempt source repair or claim whole-disk byte-integrity verification

## ADDED Requirements

### Requirement: Acceptance has a read-only reviewed plan
pve-template check with action=accept SHALL validate current acceptance request/v3 offline without credentials/network. pve-template plan with action=accept SHALL perform complete read-only online admission and emit acceptance-preview/v1. Start SHALL bind request/preview digests, target, stable cluster scope, runtime, pool, concrete VMID, reservation interval and frozen deadlines to current approval and actual execution before any facility write. Its journal SHALL retain the validated preview snapshot and digest so protected observation and original-material consumers can verify that association without rebuilding the plan.

#### Scenario: Plan acceptance with fixed resources
- **WHEN** current input fixes the source, nonempty pool, temporary VMID inside its inclusive interval, storage/network/resource bounds, runtime and deadlines
- **THEN** plan SHALL return a machine-readable bound preview including readiness and total-capacity diagnostics without clone, upload, startup, guest exec or state writes
- **AND** planning SHALL NOT consume a mutation approval or create a VMID reservation in IaaS

#### Scenario: Pool interval runtime or cutoff binding differs
- **WHEN** execution changes approved pool, interval, VMID, runtime or either cutoff, or lacks the matching preview/admission
- **THEN** start SHALL refuse dependent facility writes without replanning, filling missing values or substituting another runtime

### Requirement: Acceptance pool is mandatory and independently verified
Every new temporary acceptance VM SHALL declare a nonempty existing pool, and the full clone request SHALL directly specify it. Start and cleanup SHALL confirm actual membership before their mutations while independently retaining execution identity, UUID, exact frozen resource ownership and inactivity checks. Pool membership SHALL NOT authorize ownership or deletion of other members.

#### Scenario: Pool is missing or unusable
- **WHEN** pool is omitted/empty, authoritative evidence confirms it absent, or effective operation permissions are insufficient
- **THEN** check or online admission as applicable SHALL refuse before cloning or starting any VM
- **AND** execution SHALL NOT fall back to no pool or create/authorize a pool

#### Scenario: Actual membership changes
- **WHEN** the cloned VM is outside its approved pool before startup or cleanup
- **THEN** the dependent mutation SHALL be refused with pool_membership_mismatch and known resources retained
- **AND** matching VMID or another pool member SHALL NOT be adopted as this execution's resource

#### Scenario: Full acceptance and cleanup complete
- **WHEN** pool membership and all independent acceptance/ownership checks pass and exact temporary cleanup succeeds
- **THEN** only the execution-owned temporary VM, disks and generated snippets SHALL be removed
- **AND** the pool, its ACLs, the source template and unrelated members SHALL remain intact

### Requirement: Rejected requests and unknown outcomes remain distinct
The runtime SHALL record bounded phase, request classification and necessary HTTP status for failures. A uniquely established pre-execution interface rejection SHALL end only that request's active uncertainty; timeouts, connection interruption and possible acceptance with missing responses SHALL remain unknown. Prior successful clone/configuration/start/upload facts SHALL NOT be erased.

#### Scenario: Guest exec receives authoritative permission 403
- **WHEN** the guest exec API rejects the request before acceptance/execution with confirmed HTTP403
- **THEN** its request SHALL be recorded rejected, the cloud-init check SHALL fail with request_rejected and HTTP403, and that request SHALL no longer be active/unknown
- **AND** prior facility writes SHALL remain issued and cleanup MAY proceed only if no other conflict/unknown remains and current ownership/authority/cleanup window are valid

#### Scenario: Guest exec response is lost
- **WHEN** guest exec may have been accepted but times out or loses its response
- **THEN** its request and active outcome SHALL remain unknown, required checks SHALL NOT pass, and dependent destructive cleanup SHALL be refused
- **AND** current VM state or missing PID SHALL NOT prove the request unexecuted

#### Scenario: A different request still has unknown activity
- **WHEN** one request is clearly rejected but another dispatched task/helper remains uncertain
- **THEN** aggregate mutation activity and facility_writes SHALL preserve that uncertainty and prevent unsafe cleanup
- **AND** phase classification SHALL remain specific rather than flatten all errors to observation_unknown

### Requirement: Source consistency diagnostics require an established comparison
Source verification SHALL distinguish source_changed, source_snapshot_missing, source_query_failed and source_evidence_insufficient. Confirmed identity/configuration/volume differences against a bound baseline SHALL fail; missing snapshot or insufficient/query evidence SHALL remain unknown. Original primary failure stage/reason SHALL survive final recheck and cleanup.

#### Scenario: Capacity fails before initial snapshot is saved
- **WHEN** disk_limit_exceeded occurs before an initial source snapshot is established
- **THEN** source_unchanged SHALL be unknown with source_snapshot_missing and the original capacity failure SHALL remain visible
- **AND** the result SHALL NOT describe the missing snapshot as confirmed source mutation

#### Scenario: Source changes or cannot be observed
- **WHEN** an established source comparison confirms a different UUID/configuration/volume, or query/evidence prevents comparison
- **THEN** the result SHALL respectively report source_changed/failed or the applicable query/evidence reason with unknown
- **AND** acceptance SHALL remain non-success without source repair

### Requirement: Total disk bounds include owned auxiliary disks before clone
Acceptance plan and execution preflight SHALL calculate total_required_bytes for all disks cloned/generated for the temporary VM, including system, cloud-init, EFI, TPM and other owned auxiliary disks. They SHALL compare that total against disk_limit_bytes and applicable storage capacity before clone, return a bounded limit/total/per-disk diagnostic and refuse unknown sizes. Post-clone checks SHALL continue to enforce the bound.

#### Scenario: Forty GiB system disk has an additional cloud-init disk
- **WHEN** source requires 40 GiB plus 4 MiB cloud-init and disk_limit_bytes is 40 GiB
- **THEN** plan/start SHALL report 42,953,867,264 required bytes and disk_limit_exceeded before clone
- **AND** they SHALL NOT exclude auxiliary disks or automatically raise the limit; a changed bound SHALL require a new plan/approval

#### Scenario: Auxiliary size or capacity is insufficient
- **WHEN** a required disk size cannot be established or the known target storage capacity is insufficient
- **THEN** admission SHALL refuse before cloning with disk_size_unknown or storage_capacity_insufficient respectively
- **AND** EFI/TPM and other owned disks SHALL follow the same total-bound rule without an exhaustive platform matrix
