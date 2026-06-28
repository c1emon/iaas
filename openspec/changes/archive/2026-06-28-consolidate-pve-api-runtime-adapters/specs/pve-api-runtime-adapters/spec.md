## ADDED Requirements

### Requirement: Shared read-only PVE API facade
The system SHALL provide a repository-owned read-only PVE API facade or protocol for PVE online checks.

#### Scenario: Online checks use named read-only methods
- **WHEN** PVE preflight or PVE health logic needs live PVE facts
- **THEN** it SHALL depend on named read-only facade methods for required cluster, node, storage, VM, mapping, HA, or Ceph facts
- **AND** it SHALL NOT traverse raw PVE SDK objects or construct arbitrary HTTP endpoint strings throughout command logic

#### Scenario: Facade avoids mutation helpers
- **WHEN** the PVE API facade is exposed to online check callers
- **THEN** it SHALL NOT expose generic mutation helpers such as create, update, delete, post, put, start, stop, reboot, migrate, upload, or configuration-write operations
- **AND** callers SHALL be able to perform preflight and health checks without access to mutation-capable methods

#### Scenario: Backend implementations remain interchangeable
- **WHEN** a PVE API backend is implemented using urllib, proxmoxer, or another read-only transport
- **THEN** it SHALL satisfy the same repository-owned read-only facade shape
- **AND** preflight and health check semantics SHALL NOT depend on backend-specific exception or SDK traversal details

### Requirement: Shared PVE runtime configuration parsing
The system SHALL parse runtime configuration for PVE online checks through a shared repository-owned runtime helper.

#### Scenario: API credentials are loaded for online checks
- **WHEN** a PVE online check requires API access
- **THEN** the runtime helper SHALL load endpoint, API username, token ID, token secret, and TLS verification mode from the repository's established PVE environment variable names
- **AND** missing required API values SHALL produce an operator-readable validation failure without printing token secrets or resolved credential values

#### Scenario: Optional SSH adjunct context is loaded for preflight
- **WHEN** a PVE online check supports optional SSH adjunct checks
- **THEN** the runtime helper SHALL preserve optional SSH host and SSH user context separately from required API credentials
- **AND** absence of optional SSH context SHALL NOT prevent API-based preflight checks from running

#### Scenario: Boolean runtime values are parsed consistently
- **WHEN** runtime configuration includes boolean-like values such as TLS insecure mode
- **THEN** preflight and health commands SHALL use the same accepted boolean spellings and the same validation error behavior for invalid values

### Requirement: Safe PVE API errors and redaction
The system SHALL normalize PVE API failures into safe repository-owned exceptions and redacted operator messages.

#### Scenario: API authentication fails
- **WHEN** PVE API authentication or authorization fails during an online check
- **THEN** the system SHALL report an authentication or reachability failure using a repository-owned safe error type
- **AND** it SHALL NOT print API token secrets or resolved credential values

#### Scenario: Optional endpoint is unavailable
- **WHEN** an optional PVE endpoint such as HA, Ceph, or version-dependent mapping details is unavailable or not configured
- **THEN** the API layer SHALL preserve enough error classification for the calling check to map the condition to skip, warning, or failure according to that command's semantics
- **AND** it SHALL still redact secrets from any operator-visible message

#### Scenario: Backend exception details include sensitive text
- **WHEN** urllib, proxmoxer, or another backend exception contains token material or other known secrets
- **THEN** redaction SHALL remove those values before the message reaches reports, stderr, or test assertions

### Requirement: Existing online command semantics are preserved
The system SHALL preserve PVE preflight and PVE health operator-facing semantics while consolidating shared adapter plumbing.

#### Scenario: PVE preflight runs after adapter consolidation
- **WHEN** an operator runs PVE preflight with the same declared inventory and runtime context as before the consolidation
- **THEN** it SHALL continue to perform read-only apply-readiness checks for nodes, bridges, storage, templates, VMID ownership, PCI mapping readiness, and optional SSH adjunct checks
- **AND** it SHALL keep existing pass, warning, failure, skip, and exit-code semantics unless a later explicit change modifies those requirements

#### Scenario: PVE health runs after adapter consolidation
- **WHEN** an operator runs PVE health with the same declared inventory and runtime context as before the consolidation
- **THEN** it SHALL continue to perform read-only current-state health checks for cluster reachability, quorum, node state and capacity, required storage, templates, declared VM runtime status, HA, and Ceph
- **AND** it SHALL keep existing pass, warning, failure, skip, and exit-code semantics unless a later explicit change modifies those requirements

#### Scenario: Default offline validation runs after adapter consolidation
- **WHEN** an operator or CI runs the repository's default offline validation gate
- **THEN** PVE preflight and PVE health SHALL remain outside that default gate
- **AND** the default gate SHALL remain runnable without PVE API access, SSH access, 1Password access, runtime secrets, or mutation-capable infrastructure credentials
