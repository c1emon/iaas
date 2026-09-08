# pve-state-and-secret-operations Specification

## Purpose

Document local state, cache, runtime secret injection, generated-output sensitivity, and operator recovery expectations for PVE automation workflows.

## Requirements

### Requirement: PVE state and cache runbooks
The system SHALL document state, backup, observation, and cache handling for PVE automation after the repository reorganization.

#### Scenario: Operator reviews local OpenTofu state handling
- **WHEN** an operator needs to understand PVE OpenTofu state ownership
- **THEN** documentation SHALL identify state ownership at the explicitly selected OpenTofu working root/backend
- **AND** it SHALL label the earlier repository relocation's discarded-state behavior as historical and SHALL NOT apply it to a newly selected environment; this change SHALL NOT move, discard or migrate state or existing backups
- **AND** it SHALL describe the existing backup helper and recovery guidance for the selected local root, without claiming that the helper backs up an external remote backend
- **AND** it SHALL state that future state and backups must not be committed

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
- **THEN** generated outputs, sensitive runtime work and the externally owned OpenTofu root/backend SHALL have distinct documented locations
- **AND** container-local disposable storage SHALL NOT be presented as a configured persistent backend
- **AND** private pipeline backend selection, locking and saved-plan authorization SHALL remain later-stage responsibilities

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
