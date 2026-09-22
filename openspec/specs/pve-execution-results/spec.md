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
