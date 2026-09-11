## Purpose

Provide a shared local and CI invocation contract for selecting the runtime, transferring caller inputs, classifying operations and retaining usable outputs across container lifecycles.

## ADDED Requirements

### Requirement: Lightweight shared invocation
The project SHALL maintain a launcher with the same operation semantics on local Docker and Forgejo DinD, without requiring the host to install Python, Ansible or OpenTofu.

#### Scenario: Invoke without an implementation checkout
- **WHEN** a caller has installed the launcher and Docker prerequisites and prepared a compatible image
- **THEN** documented component operations SHALL run through the shared interface using that image
- **AND** no implementation checkout or handwritten full docker run command SHALL be required

### Requirement: Caller-owned runtime selection and compatibility
Local and CI callers SHALL use an explicitly selected caller-owned runtime configuration; the launcher SHALL validate configuration, launcher-interface and image compatibility before generation or online execution.

#### Scenario: Use a pinned runtime
- **WHEN** a caller selects a fixed image digest and platform
- **THEN** both execution modes SHALL use that selection without implicit latest or a separate CI version default
- **AND** saved-plan artifacts SHALL record the resolved immutable image identity

#### Scenario: Unsupported combination
- **WHEN** the image, platform, configuration format or launcher interface is incompatible
- **THEN** the launcher SHALL fail with actionable compatibility guidance
- **AND** it SHALL NOT silently downgrade, select another image or enable architecture emulation

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
- **WHEN** the launcher publishes its supported component operations
- **THEN** it SHALL provide selected-input offline checks and supported non-sensitive generation, OPNsense diagnostics, switch readonly facts, PVE preflight/health and saved-plan preparation/application, services/foundation generation/checks and foundation health, and existing K3s preflight/verify/deploy/snapshot/upgrade
- **AND** PVE dependency preparation SHALL remain explicit, K3s snapshot SHALL be classified as a remote write, and existing operation prerequisites SHALL remain enforced
- **AND** the design's first-release support table SHALL be reflected in help and representative dispatch tests without arbitrary command passthrough

### Requirement: Local and daemon filesystem separation
The launcher SHALL explicitly distinguish client-local Docker path sharing from DinD file transfer and SHALL preserve declared input relationships and protected-file restrictions in both modes.

#### Scenario: DinD cannot access client paths
- **WHEN** the selected daemon cannot access the client's filesystem paths
- **THEN** declared inputs and protected files SHALL be transferred to task-owned storage with deliberate path mapping
- **AND** results SHALL be returned to the caller rather than silently retained only on the daemon
- **AND** missing files or transfer failures SHALL fail without empty bind-directory substitution or unrelated-directory copying

#### Scenario: Enforce caller permissions
- **WHEN** local or DinD operations consume protected inputs and produce outputs
- **THEN** existing secret-file and SSH host-key checks SHALL remain enforced
- **AND** outputs SHALL be usable by the caller while sensitive files retain restrictive permissions

### Requirement: Operation-specific credential injection
The launcher SHALL accept only the resolved credentials and protected files required by the selected operation, independently of the caller's secret provider.

#### Scenario: Inject credentials for one operation
- **WHEN** a local caller uses outer op run or a caller injects traditional Secrets
- **THEN** the operation SHALL consume equivalent resolved values without shipping or invoking op
- **AND** the container SHALL NOT receive a 1Password bootstrap token or unrelated host credentials
- **AND** values SHALL NOT appear in command-line arguments, ordinary logs or public reports

#### Scenario: Inject CI inputs without a developer session
- **WHEN** CI invokes the launcher
- **THEN** it SHALL consume only caller-supplied parameters, resolved credentials and protected files
- **AND** it SHALL NOT obtain credentials from a developer's local 1Password session, desktop integration or interactive shell startup files
- **AND** missing required credentials SHALL fail without falling back to local authentication

#### Scenario: Prepare secret-bearing cloud-init
- **WHEN** final cloud-init rendering requires guest user material
- **THEN** it SHALL be classified as explicit protected plan preparation rather than credential-free generate
- **AND** its output SHALL be retained as a sensitive artifact, separate from ordinary generated configuration

### Requirement: Task lifecycle and truthful exit status
The launcher SHALL isolate task-owned resources, propagate execution failures and interruption, and collect persistent results and recovery artifacts before removing their storage.

#### Scenario: Normal completion and cancellation
- **WHEN** a task completes, fails or is cancelled
- **THEN** the caller SHALL receive the actual failure, cancellation or successful outcome
- **AND** completed/failed phases and known side effects SHALL be reported without secrets
- **AND** cleanup SHALL NOT affect another task or shared state

#### Scenario: Recovery or result collection fails
- **WHEN** a task contains a unique recovery state or required persistent artifact that cannot be collected
- **THEN** its container, volume or directory SHALL remain available with a reported recovery location
- **AND** automatic cleanup SHALL NOT delete the only copy or turn the failed operation into success

#### Scenario: State-changing subprocess output
- **WHEN** the launcher executes a state-changing subprocess locally or through DinD
- **THEN** protected raw stdout/stderr capture SHALL be established inside the container before that subprocess starts, including emergency state output when file recovery fails
- **AND** container and CI logs SHALL receive only controlled non-sensitive phase/status summaries, with no direct raw stream or post-hoc-only filtering
- **AND** capture and collection failures SHALL follow the state recovery contract and SHALL NOT trigger raw-output fallback or deletion of the only retained copy

### Requirement: Classified and traceable outputs
Outputs SHALL distinguish non-sensitive generated configuration, diagnostics, sensitive plans and recovery material, and disposable work.

#### Scenario: Inspect or export task results
- **WHEN** a caller reviews results or explicitly exports generated files
- **THEN** the output SHALL include a concise selected-input and runtime-version summary using available standard metadata
- **AND** absent Git metadata or uncommitted inputs SHALL NOT be misrepresented as an exact clean revision
- **AND** sensitive plans, state and temporary data SHALL NOT be included in ordinary generated exports or automatically committed
