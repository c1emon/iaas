# pve-acceptance-recovery Specification

## Purpose
Define read-only reconciliation of a retained PVE acceptance execution and newly authorized cleanup of its exact original resources, preserving historical results, finite deadlines, ownership and uncertainty.

## Requirements

### Requirement: Recovery plans consume bound original evidence
The system SHALL expose pve-template plan with action=recover and recovery request/preview v1 to reconcile an original acceptance execution through read-only online checks. Inputs SHALL bind original native and caller execution identities, request/journal/available result references, original runtime and deadlines, complete frozen resource list and any authoritative server rejection evidence. Missing or conflicting core bindings SHALL fail closed; original materials SHALL be read-only and preserved.

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

### Requirement: Reconciliation resolves only uniquely proven rejected requests
Recovery MAY use retained independent dispatch traces and trusted server rejection evidence to establish a specific pre-execution rejection. It SHALL NOT require reconstructed traces, matching IaaS identifiers in PVE logs or a complete historical evidence system. Missing or ambiguous correlation SHALL preserve historical unknown. The reviewed preview SHALL disclose uncertainty for an administrator decision through the existing new limited cleanup approval.

#### Scenario: Original guest exec has authoritative permission rejection
- **WHEN** a trusted unique match establishes that the original guest exec POST was rejected with HTTP403 before execution and all other relevant tasks/helper operations are proven inactive
- **THEN** recovery SHALL classify that request as request_rejected and remove only its active uncertainty in the new reconciliation record
- **AND** original clone/configure/start facts SHALL remain issued, while original guest check outcomes and result bytes SHALL remain unchanged

#### Scenario: Rejection evidence cannot establish unique dispatch association
- **WHEN** a log match is ambiguous, provenance is untrusted, principal/path differs, or the only evidence is current missing permission or absent PID
- **THEN** the original request outcome SHALL remain unknown and the preview SHALL indicate administrator_decision
- **AND** an existing new scoped approval MAY authorize cleanup after current ownership/reference checks without rewriting historical unknown

#### Scenario: Another original operation remains uncertain
- **WHEN** an original or retained recovery native task is confirmed running, its UPID status cannot be queried, the returned status is invalid, or helper/recovery activity remains unresolved
- **THEN** that activity SHALL block affected resource cleanup even under a new administrator approval
- **AND** only missing historical guest-exec association without a UPID/PID MAY be dispositioned through the existing new limited approval

#### Scenario: Original UPID query times out after planning
- **WHEN** a reviewed recovery preview was eligible but a current original UPID status query times out during start
- **THEN** start SHALL report task_activity_unresolved and refuse all cleanup writes, including helper deletion
- **AND** existing scoped approval SHALL NOT substitute for current activity verification

### Requirement: New cleanup authority preserves original scope and deadlines
pve-template recover start SHALL require a new execution ID and current explicit limited cleanup authorization/admission binding the recovery request/preview, selected runtime digest, original native execution, caller pending/consumption association, full original resource list and new finite work/cleanup deadlines. Both cutoffs SHALL be valid UTC YYYY-MM-DDTHH:mm:ssZ with work not later than cleanup; relative limits SHALL only tighten them. Original deadlines SHALL remain immutable; recovery SHALL freeze its new bounds from a single start time reference and SHALL NOT replay original acceptance operations.

#### Scenario: Clean after the original window expired
- **WHEN** the old execution cutoff has passed but new cleanup authority and deadlines are valid, current ownership is established and relevant current task/helper activity is established inactive
- **THEN** recovery SHALL perform admission/reconciliation within the new work window and only authorized cleanup within the new cleanup window
- **AND** it SHALL NOT refresh the old window, reuse old approval, clone, configure/start the original VM or issue guest exec

#### Scenario: Approved recovery bindings change
- **WHEN** pool bindings where originally present, full resource identities, original execution, request/preview, runtime or new deadlines differ from the approved recovery
- **THEN** start SHALL reject before facility writes rather than widen scope or select replacement resources
- **AND** absence of a historical pool binding SHALL NOT allow a fabricated new ownership binding

#### Scenario: New recovery reaches a cutoff
- **WHEN** admission is late or stop/delete/helper dispatch reaches its applicable absolute or non-extending monotonic cutoff
- **THEN** no new dependent write SHALL be issued and completed facts plus unknown residual existence/activity SHALL remain explicit
- **AND** timeout SHALL NOT imply cancellation or rollback

### Requirement: Recovery deletes only exactly owned approved resources
Recovery SHALL recheck actual ownership, UUID, complete frozen volume set, applicable historical pool binding, effective cleanup permissions and conflicting or unresolved current activity before stop/delete. Resource absence SHALL be established under sufficient visibility. Complete helper reference evidence SHALL suffice without requiring an independently unfiltered API VM inventory; the API fallback SHALL require sufficient inventory visibility when helper reference evidence is unavailable. Mutation permissions SHALL be required only for present resources requiring those actions. Volumes and snippets SHALL receive exact ownership/digest/reference safety checks, and pools SHALL remain intact.

#### Scenario: Clean the VM and original owned disks and snippet
- **WHEN** the approved original VM/UUID and two exact owned volumes are confirmed, relevant current task/helper activity is established inactive, and the frozen snippet ownership/digest/reference evidence is complete
- **THEN** recovery SHALL stop/delete only that VM as needed, verify original volume absence, then clean only the safe frozen snippet under complete reference visibility
- **AND** it SHALL preserve the source template, pools, ACLs and unrelated resources and retain original created_by identity

#### Scenario: VM is absent but frozen volumes remain
- **WHEN** current authoritative observation confirms the VM absent while some original volume remains
- **THEN** recovery SHALL report the VM currently absent without claiming historical deletion success
- **AND** independent deletion SHALL be allowed only for the exact original volume with proven original/current ownership, no external reference and valid scoped authority; otherwise it SHALL remain failed/unknown residue

#### Scenario: Identity ownership or references differ
- **WHEN** UUID, the current attached volume set, applicable pool, snippet digest or resource reference conflicts, or visibility is incomplete
- **THEN** affected deletion SHALL be refused and remaining existence SHALL be reported as observed or unknown
- **AND** recovery SHALL NOT force-unlock, select by prefix, sweep unreferenced resources or adopt resources using pool/VMID alone

#### Scenario: Source template currently differs from its historical state
- **WHEN** the original source association is bound but current source configuration changed or cannot be queried, and the independent full clone's ownership/inactivity and cleanup authority are established
- **THEN** recovery SHALL preserve the historical source result and report current source observations separately without treating them alone as a cleanup blocker
- **AND** it SHALL neither mutate the source nor use current observations to promote the original acceptance

### Requirement: Recovery conclusions remain separate from acceptance
Recovery result/v1 SHALL retain request/preview/runtime/original-execution associations, per-request reconciliation, original activity/write assessments, independent writes by the new execution, per-resource cleanup/existence, collection completeness and residuals. Success SHALL require safe confirmed cleanup/current absence for every original item and complete result collection; unknown current effects, activity or collection facts SHALL prevent success; only unlinked legacy guest-exec history MAY remain unknown under the new limited approval. Original acceptance results SHALL NOT be rewritten or promoted.

#### Scenario: Cleanup succeeds after rejected guest exec
- **WHEN** all original resources are confirmed cleaned or safely already absent and collection completes
- **THEN** recovery cleanup MAY pass while the original acceptance remains failed/unknown and its unperformed checks remain unperformed
- **AND** a subsequent acceptance SHALL require a new plan, approval and execution before caller promotion

#### Scenario: A deletion response or result collection is lost
- **WHEN** a dispatched deletion has uncertain acceptance/completion or recovery result collection is incomplete
- **THEN** recovery SHALL retain unknown effects/activity/completeness and exact remaining identities with present/absent/unknown existence
- **AND** observing current absence SHALL NOT convert the lost response into historical deletion success

### Requirement: Repeated recovery uses protected observation or fresh authority
The caller SHALL route an already dispatched recovery execution exclusively to observe using its original protected recovery directory. Observe SHALL be local read-only, credential-free and shall not construct budgets. Further cleanup SHALL require new bound materials and authority retaining the full original list and supplied prior recovery associations, without requiring a complete historical chain; supplied prior recovery activity SHALL be established inactive, and only unlinked legacy guest-exec history MAY remain unknown. Partial/unknown available result resource rows SHALL be informational unless they conflict with original identity or ownership. Complete current absence and known new effects MAY establish cleanup success while original activity/writes/acceptance remain unknown.

#### Scenario: Observe after expiry or on another Runner
- **WHEN** the same recovery execution is collected after expiry using new output paths
- **THEN** observe SHALL validate and expose only the bound existing materials without facility writes, credentials or renewed deadlines
- **AND** missing materials SHALL return unknown/non-success without falling back to start

#### Scenario: A later limited recovery cleans remaining items
- **WHEN** relevant current task/helper activity is established inactive and a fresh plan/approval binds the unchanged full original list and supplied prior recovery evidence, disclosing remaining historical unknown
- **THEN** a new recovery execution MAY safely check and clean remaining exact resources within its new window
- **AND** it SHALL preserve completed and unknown historical facts, original consumption history and original acceptance conclusion

### Requirement: Current acceptance snapshot recovery
Exact recovery SHALL accept retained current v3 acceptance request/result snapshots with their original preview, admission, runtime, policy, identity and digest bindings, without rewriting original evidence or adding legacy compatibility.

#### Scenario: Clean resources after a current native deletion failure
- **WHEN** a current acceptance execution has retained ownership evidence and its native tasks are confirmed inactive
- **THEN** a newly admitted recovery MAY clean only that execution's complete original resources
- **AND** the original acceptance result SHALL remain unchanged even if recovery cleanup succeeds

#### Scenario: Refuse conflicting current snapshots
- **WHEN** the current request, journal, preview, admission, runtime, result or source bindings conflict
- **THEN** recovery SHALL reject the materials before any facility query or mutation
