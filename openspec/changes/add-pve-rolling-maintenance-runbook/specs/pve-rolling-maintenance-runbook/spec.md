## ADDED Requirements

### Requirement: PVE rolling maintenance runbook
The system SHALL provide a documentation-only runbook for planned PVE rolling maintenance.

#### Scenario: Operator opens the rolling maintenance runbook
- **WHEN** an operator needs to plan PVE reboot-only or package-update maintenance
- **THEN** the repository SHALL provide a runbook under `docs/runbooks/`
- **AND** the runbook SHALL describe safety boundaries, prechecks, per-node procedure, postchecks, abort criteria, and recordkeeping guidance
- **AND** it SHALL make clear that all maintenance actions are manual operator actions in the first version

#### Scenario: Default offline validation runs
- **WHEN** an operator or CI runs the default offline validation path
- **THEN** the rolling maintenance runbook SHALL NOT cause VM migration, VM shutdown, node reboot, package update, Ceph mutation, PVE mutation, or network mutation
- **AND** it SHALL NOT require PVE API, SSH, 1Password, or apply-capable credentials

### Requirement: Maintenance precheck and postcheck gates
The runbook SHALL define explicit health and verification gates around maintenance.

#### Scenario: Operator prepares for planned maintenance
- **WHEN** an operator prepares for normal planned PVE maintenance
- **THEN** the runbook SHALL require `make pve-health` to complete with no failures before maintenance starts
- **AND** it SHALL require warnings to be reviewed and accepted or resolved before proceeding
- **AND** it SHALL recommend capturing a guest baseline with `make pve-verify-guests` when guest SSH context is available

#### Scenario: Operator completes maintenance on one node
- **WHEN** a maintained node returns to service
- **THEN** the runbook SHALL require a post-node health gate before continuing to another node
- **AND** it SHALL require any warnings to be reviewed before proceeding

#### Scenario: Operator completes the full maintenance window
- **WHEN** all intended nodes have been maintained or the window is stopped
- **THEN** the runbook SHALL require final `make pve-health` verification
- **AND** it SHALL recommend `make pve-verify-guests` or a recorded reason for skipping guest verification

### Requirement: Single-node and multi-node maintenance flows
The runbook SHALL distinguish single-node maintenance from multi-node rolling maintenance.

#### Scenario: Environment is effectively single-node
- **WHEN** the target environment has only one required/available PVE node for declared workloads
- **THEN** the runbook SHALL present a single-node maintenance branch
- **AND** it SHALL require the operator to accept planned downtime where applicable
- **AND** it SHALL NOT describe the procedure as no-downtime rolling maintenance

#### Scenario: Environment supports multi-node maintenance
- **WHEN** the environment has multiple suitable PVE nodes
- **THEN** the runbook SHALL describe maintaining one node at a time
- **AND** it SHALL require preserving quorum and verifying health after each node before continuing

### Requirement: VM handling policy during maintenance
The runbook SHALL document manual VM handling decisions before a node is maintained.

#### Scenario: Long-lived VM has no passthrough constraints
- **WHEN** a long-lived VM runs on the target maintenance node and does not have passthrough constraints
- **THEN** the runbook SHALL guide the operator to decide between migration, controlled shutdown, or deferring maintenance based on capacity and service tolerance
- **AND** any migration or shutdown SHALL be a manual operator action

#### Scenario: Long-lived VM has passthrough constraints
- **WHEN** a long-lived VM on the target node uses passthrough hardware or other non-migratable constraints
- **THEN** the runbook SHALL warn that live migration is usually not appropriate
- **AND** it SHALL guide the operator to plan downtime or defer maintenance

#### Scenario: Ephemeral lab VM is on the target node
- **WHEN** an ephemeral lab VM is on the target maintenance node
- **THEN** the runbook SHALL allow the operator to leave it stopped or handle it manually
- **AND** it SHALL NOT implicitly destroy, recreate, or mutate ephemeral VMs

### Requirement: Manual package update and reboot guidance
The runbook SHALL document reboot-only and package-update maintenance as manual workflows.

#### Scenario: Reboot-only maintenance is selected
- **WHEN** the operator selects reboot-only maintenance
- **THEN** the runbook SHALL guide the operator through health checks, workload handling, manual reboot, node return verification, and guest verification

#### Scenario: Package-update maintenance is selected
- **WHEN** the operator selects package-update-and-reboot maintenance
- **THEN** the runbook SHALL guide the operator to review package plans and PVE repository/channel expectations before manual package update commands
- **AND** package update and reboot commands SHALL remain manual operator actions

### Requirement: Conditional Ceph guidance
The runbook SHALL include Ceph guidance only as conditional, non-mutating operator guidance.

#### Scenario: Ceph is not configured
- **WHEN** the environment does not use Ceph
- **THEN** the runbook SHALL allow operators to skip Ceph-specific steps

#### Scenario: Ceph is configured
- **WHEN** a future environment uses Ceph
- **THEN** the runbook SHALL instruct operators to review Ceph health before node maintenance
- **AND** it SHALL keep `noout` or other Ceph flag changes as explicit manual operator decisions
- **AND** it SHALL NOT automate Ceph mutation

### Requirement: Abort and continue criteria
The runbook SHALL define when operators should stop maintenance and when they may continue.

#### Scenario: Blocking post-node problem is detected
- **WHEN** post-node checks report health failures, lost quorum, unavailable required storage, unexpected missing long-lived VMs, new guest verification failures, node return timeout, PVE UI/API outage, or unexplained locks
- **THEN** the runbook SHALL instruct operators to stop before continuing to another node
- **AND** it SHALL guide operators to preserve logs/context and avoid automatic corrective mutation as the first response

#### Scenario: Node is safe to proceed past
- **WHEN** the maintained node is back online, `make pve-health` has no failures, warnings are reviewed, expected VM state is understood, and outcome is recorded
- **THEN** the runbook SHALL allow operators to continue to the next node or close the maintenance window
