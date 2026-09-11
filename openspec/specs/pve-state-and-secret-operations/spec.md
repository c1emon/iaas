# pve-state-and-secret-operations Specification

## Purpose

Document local state, cache, runtime secret injection, generated-output sensitivity, and operator recovery expectations for PVE automation workflows.

## Requirements

### Requirement: PVE state and cache runbooks
The system SHALL document state, backup, observation, cache and recovery-artifact handling for both existing explicit entrypoints and the new S3-backed launcher.

#### Scenario: Operator reviews local OpenTofu state handling
- **WHEN** an operator needs to understand PVE OpenTofu state ownership
- **THEN** documentation SHALL identify state ownership at the explicitly selected OpenTofu working root/backend
- **AND** it SHALL label the earlier repository relocation's discarded-state behavior as historical and SHALL NOT apply it to a newly selected environment; this change SHALL NOT move, discard or migrate state or existing backups
- **AND** it SHALL describe the existing backup helper and recovery guidance for the selected local root, without claiming that the helper backs up an external remote backend
- **AND** it SHALL state that state and backups must not be committed

#### Scenario: Operator reviews cache sensitivity
- **WHEN** an operator needs to inspect or clean local artifacts
- **THEN** documentation SHALL identify the existing ignored cache and export locations
- **AND** it SHALL distinguish committed non-sensitive generated artifacts from ignored caches and live observations
- **AND** it SHALL describe which local content may include secrets, password hashes, cloud-init data, provider data, dependencies, or other sensitive material

#### Scenario: Repository review checks runtime artifact tracking
- **WHEN** repository status or hygiene checks are reviewed before committing
- **THEN** tracked state, provider data, virtual environments, local caches, Ansible collection installs, live observations, and `.DS_Store` files SHALL be treated as repository hygiene failures unless explicitly documented as safe committed artifacts
- **AND** ignored local copies SHALL remain operator responsibility rather than being deleted automatically; the historical relocation exception SHALL NOT authorize deletion during this change

#### Scenario: Operator runs the container runtime
- **WHEN** container state/cache handling is documented
- **THEN** generated outputs, sensitive runtime work, recovery artifacts and the externally owned OpenTofu root/backend SHALL have distinct documented locations
- **AND** container-local disposable storage SHALL NOT be presented as a configured persistent backend
- **AND** the caller SHALL own actual S3 configuration, bucket preparation, credentials, complete-workflow serialization and saved-plan authorization
- **AND** runtime support and actual selected-service acceptance SHALL be reported separately

### Requirement: Cloud-init manifests remain local runtime artifacts
The system SHALL treat cloud-init snippet manifests and checksums as ignored runtime artifacts adjacent to rendered user-data snippets.

#### Scenario: Operator reviews cloud-init runtime cache contents
- **WHEN** an operator inspects the cloud-init runtime cache directory
- **THEN** documentation SHALL identify rendered user-data snippets and manifest/checksum files as ignored local runtime artifacts
- **AND** it SHALL state that these files must not be committed
- **AND** it SHALL explain that rendered snippets may include password hashes, SSH public keys, hostnames, IPs, and user-data content

#### Scenario: Repository review checks cloud-init manifests
- **WHEN** repository status or hygiene checks are reviewed before committing
- **THEN** tracked cloud-init rendered snippets, manifests, or checksum files under the runtime cache SHALL be treated as repository hygiene failures unless explicitly documented as safe committed artifacts
- **AND** ignored local copies SHALL remain local operator responsibility rather than being deleted automatically

### Requirement: Runtime secret injection conventions
The system SHALL document how runtime secrets enter automation commands without being committed to the repository.

#### Scenario: Operator runs a command requiring PVE, OPNsense, switch, Packer, OpenTofu, or VM user secrets
- **WHEN** a workflow requires runtime credentials or VM user material
- **THEN** documentation SHALL direct the operator to inject those values through explicit runtime environment mechanisms such as `op run --env-file ...`
- **AND** it SHALL identify which environment templates or conventions apply to the workflow
- **AND** it SHALL state that plaintext secrets, private keys, token secrets, password hashes, and environment-specific secret values MUST NOT be committed

#### Scenario: Operator reviews generated files before commit
- **WHEN** an operator reviews generated outputs for commit
- **THEN** documentation SHALL identify which generated outputs are intended to be committed
- **AND** it SHALL state that committed generated outputs must remain non-sensitive
- **AND** it SHALL provide guidance for treating generated outputs as unsafe if unexpected credential-like values appear

### Requirement: Pre-operation and recovery checklist
The system SHALL provide an operator checklist for safe local PVE automation around plan/apply-like workflows.

#### Scenario: Operator prepares for an explicit online or mutation-capable workflow
- **WHEN** an operator prepares to run PVE plan, apply, destroy, template build, or guest verification commands
- **THEN** documentation SHALL describe the relevant pre-checks for state backup, secret injection, cache handling, and generated output freshness
- **AND** it SHALL keep those commands explicit and outside the default offline validation path

#### Scenario: Operator needs recovery guidance after a failed local workflow
- **WHEN** a local PVE automation workflow fails after changing local state or cache files
- **THEN** documentation SHALL point to state backup restoration and cache cleanup guidance
- **AND** it SHALL avoid recommending automatic infrastructure mutation as a recovery step

### Requirement: Caller-owned S3 state configuration
State-accessing operations through the new launcher SHALL require an explicitly configured caller-owned S3 backend with native locking and SHALL NOT fall back to a local backend.

#### Scenario: Local and CI select the same environment root
- **WHEN** local and CI operations access the same selected root and workspace
- **THEN** they SHALL consume the same caller-maintained backend configuration, including endpoint, region, bucket, key and any workspace key prefix
- **AND** different environments SHALL use distinct state locations
- **AND** actual values and credentials SHALL NOT be stored in the IaaS repository or runtime image

#### Scenario: Backend or lock is unavailable
- **WHEN** required S3 inputs are missing, backend initialization fails or native locking cannot be obtained
- **THEN** the state-dependent operation SHALL fail without local-backend fallback, implicit state migration or automatic lock bypass
- **AND** the runtime SHALL NOT automatically create the bucket or force-unlock another operation

#### Scenario: Prepare the selected bucket
- **WHEN** a caller adopts the S3-backed launcher
- **THEN** caller guidance SHALL require a prepared bucket with versioning and native conditional-write locking support
- **AND** use_lockfile SHALL remain enabled for state operations
- **AND** caller-provided S3 compatibility SHALL require representative lock behavior validation, not only object transfer success

### Requirement: State access controls S3 credential requirements
S3 configuration and credentials SHALL be required only for operations accessing OpenTofu state, separately from facility credentials.

#### Scenario: Diagnose a component without state
- **WHEN** an OPNsense, switch, K3s or PVE API operation does not access OpenTofu state
- **THEN** it SHALL NOT require S3 configuration, credentials or backend initialization
- **AND** its own necessary facility inputs and scope checks SHALL still apply

#### Scenario: Run an offline operation
- **WHEN** check or non-sensitive generate is requested
- **THEN** it SHALL NOT connect to S3 or consume S3 credentials
- **AND** resolved credentials for state operations SHALL continue to come from caller-injected variables or protected files, not an internal secret provider

### Requirement: Preserve failed state writes for recovery
The runtime SHALL retain local recovery state or captured emergency state output produced by a failed remote write as sensitive recovery material, without treating it as a local-backend fallback or claiming recovery succeeded when capture failed.

#### Scenario: Remote state persistence fails
- **WHEN** a state-changing operation cannot persist its result to S3 and produces a local recovery state
- **THEN** the runtime SHALL preserve it with restricted permissions in a caller-accessible location that survives task cleanup
- **AND** it SHALL report the failure and recovery location without printing state contents
- **AND** it SHALL NOT automatically push state, overwrite remote state or retry apply

#### Scenario: DinD recovery export fails
- **WHEN** the only recovery copy remains in a task container or volume and export fails
- **THEN** that storage SHALL be retained and its recovery location reported
- **AND** automatic container, volume or directory removal SHALL stop before deleting the only copy
- **AND** output collection failure SHALL NOT erase or replace the original operation failure

#### Scenario: Remote and local recovery writes both fail
- **WHEN** remote state persistence and local recovery-file creation both fail and the state tool emits emergency state to stdout or stderr
- **THEN** raw output SHALL already be routed inside the container to protected capture, never directly or through tee to container, terminal or CI logs
- **AND** captured output SHALL be retained with 0600 permissions as sensitive recovery material, with only controlled phase/status summaries in public output
- **AND** the runtime SHALL report the failure and available recovery location without automatically pushing state or retrying apply

#### Scenario: Protected capture is unavailable
- **WHEN** protected stdout/stderr capture cannot be prepared
- **THEN** the state-changing subprocess SHALL NOT start
- **AND** if capture instead fails during execution, the runtime SHALL NOT fall back to exposing raw output and SHALL retain captured content and available recovery storage
- **AND** it SHALL report the original operation outcome and capture failure with recovery completeness unconfirmed, rather than claim successful recovery retention

#### Scenario: Clean completed task resources
- **WHEN** the launcher cleans disposable task resources
- **THEN** shared remote state, native lock objects and retained plan/recovery outputs SHALL NOT be treated as disposable task files
- **AND** normal native unlock SHALL remain the state tool's responsibility
- **AND** existing state migration or manual recovery SHALL remain separately authorized caller operations
