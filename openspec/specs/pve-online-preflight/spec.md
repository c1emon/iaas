# pve-online-preflight Specification

## Purpose
Define the explicit repository-owned online PVE readiness check that validates
declared PVE resources through read-only API-first checks and optional SSH
adjunct checks before live plan/apply-like workflows.

## Requirements

### Requirement: Explicit PVE online preflight entrypoint
The system SHALL expose an explicit repository-owned online PVE preflight command for local operators.

#### Scenario: Operator runs PVE online preflight
- **WHEN** an operator runs the PVE preflight command with required PVE runtime context
- **THEN** the system SHALL perform read-only readiness checks against the declared PVE environment
- **AND** it SHALL use repository-owned command targets rather than ad-hoc shell snippets
- **AND** it SHALL NOT run OpenTofu plan, apply, destroy, Packer build, guest SSH verification, snippet upload, or infrastructure mutation

#### Scenario: Default offline validation runs
- **WHEN** an operator or CI runs the default aggregate offline validation command
- **THEN** PVE online preflight SHALL NOT be a dependency of that default gate
- **AND** the default gate SHALL remain runnable without PVE API, SSH, 1Password, or apply-capable credentials

### Requirement: API-first PVE readiness checks
The system SHALL prefer PVE API checks for PVE control-plane resources required by declared OpenTofu VM workflows.

#### Scenario: PVE API credentials are valid
- **WHEN** PVE preflight runs with PVE API endpoint and token environment variables
- **THEN** it SHALL verify that the API endpoint is reachable and the token can perform read-only queries
- **AND** it SHALL NOT print API token secrets or resolved credential values

#### Scenario: Declared resources are visible through PVE
- **WHEN** PVE preflight evaluates the validated PVE inventory model
- **THEN** it SHALL verify that required nodes, VM bridges, storage IDs, template VM records, and cloud-init snippet storage are visible or otherwise confirmed read-only
- **AND** missing or mismatched resources used by declared VMs or templates SHALL fail preflight

#### Scenario: Declared but unused resources are not blocking
- **WHEN** PVE inventory contains declared nodes or mapping-node combinations that are not used by current VM or template declarations
- **THEN** PVE preflight SHALL report missing or unavailable unused resources as warnings rather than blocking failures

### Requirement: VMID ownership readiness
The system SHALL detect declared VMID occupancy and declaration compatibility before live plan/apply-like operations, while treating root/state ownership as a separate admission fact.

#### Scenario: Declared VMID is free
- **WHEN** PVE preflight confirms a declared VMID does not exist in the selected scope
- **THEN** it SHALL report the VMID as available
- **AND** incomplete or unauthorized observation SHALL NOT be treated as absence

#### Scenario: Declared VMID already belongs to this repository
- **WHEN** an occupied VMID matches the expected declaration and repository ownership markers
- **THEN** preflight SHALL report declaration compatibility without asserting ownership by the selected root/state
- **AND** names, tags and descriptions SHALL NOT authorize adoption, import or a second state claiming the object
- **AND** lifecycle admission SHALL still require the selected state's native association and caller-owned ownership context

#### Scenario: Declared VMID is occupied by an unexpected VM
- **WHEN** PVE preflight checks an occupied VMID not associated with the selected state, or with conflicting object identity or ownership context
- **THEN** it SHALL fail before any plan/apply-like workflow is attempted
- **AND** it SHALL report safe conflict context without changing the object

#### Scenario: A managed VM has an intended change or configuration drift
- **WHEN** the selected state's native association and caller ownership context identify the occupied VM, but its mutable name, tags or configuration differ from the desired declaration
- **THEN** readiness SHALL report the difference without treating it alone as an ownership conflict
- **AND** the complete-root native plan SHALL determine the reviewed update, replacement or deletion instead of preflight blocking legitimate drift repair
- **AND** observation without state ownership evidence SHALL remain informational rather than authorize mutation

#### Scenario: Ownership remains unknown
- **WHEN** current root/state ownership cannot be established
- **THEN** the stateful lifecycle SHALL reject mutation and require caller reconciliation
- **AND** preflight SHALL NOT infer authorization from the VMID range or a repository marker

### Requirement: Passthrough readiness checks remain read-only
The system SHALL validate declared PCI passthrough readiness without creating or modifying PVE hardware mappings.

#### Scenario: VM uses a declared PCI mapping
- **WHEN** a VM declaration uses a PCI passthrough mapping on a selected node
- **THEN** PVE preflight SHALL verify read-only that the mapping exists and is compatible with the selected node where supported by available PVE checks
- **AND** it SHALL fail if a used mapping is missing or incompatible

#### Scenario: PCI mapping bootstrap is needed
- **WHEN** a declared PCI mapping is absent from PVE
- **THEN** PVE preflight SHALL report the missing mapping as a readiness failure for affected VMs
- **AND** it SHALL NOT create, update, or bootstrap the missing mapping

### Requirement: SSH adjunct checks are scoped and non-mutating
The system SHALL allow SSH only for read-only node-local adjunct checks that are not reliably available through the PVE API.

#### Scenario: SSH context is provided
- **WHEN** PVE preflight runs with SSH host and user context
- **THEN** it MAY verify node-local wrapper presence, wrapper help or verify behavior, and sudo reachability using read-only commands
- **AND** it SHALL NOT upload snippets, modify files, change sudoers, create VMs, or mutate PVE configuration

#### Scenario: SSH context is absent
- **WHEN** PVE preflight runs without optional SSH context
- **THEN** API-based checks SHALL still run
- **AND** SSH adjunct checks SHALL be reported as skipped or non-blocking unless the operator explicitly requested SSH-required preflight behavior

### Requirement: Preflight reporting and exit semantics
The system SHALL provide clear preflight results that distinguish pass, warn, fail, and skipped checks.

#### Scenario: Blocking readiness failures are found
- **WHEN** PVE preflight finds one or more blocking readiness failures
- **THEN** it SHALL exit with a non-zero status
- **AND** it SHALL report actionable failure messages without disclosing secrets

#### Scenario: Only warnings or skipped optional checks are found
- **WHEN** PVE preflight completes with no blocking failures but with warnings or skipped optional checks
- **THEN** it SHALL exit successfully
- **AND** it SHALL report the warnings or skipped checks clearly for operator review

#### Scenario: All checks pass
- **WHEN** all required preflight checks pass
- **THEN** it SHALL report successful online readiness for the declared PVE environment
