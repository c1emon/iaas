## MODIFIED Requirements

### Requirement: Root offline validation command surface
The system SHALL expose root-level commands that provide routine offline validation for Astra to local operators and CI.

#### Scenario: Generate committed outputs from source inventory
- **WHEN** an operator runs the root generation command
- **THEN** the system SHALL regenerate committed non-sensitive outputs under `environments/astra/generated/` from Astra's authored source files
- **AND** it SHALL include generated service metadata documentation from `environments/astra/inventory/services.yml`
- **AND** it SHALL use repository-owned generator behavior and paths supplied by the root command rather than ad-hoc shell snippets
- **AND** it SHALL NOT require PVE API connectivity or runtime secrets

#### Scenario: Detect stale generated outputs
- **WHEN** Astra source data changes without updating its committed generated outputs
- **THEN** the root generated-output check SHALL fail
- **AND** it SHALL report stale PVE, service, or foundation artifacts as applicable
- **AND** it SHALL NOT modify files while running in check mode

#### Scenario: Run the aggregate offline gate
- **WHEN** an operator or CI runs the root aggregate check command
- **THEN** the system SHALL run only offline read-only validation targets for Astra
- **AND** it SHALL include generated-output freshness, Python tests, YAML lint, OpenTofu formatting/validation, Python type checking, Ansible lint/syntax as applicable, and OPNsense desired-state validation
- **AND** it SHALL fail when any required validation fails
- **AND** it SHALL NOT generate or render files, access online infrastructure, read runtime secrets, plan, or mutate infrastructure

#### Scenario: Install locked toolchains before validation
- **WHEN** cloud CI validates a pull request or main-branch update
- **THEN** it SHALL install the committed Python and infrastructure validation toolchains without making OpenSpec a project runtime dependency
- **AND** it SHALL invoke the same repository-owned aggregate offline command used by operators
- **AND** it SHALL report validation failures without executing online, planning, or mutation workflows
