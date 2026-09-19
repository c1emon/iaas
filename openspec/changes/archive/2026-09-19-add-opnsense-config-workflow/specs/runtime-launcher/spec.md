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
- **WHEN** the launcher publishes its supported component operations
- **THEN** it SHALL provide selected-input offline checks and supported non-sensitive generation, OPNsense diagnostics and explicit configuration read/plan/apply/verify, switch readonly facts, PVE preflight/health and saved-plan preparation/application, services/foundation generation/checks and foundation health, and existing K3s preflight/verify/deploy/snapshot/upgrade
- **AND** PVE dependency preparation SHALL remain explicit, K3s snapshot SHALL be classified as a remote write, and existing operation prerequisites SHALL remain enforced
- **AND** help and representative dispatch tests SHALL reflect supported operations without arbitrary command passthrough

#### Scenario: OPNsense online plan is not a native state plan
- **WHEN** a caller invokes OPNsense read, plan or verify for one exact target
- **THEN** it SHALL be classified as online read-only with private local outputs and no device writes or state-backend access
- **AND** it SHALL NOT require S3 configuration, OpenTofu locking or a native saved plan

#### Scenario: Apply a selected OPNsense candidate
- **WHEN** a caller invokes OPNsense apply
- **THEN** it SHALL be classified as an infrastructure write, require the explicit compatible reviewed candidate and execute the same business contract on local Docker and DinD
- **AND** operation-specific file and credential selection SHALL exclude unrelated inputs and OP_* bootstrap credentials
