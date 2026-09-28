## ADDED Requirements

### Requirement: Fixed one-shot template clone acceptance
The runtime SHALL accept an explicitly fixed published template identity, publication record, temporary VM placement/storage/network/resource bounds, fresh cloud-init injection, required checks, deadlines and create/delete authorization for one full-clone acceptance execution.

#### Scenario: Start an authorized acceptance
- **WHEN** the caller supplies valid fixed materials and a complete execution admission
- **THEN** the runtime SHALL persist execution and request association before mutation, confirm the template identity and free VMID, perform a full clone, configure only the temporary VM and start it
- **AND** it SHALL enforce declared disk/boot expectations and resource bounds without modifying the source template or adopting existing resources

#### Scenario: Target identity or authorization is invalid
- **WHEN** the VMID is occupied, template identity differs, placement exceeds limits or create/delete authorization is missing
- **THEN** the runtime SHALL refuse dependent mutation without replacing any object or choosing another template/VMID

### Requirement: Fixed guest-agent checks establish fresh injection
The runtime SHALL require a responsive guest-agent, successful completed cloud-init and one execution-bound injected hostname matching expectation, using fixed read-only guest commands and bounded polling.

#### Scenario: Required guest checks pass
- **WHEN** the agent responds, cloud-init reports completion without errors and the fresh injected hostname matches
- **THEN** each check SHALL independently pass with protected execution evidence
- **AND** no guest SSH, external connectivity, business deployment, performance test or repeated reboot SHALL be required

#### Scenario: Guest check fails or cannot be established
- **WHEN** cloud-init failed, is disabled/unrun, required output is unavailable, the hostname is unchanged from the template baseline, or a deadline expires
- **THEN** the runtime SHALL record failed or unknown checks and their blocking stage, never pass based only on old image configuration
- **AND** it SHALL NOT remediate the guest or accept caller-provided shell commands

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
- **WHEN** final stable identity/configuration/volume comparison differs or cannot be completed
- **THEN** source verification SHALL fail or remain unknown and prevent overall acceptance success
- **AND** the runtime SHALL NOT attempt source repair or claim whole-disk byte-integrity verification

### Requirement: Repeat acceptance observes original execution
The runtime SHALL bind an acceptance execution ID to its original fixed request and durable caller reservation, preserving the original journal across result collection or controller failure. The caller SHALL atomically record the first dispatch in its existing consumption records before invoking start, and SHALL route already-dispatched or uncertain executions exclusively to observe; copied admission documents alone SHALL NOT be treated as global deduplication by IaaS.

#### Scenario: Duplicate submission
- **WHEN** the same execution ID is submitted again
- **THEN** observe SHALL use the explicitly mapped read-only original execution directory, validate its request/journal and available result bindings, expose original observations for identical inputs and reject conflicts
- **AND** missing execution evidence SHALL NOT authorize another clone, including when a new output directory or Runner is selected

#### Scenario: Previously dispatched execution loses its materials
- **WHEN** the original directory is unavailable or its core execution/request/target/admission association is incomplete
- **THEN** observe SHALL return unknown with a non-success outcome and zero PVE mutations, without falling back to start
- **AND** a missing final result with an otherwise bound journal MAY yield partial observations but SHALL NOT justify replay or invented historical success

### Requirement: Acceptance reports technical facts separately from promotion
The runtime SHALL produce a versioned result containing template and execution identity, per-check outcomes, failure stage, temporary resource ownership, cleanup outcomes, residuals and an overall passed/failed/unknown conclusion.

#### Scenario: All required checks and cleanup succeed
- **WHEN** required checks including source preservation pass, all temporary resources are confirmed cleaned and results are collected
- **THEN** overall acceptance SHALL be passed
- **AND** IaaS SHALL NOT update the caller's available registry; infra-ops promotion remains conditional on these complete results

#### Scenario: Cleanup fails after guest success
- **WHEN** a required cleanup item fails or remains unknown
- **THEN** guest success SHALL remain separately recorded and overall acceptance SHALL NOT pass
- **AND** original failure facts and unknown effects SHALL remain visible rather than being overwritten by cleanup or current observations
