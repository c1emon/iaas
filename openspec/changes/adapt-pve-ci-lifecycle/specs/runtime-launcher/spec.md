## MODIFIED Requirements

### Requirement: Explicit operation effects
Help and results SHALL distinguish offline checks, generation, dependency preparation, device diagnostics, plans and mutations by networking, state access, local outputs and infrastructure side effects.

#### Scenario: Pure offline check or generation
- **WHEN** the launcher and image are prepared and check or non-sensitive generate runs with networking disabled and no credentials
- **THEN** valid selected inputs SHALL succeed without S3, device access, secret resolution or dependency installation
- **AND** generated outputs SHALL NOT modify caller sources

#### Scenario: Prepare dependencies separately
- **WHEN** locked provider or module dependencies are not prepared
- **THEN** an explicit dependency-preparation operation SHALL be required for their downloads
- **AND** it SHALL preserve the caller lockfile and distinguish backend-disabled preparation from online state operations

#### Scenario: Request an unsupported operation or missing target
- **WHEN** a component has no supported requested operation or an online operation lacks its explicit target/scope
- **THEN** the launcher SHALL fail without executing an alternative or selecting all devices
- **AND** Ansible check mode, device validation and OpenTofu plans SHALL NOT be reported as equivalent guarantees

#### Scenario: Expose the first-release component operations
- **WHEN** the launcher publishes supported component operations
- **THEN** it SHALL retain selected-input offline checks/generation, OPNsense diagnostics and read/plan/apply/verify, switch readonly facts, services/foundation checks/generation, foundation health and existing K3s operations
- **AND** PVE SHALL expose preflight/health, explicit dependency preparation and read/plan/apply/verify, with apply exclusively consuming a selected native plan
- **AND** pve-template SHALL expose independent check/read/plan/apply/verify for build and explicit cleanup previews, without requiring VM declarations or S3
- **AND** PVE configuration verify SHALL be read-only without implicit backend initialization, while PVE state observations SHALL declare state access
- **AND** native PVE planning SHALL disclose backend locking and explicitly admitted empty-state initialization separately from read-only observation and VM mutation
- **AND** snapshot and template build/cleanup apply SHALL be classified as remote writes
- **AND** help and representative dispatch tests SHALL reflect supported operations without arbitrary command passthrough

#### Scenario: OPNsense online plan is not a native state plan
- **WHEN** a caller invokes OPNsense read, plan or verify for one exact target
- **THEN** it SHALL be classified as online read-only with private local outputs and no device writes or state-backend access
- **AND** it SHALL NOT require S3 configuration, OpenTofu locking or a native saved plan

#### Scenario: Apply a selected OPNsense candidate
- **WHEN** a caller invokes OPNsense apply
- **THEN** it SHALL be classified as an infrastructure write, require the explicit compatible reviewed candidate and execute the same business contract on local Docker and DinD
- **AND** operation-specific file and credential selection SHALL exclude unrelated inputs and OP_* bootstrap credentials

### Requirement: Task lifecycle and truthful exit status
The launcher SHALL isolate task-owned resources, propagate available execution failures and interruption evidence, and collect persistent results and recovery artifacts before removing their storage.

#### Scenario: Normal completion and cancellation
- **WHEN** a task completes, fails or handles cancellation
- **THEN** the caller SHALL receive the observed local outcome and any known remote outcome separately
- **AND** completed/failed phases and known or unknown side effects SHALL be reported without secrets
- **AND** cleanup SHALL NOT affect another task or shared state

#### Scenario: Controller is lost while a remote task may continue
- **WHEN** termination prevents final local reporting or disconnects a remote template worker
- **THEN** absence of a final result SHALL NOT imply remote stop or success
- **AND** callers SHALL be able to query available retained evidence using the original execution identity
- **AND** the launcher SHALL NOT promise delivery from a terminated controller or automatically replay remote work

#### Scenario: Recovery or result collection fails
- **WHEN** a task contains a unique recovery state or required persistent artifact that cannot be collected
- **THEN** its container, volume or directory SHALL remain available with a reported recovery location
- **AND** automatic cleanup SHALL NOT delete the only copy or turn the failed operation into success

#### Scenario: State-changing subprocess output
- **WHEN** the launcher executes a state-changing subprocess locally or through DinD
- **THEN** protected raw stdout/stderr capture SHALL be established inside the container before that subprocess starts, including emergency state output when file recovery fails
- **AND** container and CI logs SHALL receive only controlled non-sensitive phase/status summaries, with no direct raw stream or post-hoc-only filtering
- **AND** capture and collection failures SHALL follow the state recovery contract and SHALL NOT trigger raw-output fallback or deletion of the only retained copy

## ADDED Requirements

### Requirement: Versioned PVE execution identity and entrypoint cutover
The launcher SHALL discover and enforce PVE plan/result and template helper compatibility, bind each mutation to an explicit execution identity, and reject obsolete execution paths rather than bypass new admission.

#### Scenario: Invoke PVE lifecycle with matching contracts
- **WHEN** a caller provides a supported runtime/helper and fresh mutation execution ID
- **THEN** discovery, selected inputs and retained results SHALL associate that same execution with its exact reviewed plan or preview
- **AND** local Docker and DinD SHALL preserve identical associations, permissions and credential requirements

#### Scenario: Admit a caller-reserved mutation
- **WHEN** a VM or template mutation is submitted
- **THEN** before the first facility side effect the runtime SHALL require caller execution admission bound to the selected plan or preview digest, target and execution ID
- **AND** that admission SHALL declare prior approval, durable consumption reservation and pending record, and the held complete-workflow serialization context
- **AND** missing or inconsistent associations SHALL reject execution; fresh execution IDs alone SHALL NOT replace this admission
- **AND** persistent one-time consumption and prevention of replay across runners SHALL remain caller responsibilities, without a second IaaS deployment ledger

#### Scenario: Invoke a legacy or incompatible write entrypoint
- **WHEN** a caller requests prepare-plan/apply-saved-plan, an old helper protocol or a repository legacy direct-write path lacking the new contract
- **THEN** it SHALL fail with migration guidance or delegate exclusively to the new contract with all required explicit inputs
- **AND** it SHALL NOT silently translate old saved artifacts, inject missing approvals or fall back to force replacement
