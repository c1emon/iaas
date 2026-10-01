## ADDED Requirements

### Requirement: Pool admission uses actual effective operation permissions
Online planning and execution admission SHALL verify that every selected pool exists and that the actual authenticated principal can perform the requested create/clone placement and dependent lifecycle operations. Privilege-separated token checks SHALL use effective privileges and native API permission conditions rather than role names, user-only grants or ACL presence.

#### Scenario: Create or clone through pool authorization
- **WHEN** the native API permits allocation through the selected pool instead of a direct target VMID grant
- **THEN** admission SHALL evaluate that authorized path with all required source/storage/network permissions
- **AND** it SHALL NOT erroneously require both direct target VMID and pool allocation grants

#### Scenario: Prospective permissions or pool visibility are insufficient
- **WHEN** the not-yet-created VM's effective pool-derived permissions cannot be established, pool existence is unobservable, or the only occupancy evidence is an incomplete pool-filtered VM list
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
