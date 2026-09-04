## MODIFIED Requirements

### Requirement: PVE state and cache runbooks
The system SHALL document state, backup, observation, and cache handling for PVE automation after the repository reorganization.

#### Scenario: Operator reviews local OpenTofu state handling
- **WHEN** an operator needs to understand PVE OpenTofu state ownership
- **THEN** documentation SHALL identify future ignored state at `environments/astra/opentofu/pve/terraform.tfstate`
- **AND** it SHALL state that state files in the old OpenTofu root are discarded rather than migrated and that existing ignored backup caches remain untouched
- **AND** it SHALL describe the existing backup helper and recovery guidance for state created by future operations at the relocated root
- **AND** it SHALL state that future state and backups must not be committed

#### Scenario: Operator reviews cache sensitivity
- **WHEN** an operator needs to inspect or clean local artifacts
- **THEN** documentation SHALL identify the existing ignored cache and export locations
- **AND** it SHALL distinguish committed non-sensitive generated artifacts from ignored caches and live observations
- **AND** it SHALL describe which local content may include secrets, password hashes, cloud-init data, provider data, dependencies, or other sensitive material

#### Scenario: Repository review checks runtime artifact tracking
- **WHEN** repository status or hygiene checks are reviewed before committing
- **THEN** tracked state, provider data, virtual environments, local caches, Ansible collection installs, live observations, and `.DS_Store` files SHALL be treated as repository hygiene failures unless explicitly documented as safe committed artifacts
- **AND** ignored local copies other than the explicitly discarded state files in the old OpenTofu root SHALL remain operator responsibility rather than being deleted automatically
