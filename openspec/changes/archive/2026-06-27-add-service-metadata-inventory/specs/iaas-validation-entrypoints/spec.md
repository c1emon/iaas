## MODIFIED Requirements

### Requirement: Root offline validation command surface
The system SHALL expose root-level commands for routine offline validation that can be run by both local operators and CI.

#### Scenario: Generate committed outputs from source inventory
- **WHEN** an operator runs the root generation command
- **THEN** the system SHALL regenerate committed non-sensitive outputs from operator-authored source-of-truth files
- **AND** it SHALL include generated service metadata documentation when `inventory/services.yml` is present
- **AND** it SHALL use repository-owned generator behavior rather than ad-hoc shell snippets
- **AND** it SHALL NOT require PVE API connectivity or runtime secrets

#### Scenario: Detect stale generated outputs
- **WHEN** source-of-truth inventory changes without updating committed generated outputs
- **THEN** the root generated-output check SHALL fail
- **AND** it SHALL report stale PVE generated outputs or stale service documentation as applicable
- **AND** it SHALL NOT modify files while running in check mode

#### Scenario: Run the aggregate offline gate
- **WHEN** an operator or CI runs the root aggregate check command
- **THEN** the system SHALL run only offline-safe validation targets
- **AND** it SHALL include stale generated output detection for PVE outputs and service metadata documentation
- **AND** it SHALL include relevant Python tests
- **AND** it SHALL include YAML linting for source-of-truth files
- **AND** it SHALL include OpenTofu formatting and offline validation where practical
- **AND** it SHALL NOT perform online infrastructure access or mutation
