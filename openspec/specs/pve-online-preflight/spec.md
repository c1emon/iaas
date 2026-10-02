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

### Requirement: Pool admission uses actual effective operation permissions
Online planning and execution admission SHALL verify that every selected pool exists and that the actual authenticated principal can perform the requested create/clone placement and relevant current operations. Ordinary VM creation SHALL precheck all necessary dependent lifecycle/configuration permissions before writes, and refuse insufficient prospective pool evidence. Acceptance/publication dependent lifecycle preflight SHALL retain its current scope. Privilege-separated token checks SHALL use effective privileges and native API permission conditions rather than role names, user-only grants or ACL presence.

#### Scenario: Create or clone through pool authorization
- **WHEN** the native API permits allocation through the selected pool instead of a direct target VMID grant
- **THEN** admission SHALL evaluate that authorized path with all required source/storage/network permissions
- **AND** it SHALL NOT erroneously require both direct target VMID and pool allocation grants

#### Scenario: Prospective permissions or pool visibility are insufficient
- **WHEN** required prospective permission evidence cannot be established, pool existence is unobservable, or the only occupancy evidence is an incomplete pool-filtered VM list
- **THEN** admission SHALL report permission_evidence_insufficient and refuse dependent facility writes
- **AND** it SHALL NOT interpret an empty filtered list or arbitrary union of ACLs as complete authority

#### Scenario: Existing restricted helper supplies complete occupancy evidence
- **WHEN** API visibility is pool-limited but the required existing read-only helper establishes complete VMID visibility for the confirmed selected cluster/node
- **THEN** admission MAY use that authoritative evidence to establish the concrete VMID free without requiring unrelated global API privileges
- **AND** helper/cluster identity, completeness and selected VMID association SHALL remain mandatory and the effective API operation permissions SHALL still be checked

#### Scenario: Required pool or effective permission is missing
- **WHEN** authoritative evidence confirms a required pool is nonexistent or an operation privilege is absent for the actual token
- **THEN** admission SHALL fail before clone/configuration/upload/start and identify the object, operation and missing permission where applicable
- **AND** IaaS SHALL NOT create the pool, adjust ACLs or downgrade placement

### Requirement: Permission failures have fixed safe classifications
Permission diagnostics SHALL distinguish permission_missing, permission_value_invalid, permission_query_failed and permission_evidence_insufficient, including existing storage permission checks. They SHALL expose only bounded stage/object/operation/missing-privilege context and necessary HTTP status.

#### Scenario: A granted privilege has propagation value zero
- **WHEN** an effective-permission response contains a required privilege with a valid propagation flag of 0 or 1
- **THEN** the privilege SHALL be treated as granted under the API contract rather than using truthiness to reject zero

#### Scenario: Permission evidence is negative malformed or unavailable
- **WHEN** a complete response omits a required privilege, contains an illegal privilege value, the query fails, or its structure/scope cannot establish authority
- **THEN** the corresponding fixed classification SHALL be emitted separately
- **AND** credentials, authentication headers and sensitive raw response content SHALL NOT be included

### Requirement: Acceptance prerequisites are complete before facility writes
Acceptance online plan and execution admission SHALL verify source identity, placement/node, storage capability and capacity, network, concrete VMID availability, resource bounds and all required API/SSH/helper conditions before clone. Plan success SHALL NOT replace execution rechecks. Offline check SHALL remain credential-free and network-free.

#### Scenario: A required helper is unavailable or lacks capability
- **WHEN** the acceptance upload/delete helper, strict SSH trust, isolated key, noninteractive sudo or required create-only/deadline/reference capability is unavailable
- **THEN** plan/start SHALL fail before clone or any acceptance facility write
- **AND** capability probes SHALL be read-only and missing support SHALL NOT trigger bootstrap or a protocol fallback

#### Scenario: Guest-agent permission is missing
- **WHEN** the actual effective privileges do not satisfy VM.GuestAgent.Audit OR VM.GuestAgent.Unrestricted for ping/hostname, or VM.GuestAgent.Unrestricted for exec/status
- **THEN** admission SHALL refuse before cloning or starting the VM rather than discovering the omission through guest execution

#### Scenario: Unrestricted grant satisfies the native informational permission alternative
- **WHEN** actual effective VM.GuestAgent.Unrestricted is granted while VM.GuestAgent.Audit is not separately granted
- **THEN** guest permission admission SHALL satisfy the native informational and exec/status conditions without requiring a redundant independent grant
- **AND** the permission documentation SHALL still list both privilege names and their operation-specific predicates

#### Scenario: Prerequisites change after a successful plan
- **WHEN** permissions, source identity, pool, node/storage/network/helper readiness or VMID availability changes before execution
- **THEN** start SHALL independently recheck the applicable prerequisites and refuse conflicting writes
- **AND** it SHALL retain the reviewed request and report the actual failure without silently changing the plan
