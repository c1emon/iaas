## MODIFIED Requirements

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
