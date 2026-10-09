# runtime-launcher Specification

## Purpose
Provide a shared local and CI invocation contract for selecting the runtime, transferring caller inputs, classifying operations and retaining usable outputs across container lifecycles.

## Requirements

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
- **AND** Ansible check mode, device validation, Packer configuration validation and OpenTofu native plans SHALL NOT be reported as equivalent guarantees

#### Scenario: Expose the first-release component operations
- **WHEN** the launcher publishes supported component operations
- **THEN** it SHALL retain selected-input offline checks/generation, OPNsense diagnostics and read/plan/apply/verify, switch readonly facts, services/foundation checks/generation, foundation health and existing K3s operations
- **AND** PVE SHALL expose preflight/health, explicit dependency preparation and read/plan/apply/verify, with apply exclusively consuming a selected native plan
- **AND** image SHALL expose passive check/read/verify and direct local build/test/clean, independent of PVE targets, state and mandatory preview/apply
- **AND** pve-template SHALL expose check/read/plan/apply/verify with publish, cleanup or retire previews, without requiring VM declarations, OpenTofu state or image construction
- **AND** PVE configuration verify SHALL be read-only without implicit backend initialization, while PVE state observations SHALL declare state access
- **AND** native PVE planning SHALL disclose backend locking and explicitly admitted empty-state initialization separately from read-only observation and VM mutation
- **AND** image build/test/clean SHALL disclose their local guest/file/network effects, while snapshot and template publish/cleanup/retire apply SHALL disclose remote writes
- **AND** help and representative dispatch tests SHALL reflect supported operations without arbitrary command passthrough

#### Scenario: OPNsense online plan is not a native state plan
- **WHEN** a caller invokes OPNsense read, plan or verify for one exact target
- **THEN** it SHALL be classified as online read-only with private local outputs and no device writes or state-backend access
- **AND** it SHALL NOT require S3 configuration, OpenTofu locking or a native saved plan

#### Scenario: Apply a selected OPNsense candidate
- **WHEN** a caller invokes OPNsense apply
- **THEN** it SHALL be classified as an infrastructure write, require the explicit compatible reviewed candidate and execute the same business contract on local Docker and DinD
- **AND** operation-specific file and credential selection SHALL exclude unrelated inputs and OP_* bootstrap credentials

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
The launcher SHALL isolate task-owned resources, propagate available execution failures and interruption evidence, and collect persistent results and recovery artifacts before removing their storage.

#### Scenario: Normal completion and cancellation
- **WHEN** a task completes, fails or handles cancellation
- **THEN** the caller SHALL receive the observed local outcome and any known remote outcome separately
- **AND** completed/failed phases and known or unknown side effects SHALL be reported without secrets
- **AND** cleanup SHALL NOT affect another task or shared state

#### Scenario: Controller is lost while a remote task may continue
- **WHEN** termination prevents final local reporting or disconnects observation of a native PVE API task
- **THEN** absence of a final result SHALL NOT imply remote stop or success
- **AND** callers SHALL be able to query retained journal, task and object evidence using the original execution association
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

### Requirement: Classified and traceable outputs
Outputs SHALL distinguish non-sensitive generated configuration, diagnostics, sensitive plans and recovery material, and disposable work.

#### Scenario: Inspect or export task results
- **WHEN** a caller reviews results or explicitly exports generated files
- **THEN** the output SHALL include a concise selected-input and runtime-version summary using available standard metadata
- **AND** absent Git metadata or uncommitted inputs SHALL NOT be misrepresented as an exact clean revision
- **AND** sensitive plans, state and temporary data SHALL NOT be included in ordinary generated exports or automatically committed

### Requirement: Versioned PVE execution identity and entrypoint cutover
The launcher SHALL enforce exact supported runtime, native plan/result and new template request/preview/record schemas, bind each mutation to an explicit execution identity, and reject obsolete execution paths without translation or helper write fallback.

#### Scenario: Invoke PVE lifecycle with matching contracts
- **WHEN** a caller provides a supported runtime and schema with a fresh mutation execution ID
- **THEN** discovery, selected inputs and retained results SHALL associate that same execution with its exact reviewed native plan or publication/recovery preview
- **AND** supported execution topologies SHALL preserve identical associations, permissions and credential requirements; unsupported capabilities SHALL fail explicitly
- **AND** publication SHALL require neither a retired template worker protocol nor a new space-probe helper, and independent VM snippet-helper requirements SHALL remain separate

#### Scenario: Admit a caller-reserved mutation
- **WHEN** a VM or template mutation is submitted
- **THEN** before the first facility side effect the runtime SHALL require caller execution admission bound to the selected plan or preview digest, target and execution ID
- **AND** that admission SHALL declare prior approval, durable consumption reservation and pending record, and the held complete-workflow serialization context
- **AND** missing or inconsistent associations SHALL reject execution; fresh execution IDs alone SHALL NOT replace this admission
- **AND** persistent one-time consumption and prevention of replay across runners SHALL remain caller responsibilities, without a second IaaS deployment ledger

#### Scenario: Invoke a legacy or incompatible write entrypoint
- **WHEN** a caller requests prepare-plan/apply-saved-plan, combined node template build, an old helper protocol or a repository legacy direct-write path lacking the new contract
- **THEN** it SHALL fail with migration guidance and require a new request and plan through the supported capability
- **AND** it SHALL NOT delegate to a legacy alias, translate saved artifacts or records, inject missing approvals, fall back to force replacement or invoke node CLI writes

### Requirement: Caller-owned private CA input for PVE VM operations
The launcher SHALL accept optional `files.api_ca` for PVE VM online operations through its existing selected-file transport contract. The CA SHALL remain caller-owned and SHALL NOT require embedding site certificates in the generic runtime image.

#### Scenario: Supply a private CA to an online VM operation
- **WHEN** a caller selects PVE preflight, health, read or plan with `files.api_ca`
- **THEN** local Docker and DinD SHALL make the selected file available at its mapped task path
- **AND** the operation SHALL preserve the existing public trust-file protection rules without treating the CA as an authentication secret

#### Scenario: Offline operations do not consume API trust files
- **WHEN** a caller selects offline check, generate or independent dependency preparation
- **THEN** the operation SHALL NOT load or require `files.api_ca`

#### Scenario: Transfer a saved plan with private CA material
- **WHEN** a caller selects apply or verify with a saved plan that includes private CA material
- **THEN** the launcher SHALL transfer and retain that material with the selected companions in both local Docker and DinD modes
- **AND** it SHALL NOT require the original caller CA path or substitute the current environment's `files.api_ca`

### Requirement: Separate image executor and template publisher capabilities
The launcher SHALL dispatch image and pve-template through the common component interface while preserving distinct operation sets, effects and credential requirements rather than forcing local image work into deployment plan/apply.

#### Scenario: Select a build runtime
- **WHEN** image build or test runs
- **THEN** the launcher SHALL select the pinned image-builder runtime with explicit KVM device/work mounts and resources
- **AND** it SHALL NOT expose broad privileged mode, host Docker socket or unrelated PVE/state/bootstrap credentials
- **AND** unsupported execution topology SHALL fail without hidden emulation or host modifications

#### Scenario: Use passive checks or PVE publication
- **WHEN** image check/read/verify or pve-template operations run
- **THEN** they SHALL NOT acquire unnecessary build virtualization permissions
- **AND** PVE publication SHALL only receive its artifact access and API/trust credentials, without node SSH or a space-probe helper
- **AND** check/read/verify and PVE plan SHALL NOT start guests, and PVE publication/cleanup/retire mutations SHALL require apply with exact preview association

#### Scenario: Clean local image resources
- **WHEN** image clean selects a stopped task and its resource record
- **THEN** the launcher SHALL dispatch direct local cleanup under the original task lock without a plan/apply workflow or deployment admission
- **AND** only task-owned local resources SHALL be eligible and the cleanup attempt SHALL be recorded

#### Scenario: Switch contracts directly
- **WHEN** a caller supplies legacy combined template build inputs or an unsupported schema/runtime
- **THEN** dispatch SHALL reject with migration guidance without translating inputs, parsing old records or invoking old helpers
- **AND** new outputs, help, generation and VM consumers SHALL use the new contract directly

### Requirement: Bounded PVE acceptance and snippet cleanup entrypoints
The shared launcher SHALL expose fixed-request template acceptance, acceptance recovery and standalone VM snippet cleanup with current versioned contracts, machine-readable capabilities, common consumer fixtures and truthful effect declarations.

#### Scenario: Discover or invoke the new operations
- **WHEN** a caller uses pve-template accept, pve-template recover or pve snippet-cleanup
- **THEN** the launcher SHALL require explicit start or observe mode, validate the corresponding request/admission or original execution materials, advertise start as infrastructure-writing without state writes and observe as read-only, and dispatch through the existing runtime
- **AND** missing or unsupported capability versions SHALL be rejected without adapting historical records or invoking prerequisite preparation implicitly

#### Scenario: Map original execution and cleanup evidence across Runners
- **WHEN** observe or a new cleanup execution consumes prior protected materials
- **THEN** files.original_execution_dir and files.cleanup_evidence_dir SHALL be explicitly mapped read-only as applicable, with confined relative references and identity/digest validation
- **AND** observe SHALL require no new execution admission, SHALL write only to its new collection output and SHALL NOT mutate PVE or overwrite original evidence
- **AND** missing core material SHALL prevent mutation rather than cause start fallback or reconstruction of historical success

#### Scenario: Preserve isolated trust and credentials
- **WHEN** the launcher transports acceptance, recovery or cleanup materials through local Docker or DinD
- **THEN** it SHALL preserve current TLS/private-CA validation, strict SSH host verification, protected file mapping and operation-scoped credentials
- **AND** acceptance SHALL NOT receive artifact-download credentials, recovery and snippet cleanup SHALL NOT receive state-backend or artifact-download credentials, and all original-evidence observe modes SHALL receive no operation credentials
- **AND** public output SHALL exclude raw guest, cloud-init and credential material

#### Scenario: Return incomplete or unknown execution
- **WHEN** mutation or result collection is incomplete
- **THEN** the launcher SHALL retain protected original evidence, expose failed/unknown outcomes and avoid a success exit for incomplete acceptance/cleanup
- **AND** read-only observation SHALL NOT replay an execution or manufacture historical success

#### Scenario: Deliver software capability without site qualification
- **WHEN** implementation is released
- **THEN** IaaS SHALL ship current request/result schemas, shared positive/negative examples, invocation/version notes and minimal helper installation/permissions
- **AND** software fixture results SHALL NOT be described as real PVE qualification; real VM creation/deletion SHALL require a separately bounded caller authorization

### Requirement: Launcher exposes the absolute deadline contract
Capabilities SHALL advertise v3 acceptance request/result, v1 acceptance preview/recovery request/preview/result, v2 acceptance/recovery one-shot admission and v2 standalone snippet cleanup request/result contracts and per-operation absolute_deadlines support. The launcher SHALL require matching current capability declarations and transmit frozen request/admission and protected original materials unchanged through local and DinD execution. Capability checks SHALL NOT substitute for internal native deadline enforcement.

#### Scenario: Caller selects an incompatible runtime
- **WHEN** a selected runtime lacks the current contracts or absolute deadline support
- **THEN** the launcher SHALL reject invocation without silently choosing another image, defaulting deadlines or converting relative timeouts to approval windows

#### Scenario: Delayed transport and expired observation
- **WHEN** transfer or container startup delays execution, or observe reads expired original materials
- **THEN** transmitted deadlines SHALL remain unchanged, start SHALL rely on native remaining-window checks, and observe SHALL remain read-only without renewed budgets

### Requirement: Deadline implementation has fixed consumable delivery
After implementation and scoped validation, IaaS SHALL publish a new immutable runtime release and matching launcher assets through the existing release process, documenting runtime manifest/platform digests, launcher checksums, current capabilities and deadline-aware helper installation requirements. infra-ops SHALL own calculation and persistence of deadlines from lawful target start and approved policy; IaaS SHALL enforce the received frozen windows internally.

#### Scenario: Consume the released implementation
- **WHEN** infra-ops pins the documented runtime digest and checksum-verified launcher release
- **THEN** the artifacts SHALL expose and enforce the declared deadline contract without a source checkout
- **AND** release completion SHALL require actual published artifacts rather than workflow configuration or local fixture success

#### Scenario: Report validation boundaries
- **WHEN** software tests or publication complete
- **THEN** the delivery record SHALL distinguish those results from real PVE, shared environment or production qualification

### Requirement: Controlled proxy transport in both engines
The launcher SHALL implement the runtime-network-proxy contract through local Docker and DinD, separately from credential discovery. Effective network permission SHALL determine proxy injection. Docker client defaults and image ENV SHALL NOT implicitly select a different proxy policy for task containers.

#### Scenario: Online local or DinD operation
- **WHEN** a caller invokes a compatible runtime with supported proxy variables
- **THEN** the launcher SHALL inject normalized values into the execution container without putting proxy URLs in command-line arguments
- **AND** local mounts and DinD transfer SHALL retain the same proxy semantics and existing input/credential boundaries

#### Scenario: No caller proxy or offline discovery
- **WHEN** supported caller proxy settings are absent, or the container is for capabilities, discovery, transfer or an offline operation
- **THEN** the launcher SHALL explicitly neutralize automatic proxy variables from Docker defaults or image ENV
- **AND** execution without proxy settings SHALL retain direct behavior for permitted networking while offline and discovery containers retain network isolation
- **AND** Docker context, daemon networking and image-pull policy SHALL NOT be changed by this task proxy configuration

### Requirement: Proxy capability admission
Runtime capabilities SHALL advertise network_proxy_version=1 when the controlled proxy contract, including Basic authentication protection and its explicit supported-path boundary, is implemented. For effective network-enabled operations, a launcher with any non-empty supported proxy item, including NO_PROXY alone, SHALL require that support before execution rather than silently passing configuration to an image that filters it out. Offline operations SHALL NOT require the proxy capability or parse authentication values merely because host proxy settings exist.

#### Scenario: Proxy with an incompatible image
- **WHEN** the effective operation permits networking and a supported proxy item is configured but the selected image lacks the supported proxy capability
- **THEN** the launcher SHALL fail with compatibility guidance without running the online operation
- **AND** it SHALL NOT silently drop the proxy, switch images or select a direct fallback

### Requirement: Real locked dependency consumption through the launcher
Acceptance SHALL demonstrate PVE prepare-dependencies through fixed-version launcher/runtime in local and real DinD under task-scoped direct-egress restrictions, with a reachable proxy and no facility credentials or state authority.

#### Scenario: Direct path unavailable and proxy succeeds
- **WHEN** a fresh workspace requires a locked provider package not satisfied by preinstalled or cached dependencies
- **THEN** an unproxied invocation SHALL fail in the restricted environment and a proxied invocation SHALL succeed with actual proxy/download evidence
- **AND** the archive SHALL satisfy lockfile, checksum and existing restore checks
- **AND** the operation SHALL not discover, receive or access facility credential/backend/state decoys

#### Scenario: Authenticated proxy consumption
- **WHEN** formal local and real DinD launcher invocations use a test-scoped proxy requiring Basic authentication
- **THEN** valid authentication SHALL allow actual locked dependency downloads and invalid authentication SHALL produce non-zero failure without direct fallback
- **AND** ordinary logs, error output, plans, archives and summaries SHALL contain no configured authentication material
- **AND** authentication or proxy request headers SHALL NOT be included in ordinary acceptance evidence

#### Scenario: Bypass, failure and isolation controls
- **WHEN** the same formal invocation path exercises NO_PROXY matching, an unavailable proxy and an offline operation
- **THEN** request evidence SHALL distinguish bypass and proxy routing, the unavailable proxy SHALL yield diagnosable non-zero failure without fallback, and the offline operation SHALL remain isolated
- **AND** simulated transfer tests or cached package success SHALL NOT replace real container/network consumption evidence

### Requirement: Acceptance planning and recovery have explicit effects
The launcher SHALL advertise and dispatch action=accept check/plan, action=recover plan and recover start/observe with current schema/capability gates. Offline check SHALL have no network/credentials; online plans SHALL be read-only with only necessary API/helper credentials and no state writes; recover start SHALL be infrastructure-writing without state writes; recover observe SHALL be local read-only without operation credentials.

#### Scenario: Invoke acceptance or recovery plan
- **WHEN** the selected current runtime advertises the requested action and current preview contract
- **THEN** the launcher SHALL pass fixed requests and protected evidence unchanged and collect the read-only plan into new outputs without consuming approval or implicitly preparing/mutating infrastructure
- **AND** unsupported actions or capability versions SHALL fail without selecting an alternative operation

#### Scenario: Transfer recovery input or observe through either engine
- **WHEN** local Docker or DinD executes recovery start/observe with original directories and confined references
- **THEN** original evidence SHALL be mapped read-only, new outputs SHALL not overlap originals, and start SHALL preserve new preview/admission/runtime/deadline bindings
- **AND** observe SHALL not receive API/SSH/backend credentials or refresh any execution window

### Requirement: Pool and recovery delivery includes caller adaptation instructions
After implementation and scoped verification IaaS SHALL publish a new fixed runtime version with immutable manifest/platform digests and matching checksum-verified launcher assets, current contracts/permissions and exact node helper installation/capability requirements. It SHALL deliver a run-120-1 recovery example and infra-ops adaptation checklist without modifying infra-ops or requiring record migration.

#### Scenario: Software release is delivered
- **WHEN** the release is published
- **THEN** the delivery SHALL include actual version/digests, helper update requirements, formally validated request/result/recovery examples and software test results
- **AND** release and simulated recovery SHALL be clearly separated from real VM798 cleanup, real PVE acceptance and caller promotion

#### Scenario: Real recovery lacks required materials or authorization
- **WHEN** authoritative original evidence, sufficient effective privileges or currently valid limited cleanup approval is absent
- **THEN** the real recovery status SHALL remain blocked/failed/unknown as evidenced and SHALL NOT be recorded as completed by software fixture success
- **AND** the adaptation checklist SHALL identify caller-owned inputs and acceptance prerequisites without changing infra-ops code

### Requirement: Safe public error and warning continuity
The runtime and launcher SHALL preserve critical error and warning information across protected Ansible tasks, subprocess capture, runtime public JSON and final terminal output without printing credentials, raw configuration, provider responses or uncontrolled exception text. Public messages SHALL be reconstructed from a fixed catalog with bounded approved fields.

#### Scenario: Protected task fails
- **WHEN** a no_log task fails or is unreachable
- **THEN** public output SHALL retain error classification and safe task metadata
- **AND** recognized static assertion gates SHALL retain their value-free reason
- **AND** warning presence/count SHALL remain visible while warning text stays protected

#### Scenario: Provider returns a recognized API failure
- **WHEN** an OPNsense save or activation returns field validation, authentication, permission or timeout evidence
- **THEN** the task SHALL sanitize that evidence before publishing it
- **AND** runtime and launcher SHALL display the approved field, reason and HTTP code when available
- **AND** no_log SHALL NOT be bypassed to access hidden callback payloads

#### Scenario: Runtime protects raw subprocess output
- **WHEN** a child process fails
- **THEN** runtime JSON and launcher terminal output SHALL retain the phase and exit status plus approved diagnostics
- **AND** incomplete capture and process-start failure SHALL remain explicit failures
- **AND** unknown diagnostics SHALL NOT be replaced by raw stdout/stderr

#### Scenario: Successful operation has warnings
- **WHEN** an operation succeeds but carries protected warnings or the native OPNsense evidence limitation
- **THEN** runtime JSON and launcher terminal output SHALL preserve the warning

#### Scenario: Malicious or unrecognized diagnostic text
- **WHEN** captured output or runtime diagnostics contain arbitrary code, message or field values
- **THEN** only known codes and approved fields SHALL be published with cataloged messages
- **AND** diagnostic lists and capture scanning SHALL remain bounded
