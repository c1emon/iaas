# pve-rolling-maintenance-runbook Specification

## Purpose
TBD - created by archiving change add-pve-rolling-maintenance-runbook. Update Purpose after archive.

## Requirements

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
- **AND** it SHALL require a recorded maintenance scope and stop deadline, applicable backup/recovery evidence, and working alternate console access before disruptive work
- **AND** it SHALL recommend capturing a guest baseline with `make pve-verify-guests` when guest SSH context is available

#### Scenario: Operator completes maintenance on one node
- **WHEN** a maintained node returns to service
- **THEN** the runbook SHALL require a post-node health gate before continuing to another node
- **AND** it SHALL require any warnings to be reviewed before proceeding

#### Scenario: Operator completes the full maintenance window
- **WHEN** all intended nodes have been maintained or the window is stopped
- **THEN** the runbook SHALL require final `make pve-health` verification
- **AND** it SHALL recommend comparing `make pve-verify-guests` results with the baseline or recording a reason for skipping guest verification

### Requirement: Single-node and multi-node maintenance flows
The runbook SHALL distinguish single-node maintenance from multi-node rolling maintenance.

#### Scenario: Environment is effectively single-node
- **WHEN** the target environment has only one required/available PVE node for declared workloads
- **THEN** the runbook SHALL present a single-node maintenance branch
- **AND** it SHALL require the operator to accept planned downtime where applicable
- **AND** it SHALL require working local or out-of-band console access before the node is disrupted
- **AND** it SHALL NOT describe the procedure as no-downtime rolling maintenance

#### Scenario: Environment supports multi-node maintenance
- **WHEN** the environment has multiple live PVE nodes that may be suitable for rolling maintenance
- **THEN** the runbook SHALL describe maintaining one node at a time
- **AND** it SHALL require explicit live quorum evidence rather than treating a skipped quorum check as sufficient
- **AND** it SHALL require manual confirmation of workload-placement capacity, storage compatibility, and passthrough handling before selecting the rolling branch
- **AND** it SHALL require preserving quorum and verifying health after each node before continuing
- **AND** it SHALL block the rolling branch when those prerequisites are uncertain

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
The runbook SHALL document reboot-only and package-update maintenance as manual workflows, with reboot treated as a separate planned or package-required action.

#### Scenario: Reboot-only maintenance is selected
- **WHEN** the operator selects reboot-only maintenance
- **THEN** the runbook SHALL guide the operator through health checks, workload handling, manual reboot, node return verification, and guest verification

#### Scenario: Package-update maintenance is selected
- **WHEN** the operator selects package-update maintenance
- **THEN** the runbook SHALL guide the operator to review package plans and PVE repository/channel expectations before manual package update commands
- **AND** package update and any planned or required reboot commands SHALL remain manual operator actions
- **AND** the runbook SHALL NOT imply that every package update requires a reboot or has a generic package rollback path

### Requirement: Conditional Ceph guidance
The runbook SHALL include Ceph guidance only as conditional, non-mutating operator guidance.

#### Scenario: Ceph is not configured
- **WHEN** the environment does not use Ceph
- **THEN** the runbook SHALL allow operators to skip Ceph-specific steps

#### Scenario: Ceph is configured
- **WHEN** a future environment uses Ceph
- **THEN** the runbook SHALL require a separately reviewed environment-specific Ceph maintenance procedure before using this runbook
- **AND** it SHALL instruct operators to defer maintenance under this runbook when that procedure is absent
- **AND** it SHALL NOT prescribe generic `noout` or other Ceph flag commands
- **AND** it SHALL NOT automate Ceph mutation

### Requirement: Abort and continue criteria
The runbook SHALL define when operators should stop maintenance and when they may continue.

#### Scenario: Blocking post-node problem is detected
- **WHEN** post-node checks report health failures, lost or unverified quorum in a clustered flow, unavailable required storage, unexpected missing long-lived VMs, new guest verification failures, a missed recorded node-return deadline, PVE UI/API outage, or unexplained locks
- **THEN** the runbook SHALL instruct operators to stop before continuing to another node
- **AND** it SHALL guide operators to preserve logs/context, use the preselected recovery path, avoid generic automatic corrective mutation as the first response, and require fresh admission before resuming

#### Scenario: Node is safe to proceed past
- **WHEN** the maintained node is back online, `make pve-health` has no failures, warnings are reviewed, expected VM state is understood, and outcome is recorded
- **THEN** the runbook SHALL allow operators to continue to the next node or close the maintenance window
