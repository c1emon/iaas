## ADDED Requirements

### Requirement: Explicit PVE cluster health entrypoint
The system SHALL expose an explicit repository-owned online PVE cluster health command for local operators.

#### Scenario: Operator runs PVE health check
- **WHEN** an operator runs the PVE health command with required PVE runtime context
- **THEN** the system SHALL perform read-only health checks against the declared PVE environment
- **AND** it SHALL use repository-owned command targets rather than ad-hoc shell snippets
- **AND** it SHALL NOT run OpenTofu plan, apply, destroy, Packer build, guest SSH verification, VM migration, node reboot, package update, or infrastructure mutation

#### Scenario: Default offline validation runs
- **WHEN** an operator or CI runs the default aggregate offline validation command
- **THEN** PVE cluster health checks SHALL NOT be a dependency of that default gate
- **AND** the default gate SHALL remain runnable without PVE API, SSH, 1Password, or apply-capable credentials

### Requirement: Read-only Python PVE API layer
The system SHALL access live PVE state for health checks through a repository-owned Python API layer backed by `proxmoxer`.

#### Scenario: API layer is a reusable module
- **WHEN** the implementation adds the proxmoxer-backed PVE API layer
- **THEN** it SHALL place the wrapper in a standalone reusable PVE API package rather than embedding it inside the health command or preflight command
- **AND** the package SHALL support separation of client, error handling, and future endpoint/normalization helpers instead of requiring all API concerns in one large file
- **AND** health-command code SHALL depend on that package for live PVE connectivity and endpoint traversal
- **AND** existing preflight-specific API code MAY remain separate until a future refactor migrates it intentionally

#### Scenario: Health checks query PVE through the API layer
- **WHEN** the health command needs live PVE cluster, node, storage, VM, HA, or Ceph data
- **THEN** it SHALL call named read-only methods on the repository-owned PVE API layer
- **AND** health-check logic SHALL NOT traverse the raw `proxmoxer` client directly throughout the command implementation

#### Scenario: API layer preserves read-only behavior
- **WHEN** the PVE API layer talks to Proxmox VE
- **THEN** it SHALL use read-only API operations for health facts
- **AND** it SHALL NOT expose generic mutation helpers such as create, update, delete, start, stop, reboot, migrate, upload, or configuration-write operations to health-check callers
- **AND** it SHALL NOT print API token secrets or resolved credential values

### Requirement: Cluster and node health checks
The system SHALL report PVE cluster and node health using read-only API data.

#### Scenario: PVE API credentials are valid
- **WHEN** PVE health runs with PVE API endpoint and token environment variables
- **THEN** it SHALL verify that the API endpoint is reachable and the token can perform read-only health queries
- **AND** it SHALL NOT print API token secrets or resolved credential values

#### Scenario: Quorum state is exposed
- **WHEN** PVE cluster status exposes quorum state
- **THEN** the health command SHALL pass when the cluster is quorate
- **AND** it SHALL fail when the cluster is not quorate

#### Scenario: Quorum state is not exposed
- **WHEN** PVE cluster status does not expose quorum state
- **THEN** the health command SHALL report the quorum check as skipped rather than failed

#### Scenario: Required node is missing or offline
- **WHEN** a node hosting declared VMs or referenced templates is missing or offline
- **THEN** the health command SHALL fail
- **AND** it SHALL identify the affected required node

#### Scenario: Optional placeholder node is missing or offline
- **WHEN** a declared node is not currently required by declared VMs or referenced templates and is missing or offline
- **THEN** the health command SHALL warn rather than fail

### Requirement: Capacity threshold checks
The system SHALL warn or fail when read-only capacity data indicates operational pressure.

#### Scenario: Node capacity crosses warning threshold
- **WHEN** a checked node reports CPU usage greater than 90 percent, memory usage greater than 90 percent, or root disk usage greater than 90 percent
- **THEN** the health command SHALL report a warning for the affected capacity dimension

#### Scenario: Node root disk crosses failure threshold
- **WHEN** a checked node reports root disk usage greater than 98 percent
- **THEN** the health command SHALL report a failure for root disk capacity pressure

#### Scenario: Datastore capacity crosses thresholds
- **WHEN** a required datastore reports usage greater than 85 percent
- **THEN** the health command SHALL report a warning
- **AND** when a required datastore reports usage greater than 95 percent, it SHALL report a failure

### Requirement: Storage health checks
The system SHALL check required PVE datastore presence and availability using read-only API data.

#### Scenario: Required datastore is present and active
- **WHEN** the health command checks a datastore required by declared VMs, templates, or generated snippets
- **THEN** it SHALL pass when the datastore is present and active or otherwise available according to PVE API data

#### Scenario: Required datastore is missing or inactive
- **WHEN** a datastore required by declared VMs, templates, or generated snippets is missing, inactive, or unavailable
- **THEN** the health command SHALL fail
- **AND** it SHALL identify the affected node and datastore

### Requirement: Template and VM runtime checks
The system SHALL report template and declared VM runtime state using lifecycle-aware semantics.

#### Scenario: Referenced template is healthy
- **WHEN** a template referenced by declared VMs exists and is marked as a PVE template
- **THEN** the health command SHALL pass the referenced template check

#### Scenario: Referenced template is missing or not a template
- **WHEN** a template referenced by declared VMs is missing or exists without being marked as a template
- **THEN** the health command SHALL fail

#### Scenario: Long-lived VM is missing or stopped
- **WHEN** a declared `long_lived` VM is missing from PVE or is stopped
- **THEN** the health command SHALL report a warning
- **AND** it SHALL continue unless other failures are present

#### Scenario: Ephemeral lab VM is missing or stopped
- **WHEN** a declared `ephemeral_lab` VM is missing from PVE or is stopped
- **THEN** the health command SHALL NOT warn solely for that missing or stopped state
- **AND** it MAY include the state in an informational pass/skip/summary record

### Requirement: HA and Ceph optional subsystem checks
The system SHALL check HA and Ceph health when available without requiring those subsystems in small environments.

#### Scenario: HA endpoint is unavailable or has no resources
- **WHEN** the PVE HA status endpoint is unavailable, not configured, or reports no HA resources
- **THEN** the health command SHALL skip HA checks rather than fail

#### Scenario: HA reports unhealthy resources
- **WHEN** PVE HA status reports resource error, fence, unknown, or similarly unhealthy states
- **THEN** the health command SHALL fail and identify the affected HA resource

#### Scenario: Ceph endpoint is unavailable
- **WHEN** the PVE Ceph health endpoint is unavailable or not configured
- **THEN** the health command SHALL skip Ceph checks rather than fail

#### Scenario: Ceph health is available
- **WHEN** PVE Ceph health reports `HEALTH_OK`
- **THEN** the health command SHALL pass the Ceph check
- **AND** when Ceph reports `HEALTH_WARN`, it SHALL warn
- **AND** when Ceph reports `HEALTH_ERR`, it SHALL fail

### Requirement: Health reporting and exit semantics
The system SHALL provide clear PVE health results that distinguish pass, warn, fail, and skipped checks.

#### Scenario: Blocking health failures are found
- **WHEN** PVE health finds one or more blocking failures
- **THEN** it SHALL exit with a non-zero status
- **AND** it SHALL report actionable failure messages without disclosing secrets

#### Scenario: Only warnings or skipped optional checks are found
- **WHEN** PVE health completes with no blocking failures but with warnings or skipped optional checks
- **THEN** it SHALL exit successfully
- **AND** it SHALL report the warnings or skipped checks clearly for operator review

#### Scenario: All required health checks pass
- **WHEN** all required health checks pass
- **THEN** it SHALL report successful health for the declared PVE environment
