## MODIFIED Requirements

### Requirement: PVE state and cache runbooks
The system SHALL document local state and cache handling for PVE automation workflows, including which local runtime artifacts must remain out of source control.

#### Scenario: Operator reviews local OpenTofu state handling
- **WHEN** an operator needs to understand PVE OpenTofu state ownership
- **THEN** documentation SHALL identify the local state path and backup location
- **AND** it SHALL describe when to run the state backup helper
- **AND** it SHALL describe a restore path for recovering from an unintended local state change
- **AND** it SHALL state that local state files and state backups must not be committed

#### Scenario: Operator reviews cache sensitivity
- **WHEN** an operator needs to inspect or clean ignored cache directories
- **THEN** documentation SHALL identify known repository cache paths used by PVE automation
- **AND** it SHALL distinguish non-sensitive generated review artifacts from ignored runtime-derived cache files
- **AND** it SHALL describe which cache contents may include secrets, password hashes, rendered cloud-init data, state backups, provider data, dependencies, or other sensitive material

#### Scenario: Repository review checks runtime artifact tracking
- **WHEN** repository status or hygiene checks are reviewed before committing
- **THEN** tracked `terraform.tfstate*`, `.terraform/`, `.venv/`, `.cache/`, `ansible/collections/`, and `.DS_Store` files SHALL be treated as repository hygiene failures unless explicitly documented as safe committed artifacts
- **AND** ignored local copies of those artifacts SHALL remain local operator responsibility rather than being deleted automatically
