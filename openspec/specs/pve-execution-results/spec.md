# pve-execution-results Specification

## Purpose
Define versioned PVE execution and verification evidence that callers can register or reconcile without confusing process exits, current configuration, native state persistence, guest readiness and business acceptance.

## Requirements

### Requirement: Bound multidimensional PVE results
The runtime SHALL associate PVE results with target, plan or preview, execution identity, runtime and applicable backend/workspace, while independently reporting execution, side effects, state persistence, verification and collection.

#### Scenario: Complete a VM apply
- **WHEN** native apply completes, native state persistence is confirmed, mandatory configuration verification passes and required local result collection completes
- **THEN** the runtime SHALL report native lifecycle success with phase and state associations
- **AND** it SHALL NOT claim caller archival, publication, pending clearance, guest readiness or business acceptance that it did not perform

#### Scenario: A phase fails after partial effects
- **WHEN** upload, build, apply, verification or output collection fails after a write may have started
- **THEN** the result SHALL distinguish confirmed effects from unknown effects and stop dependent phases
- **AND** a failed or interrupted process SHALL NOT be represented as no writes merely because it returned nonzero
- **AND** native execution and later collection failures SHALL retain their separate facts

#### Scenario: Controller cannot deliver a final result
- **WHEN** the controller is forcibly terminated or its output storage becomes unavailable
- **THEN** the contract SHALL allow a missing final result and SHALL document caller retention of unknown/pending
- **AND** subsequent observations SHALL NOT synthesize an original success result

### Requirement: Verification uses the saved plan expectation
The PVE runtime SHALL expose independent read-only configuration verification bound to the original plan's expected changes, including identities retained for deleted objects.

#### Scenario: Verify changed VM configuration
- **WHEN** verification examines a selected create or update
- **THEN** it SHALL compare supported critical identity, placement, compute, disk, network, cloud-init and expected power-state facts with the saved expectation and determinate native outputs
- **AND** unknown or unsupported mandatory fields SHALL NOT pass
- **AND** current source declarations and general health warnings/skips SHALL NOT replace that expectation

#### Scenario: Verify deletion or an intentionally stopped VM
- **WHEN** the plan requires absence or a stopped VM
- **THEN** verification SHALL use that expectation instead of requiring every VM to be running or SSH-reachable
- **AND** access denial or incomplete observation SHALL NOT prove deletion

#### Scenario: No changed VM objects
- **WHEN** the native plan has no VM configuration changes
- **THEN** verification SHALL explicitly report its empty changed-object scope
- **AND** it SHALL NOT describe that outcome as whole-cluster verification or suppress separately recorded snippet effects

#### Scenario: Verify replacement without confusing old and new objects
- **WHEN** the native plan replaces a VM through delete/create or create-before-destroy actions
- **THEN** verification SHALL derive final expectations from both before and after identities and the native action ordering
- **AND** reuse of a VMID SHALL require the replacement object's expected configuration and available new-object association, not absence of that reused VMID
- **AND** a replacement using a different VMID SHALL also require absence of the old object and SHALL NOT pass with an unresolved old or deposed instance
- **AND** current configuration matches SHALL NOT alone prove that the original replacement action completed

#### Scenario: Repeat configuration verification with computed values
- **WHEN** a saved plan contains mandatory values that become determinate only during apply
- **THEN** the original apply SHALL retain a private post-apply native state or resource-result snapshot and derived expectations associated with the plan, execution and available state lineage/serial
- **AND** independent verify SHALL consume that retained association without requiring caller root outputs or implicit backend initialization
- **AND** missing, conflicting or indeterminate expectation material SHALL remain unknown rather than deriving expected values from the current device under test
- **AND** later state observations SHALL be reported as current facts, not substituted for missing original action evidence

#### Scenario: Optional guest checks are not run
- **WHEN** only native execution and configuration checks are performed
- **THEN** guest and business checks SHALL remain not_attempted or not_performed
- **AND** any caller-required guest acceptance SHALL remain an independent caller gate, not an invented native result

#### Scenario: Required caller-owned guest acceptance is unavailable
- **WHEN** the original plan requires a caller-owned guest check whose evidence is missing or unconfirmed
- **THEN** results SHALL retain the plan-bound requirement and report that external acceptance as incomplete
- **AND** successful native lifecycle facts SHALL remain separate and SHALL NOT be presented as overall acceptance completion

### Requirement: Read-only evidence supports caller reconciliation
The runtime SHALL expose read-only native interpretation and associated recovery materials without managing deployment records, replaying operations or asserting historical success from present state.

#### Scenario: Original success was not registered
- **WHEN** a caller presents complete original execution materials
- **THEN** the runtime SHALL provide their version and target/plan/execution association for caller re-registration
- **AND** it SHALL NOT rerun apply or rewrite the original result

#### Scenario: Execution failed or its result is missing
- **WHEN** a caller reads current device/state facts to reconcile an earlier execution
- **THEN** the output SHALL distinguish current observations from original action evidence and identify unresolved effects or ownership
- **AND** manual closure and the manually_reconciled deployment status SHALL remain caller decisions bound to the original execution
- **AND** no automatic rollback, state push, state removal or force-unlock SHALL occur
- **AND** manual reconciliation SHALL NOT restore the consumed plan or preview's authorization; any later mutation SHALL use newly reviewed materials and a new caller reservation

### Requirement: Sensitive recovery survives task collection failure
The runtime SHALL preserve protected native plans, configuration, state, logs and remote receipts until necessary results are collected, without exposing them as public summaries.

#### Scenario: State write or export fails
- **WHEN** native persistence fails or the sole recovery copy cannot be exported from task storage
- **THEN** the runtime SHALL retain the original recovery state or protected emergency capture and identify retained storage
- **AND** it SHALL report incomplete collection without deleting the sole copy, retrying apply or falling back to a local backend

#### Scenario: Public review and results are displayed
- **WHEN** the caller consumes a public summary
- **THEN** it SHALL contain only explicitly allowed safe identities, status and reason fields
- **AND** raw provider diagnostics, free-form resource keys, secrets, state and cloud-init content SHALL remain private

### Requirement: Plan-bound PVE verification observes target convergence
Native PVE deployment verification SHALL apply shared bounded observation to saved-plan expectations for clone/create ownership and placement, configuration/disk capacity, expected power state and deleted original-object disappearance where synchronization can be pending. Post-apply verification SHALL freeze one finite observation window at verification-group entry; independent verify SHALL freeze its own window at invocation. Each SHALL use an existing applicable finite timeout or the current internal default of 120 seconds, sharing the cutoff across all selected objects, probes and retries. Any already bound applicable execution cutoff SHALL only tighten that window without being refreshed. Actual window source/start/cutoff SHALL be retained in results. This SHALL NOT introduce required apply-admission deadline fields, new mandatory independent-verify deadline inputs or a facility admission rejection solely for their absence. Both SHALL preserve determinate native-output/state associations and fixed resource identities. Neither SHALL retry provider apply, substitute current declarations for original expectations, renew original write authority or infer action completion from matching current state. Unknown expected identity and explicit ownership/configuration conflicts SHALL stop the affected check.

#### Scenario: Apply finished before the target view synchronized
- **WHEN** determinate native output and original saved-plan bindings establish the selected object and its pending expected configuration
- **THEN** post-apply verification SHALL observe only that bound object under the once-frozen verification-group budget until convergence or a truthful stop
- **AND** provider apply SHALL NOT be invoked again

#### Scenario: Replacement or expectation cannot be proven
- **WHEN** current VMID exists but required new identity/output association is missing or conflicts
- **THEN** verification SHALL remain failed/unknown as justified rather than adopting the object or declaring the original action successful

#### Scenario: Independent verify follows a completed original window
- **WHEN** the original observation window has ended and independent verify has complete original plan/output/identity evidence
- **THEN** it SHALL observe current facts under its own bounded query window without mandatory new deadline input, renewed mutation authority or modified original results
- **AND** current configuration convergence SHALL NOT establish historical apply success

#### Scenario: No explicit verification deadline is supplied
- **WHEN** an otherwise valid apply or independent verify has no separately supplied observation deadline
- **THEN** its verification entry SHALL freeze the existing applicable finite timeout or the 120-second default rather than reject apply or perform unbounded polling
- **AND** probes for subsequent objects or transient failures SHALL retain that same cutoff

#### Scenario: An existing execution window is tighter
- **WHEN** verification is enclosed by an already bound execution deadline earlier than its local observation cutoff
- **THEN** every probe SHALL use the tighter existing bound without extending it
- **AND** expiry SHALL stop verification with unknown pending facts while preserving native execution/state/collection facts without cancelling or replaying provider apply

### Requirement: Native stop diagnostics are directly consumable
Affected native lifecycle results and consumable CLI summaries SHALL expose versioned structured stop diagnostics: completed stages/substages, stopped or failed check and reason, write-dispatch facts, associated task/PID activity with query time, resource ownership and existence separately, residual inventory completeness, per-phase/check/resource necessary safe decision evidence and recovery support/eligibility with blockers or required evidence categories. Necessary terminal evidence for every completed or failed check SHALL survive later cleanup/source observations; a global last-observation slot SHALL NOT replace it. The caller SHALL NOT need to parse private logs to obtain these facts. Unknown, not observed and known failed SHALL remain distinct; only an explicit safe field allowlist SHALL be public.

#### Scenario: Failed task and unknown residue coexist
- **WHEN** a native deletion task explicitly failed but storage visibility or current activity is incomplete
- **THEN** diagnosis SHALL report the failed task/check, completed earlier stages, original UPID, and unknown residual/activity facts independently
- **AND** overall unknown SHALL NOT erase the known task failure or imply another write was dispatched

#### Scenario: Unregistered clone resources remain
- **WHEN** clone succeeded but full ownership registration did not complete
- **THEN** diagnosis SHALL identify candidates as ownership unknown, preserve necessary observed volid/vmid/UUID/pool evidence and disclose whether bounded recovery is supported and currently eligible or needs evidence
- **AND** it SHALL NOT present partial candidates as a complete owned cleanup list

#### Scenario: Collection is interrupted
- **WHEN** no final result is available but bound journal evidence remains
- **THEN** read/observe SHALL expose only the available completed/failed facts, unknown completion or activity and incomplete collection
- **AND** it SHALL neither synthesize original success nor renew execution authority

#### Scenario: Sensitive query or exception material exists
- **WHEN** a failed check involved credentials, a private artifact URL or cloud-init content
- **THEN** consumable diagnostics SHALL expose only controlled identities, required comparison facts, statuses, timestamps and reason codes
- **AND** raw responses, sensitive values and arbitrary exception strings SHALL remain excluded

#### Scenario: Later observations follow failed claim
- **WHEN** claim recorded two relevant volid/vmid rows before failing and cleanup/source checks subsequently produced other observations
- **THEN** native diagnostics SHALL retain the original claim's necessary expected/actual fields, query time, phase and reason alongside those later checks
- **AND** consumers SHALL NOT need private logs to reconstruct either check's terminal decision
