## ADDED Requirements

### Requirement: Pre-registration recovery requires independently proven creation
Current recovery SHALL support read-only assessment of an original clone that completed but stopped before full ownership registration. The supported positive stop point SHALL retain immutable original request/preview/admission/runtime/execution bindings, free-target admission, preview-bound one-use marker carried by the original clone POST, its returned successful UPID, and a complete independently queried marker-matching candidate UUID and slot-to-volume snapshot captured before registration stopped. Initial derivation SHALL independently requery the present VM's configuration and storage content, require exactly that marker, UUID and full slot-to-volume set, expected pool/storage and each original volume's vmid ownership, and exclude source volumes before proposing ownership. This joint evidence rule SHALL bind original creation to the exact resource scope; UPID success, current VMID/name/pool, or a current marker alone SHALL NOT suffice. Missing, incomplete or conflicting original proof SHALL yield failed/unknown/needs_evidence as applicable and refuse cleanup rather than derive missing original identities from current existence. An authoritative absent VM SHALL NOT permit first-time derivation without an already independently proven frozen scope.

#### Scenario: Original task and independent resources uniquely correlate
- **WHEN** original clone POST/UPID, preview-bound marker and complete candidate snapshot are retained, and current independent configuration/content checks confirm the same marker, UUID, exact full disks and expected ownership
- **THEN** read-only recovery plan SHALL freeze the complete proven resource set and proof associations into a new preview without rewriting original journal/result
- **AND** candidates SHALL become a proposed cleanup scope only through that independent proof, not through caller assertion or present VMID alone

#### Scenario: VMID was reused or native creation proof is missing
- **WHEN** the current UUID/volume ownership conflicts or unique original creation association cannot be established
- **THEN** reconciliation SHALL fail or remain unknown as appropriate and disclose conflicting or required evidence
- **AND** recovery SHALL NOT adopt, stop or delete that VM or its disks

#### Scenario: Storage ownership view was incomplete before registration
- **WHEN** original clone/task/free-target bindings and a complete marker-matching candidate UUID/disk snapshot exist, but pool/storage-content verification failed before owned registration
- **THEN** recovery plan SHALL independently confirm the unchanged candidate identity and full disks against current config/content and source bindings before freezing the exact scope
- **AND** it SHALL NOT require a fabricated original owned resource record

#### Scenario: Marker or complete original candidate snapshot is absent
- **WHEN** original marker, UUID, complete expected disk slots or reliable original UPID is absent, even though current VMID exists and present configuration looks suitable
- **THEN** current recovery SHALL report needs_evidence/unknown without adoption or deletion
- **AND** it SHALL NOT write a marker, backfill old snapshots or accept current extra disks as original clone resources

#### Scenario: Marker matches but identity or volume set changed
- **WHEN** current marker matches while UUID, full slot-to-volume set or volume ownership differs from the original complete candidate snapshot
- **THEN** recovery SHALL reject the conflict before stop/delete
- **AND** matching marker SHALL NOT override identity, disk-set, inactivity or reference checks

### Requirement: Derived recovery scope requires new exact authority
A proven pre-registration recovery scope SHALL be treated as the complete frozen original resource scope for that new recovery and subsequent limited recovery associations, without fabricating an original registered journal record. It SHALL preserve the original candidate snapshot's full resource set and exact originally recorded snippet list, not extend it using currently attached replacement or additional disks. Start SHALL require new explicit deadline-bound approval/admission of the exact reviewed resource set and proof bindings. For a present VM it SHALL independently recheck marker, UUID and full slot-to-volume set; for an authoritatively absent VM it SHALL instead require the complete scope already independently proven and frozen while the VM was present, plus supplied prior recovery associations where applicable. Both branches SHALL verify exact remaining resource ownership, complete references, visibility, permissions and original/helper/supplied-recovery inactivity before mutation. Absence SHALL NOT authorize fresh scope derivation or a replacement VM's adoption. New evidence or approval SHALL NOT substitute for known inactivity. Recovery SHALL NOT clone, configure/start, issue guest exec, edit historical results or sweep resources outside that scope.

#### Scenario: Perform newly authorized derived-scope cleanup
- **WHEN** the reviewed derived scope is approved under a new execution and all current safety checks establish unchanged ownership and inactivity
- **THEN** recovery MAY stop/delete only those exact resources and verify absence within its new frozen window
- **AND** the original ownership-check failure and acceptance outcome SHALL remain unchanged

#### Scenario: Scope changes or task activity cannot be resolved
- **WHEN** UUID, complete disks, proof bindings or current original/helper/recovery activity conflict or remain unresolved
- **THEN** start SHALL refuse affected cleanup even with an approval and retain failed/unknown diagnostics
- **AND** it SHALL NOT widen the scope, refresh the original window or repeat the original clone

#### Scenario: VM is absent after partial derived-scope recovery
- **WHEN** a prior independently proven frozen derived scope exists, authoritative visibility confirms its VM is absent, and a new limited recovery binds the unchanged full scope and supplied prior recovery materials
- **THEN** it SHALL verify activity, ownership and complete references for the exact remaining original volumes/snippets without requiring configuration from an absent VM
- **AND** it SHALL neither delete the VM again nor add resources or replace original identity evidence

#### Scenario: VM absent without a proven scope or VMID occupied by replacement
- **WHEN** the VM is absent without an independently proven frozen scope, or its VMID is occupied by a conflicting replacement
- **THEN** recovery SHALL retain unknown or failed as justified and refuse affected cleanup
- **AND** missing current configuration SHALL NOT be used to invent original ownership or bypass a replacement conflict

### Requirement: Recovery observes tasks and disappearance without replay
Recovery SHALL use shared bounded observation semantics for each original associated task/PID and for known successful cleanup tasks followed by exact VM/volume/snippet absence checks. Permitted transient read failures and stale original-object inventories SHALL consume the same applicable recovery deadline. Explicit native task failure SHALL stop dependent processing. Unknown write acceptance or helper activity SHALL remain unknown and SHALL NOT trigger another stop/delete/unlink.

#### Scenario: Recovery deletion succeeds before storage inventory converges
- **WHEN** the original recovery delete UPID is confirmed OK but a successful storage query still shows the original volume
- **THEN** recovery SHALL continue bounded reads of the exact frozen scope under remaining cleanup time
- **AND** it SHALL not redispatch deletion

#### Scenario: Query temporarily fails or cleanup task explicitly fails
- **WHEN** an admitted task-status query temporarily fails
- **THEN** recovery SHALL continue observing the same UPID within the original remaining budget
- **AND** an explicit non-OK task outcome SHALL instead stop immediately with known failure preserved

## MODIFIED Requirements

### Requirement: Recovery plans consume bound original evidence
The system SHALL expose pve-template plan with action=recover and current versioned recovery request/preview to reconcile an original acceptance execution through read-only online checks. Inputs SHALL bind original native and caller execution identities, request/journal/available result references, original runtime and deadlines, either the complete original registered resource list or the pre-registration clone/candidate evidence mode, and any authoritative server rejection evidence. The pre-registration mode SHALL derive a complete independently proven scope through read-only planning before new cleanup authority; missing original registration alone SHALL NOT be an unsupported stop point. Missing or conflicting core bindings SHALL fail closed; original materials SHALL be read-only and preserved.

#### Scenario: Reconcile the run-120-1 retained execution
- **WHEN** the caller supplies original rc.19 materials for native execution 01591395-b75d-4108-a19d-7e5ccdb99acc-accept, associated with infra-ops execution 01591395-b75d-4108-a19d-7e5ccdb99acc and plan run-120-1
- **THEN** recovery plan SHALL validate those associations, source cohe/VM9004, original temporary cohe/VM798, original task facts and the full original UUID/volume/snippet ownership evidence
- **AND** it SHALL produce a bound reconciliation preview without clone, start, guest exec, resource deletion or modification of original evidence

#### Scenario: Original contract has no new pool or acceptance interval
- **WHEN** the retained original request predates the new acceptance pool and interval fields
- **THEN** recovery SHALL validate the original contract and digest as evidence without injecting those fields or converting it into a new start request
- **AND** new interval boundaries SHALL NOT invalidate original VM798 ownership or authorize changing its pool

#### Scenario: Original evidence is incomplete or unsafe
- **WHEN** core request/journal/caller association is absent, original identity/digest conflicts, references escape their mapped directories, or core resource ownership evidence is insufficient
- **THEN** recovery SHALL report failed/unknown reconciliation as applicable and refuse facility writes
- **AND** it SHALL NOT reconstruct historical success from current resource existence or require journal edits, execution-directory removal or clearing caller consumption records

### Requirement: Recovery conclusions remain separate from acceptance
The current versioned recovery result SHALL retain request/preview/runtime/original-execution associations, per-request reconciliation, original activity/write assessments, independent writes by the new execution, per-resource cleanup/existence, collection completeness and residuals. Success SHALL require safe confirmed cleanup/current absence for every original item and complete result collection; unknown current effects, activity or collection facts SHALL prevent success; only unlinked legacy guest-exec history MAY remain unknown under the new limited approval. Original acceptance results SHALL NOT be rewritten or promoted.

#### Scenario: Cleanup succeeds after rejected guest exec
- **WHEN** all original resources are confirmed cleaned or safely already absent and collection completes
- **THEN** recovery cleanup MAY pass while the original acceptance remains failed/unknown and its unperformed checks remain unperformed
- **AND** a subsequent acceptance SHALL require a new plan, approval and execution before caller promotion

#### Scenario: A deletion response or result collection is lost
- **WHEN** a dispatched deletion has uncertain acceptance/completion or recovery result collection is incomplete
- **THEN** recovery SHALL retain unknown effects/activity/completeness and exact remaining identities with present/absent/unknown existence
- **AND** observing current absence SHALL NOT convert the lost response into historical deletion success

### Requirement: Current acceptance snapshot recovery
Exact recovery SHALL accept retained current acceptance request/result snapshots with their original preview, admission, runtime, policy, identity and digest bindings, without rewriting original evidence or adding legacy compatibility.

#### Scenario: Clean resources after a current native deletion failure
- **WHEN** a current acceptance execution has retained ownership evidence and its native tasks are confirmed inactive
- **THEN** a newly admitted recovery MAY clean only that execution's complete original resources
- **AND** the original acceptance result SHALL remain unchanged even if recovery cleanup succeeds

#### Scenario: Refuse conflicting current snapshots
- **WHEN** the current request, journal, preview, admission, runtime, result or source bindings conflict
- **THEN** recovery SHALL reject the materials before any facility query or mutation
