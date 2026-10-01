## MODIFIED Requirements

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

## ADDED Requirements

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
