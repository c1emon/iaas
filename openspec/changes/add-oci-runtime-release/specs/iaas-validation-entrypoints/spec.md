## MODIFIED Requirements

### Requirement: Root offline validation command surface
The system SHALL expose root-level commands that provide routine offline validation for the explicitly selected environment to local operators and CI.

#### Scenario: Generate committed outputs from source inventory
- **WHEN** an operator runs the root generation command
- **THEN** the system SHALL regenerate non-sensitive outputs beneath the explicitly selected generated-output directory from the selected environment's authored source files
- **AND** it SHALL include generated service metadata documentation from the selected environment's `inventory/services.yml`
- **AND** it SHALL use repository-owned generator behavior and paths supplied by the root command rather than ad-hoc shell snippets
- **AND** it SHALL NOT require PVE API connectivity or runtime secrets

#### Scenario: Detect stale generated outputs
- **WHEN** selected environment source data changes without updating its committed generated outputs
- **THEN** the root generated-output check SHALL fail
- **AND** it SHALL report stale PVE, service, or foundation artifacts as applicable
- **AND** it SHALL NOT modify files while running in check mode

#### Scenario: Run the aggregate offline gate
- **WHEN** an operator or CI runs the root aggregate check command
- **THEN** the system SHALL run only infrastructure-offline validation targets for the selected environment
- **AND** it SHALL include generated-output freshness, Python tests, YAML lint, OpenTofu formatting/validation, Python type checking, Ansible lint/syntax as applicable, and OPNsense desired-state validation
- **AND** it SHALL fail when any required validation fails
- **AND** it SHALL NOT generate or render files, access online infrastructure, read runtime secrets, plan, or mutate infrastructure

#### Scenario: Install locked toolchains before validation
- **WHEN** cloud CI validates a pull request or main-branch update
- **THEN** it SHALL install the committed Python and infrastructure validation toolchains without making OpenSpec a project runtime dependency
- **AND** it SHALL invoke the same repository-owned aggregate offline command used by operators
- **AND** it SHALL report validation failures without executing online, planning, or mutation workflows

#### Scenario: Caller omits environment selection
- **WHEN** a root operation needs authored environment data but receives no complete explicit environment/file inputs
- **THEN** it SHALL fail before generation, online access or mutation with a generic input requirement
- **AND** it SHALL NOT fall back to Astra paths or accept a removed `ASTRA` selector
- **AND** environment-independent commands SHALL remain usable without unrelated inputs

### Requirement: CI validates and reports only
The system SHALL keep PR/main CI limited to validation and image build/smoke checks without internal infrastructure privileges or image publication. A separate Release publication workflow SHALL follow the `oci-runtime-delivery` contract.

#### Scenario: Validate a pull request in cloud CI
- **WHEN** a pull request triggers the CI workflow
- **THEN** GitHub Actions SHALL install the required locked validation toolchain and explicitly select validation inputs
- **AND** it SHALL call repository-owned offline validation commands
- **AND** it SHALL report success or failure to the Git provider
- **AND** it SHALL NOT require internal network routes or infrastructure secrets

#### Scenario: Validate main branch updates in cloud CI
- **WHEN** changes are pushed to the main branch
- **THEN** CI SHALL run the same offline validation gate used for pull requests with explicit environment/output selection
- **AND** it SHALL NOT perform PVE preflight, OpenTofu plan, OpenTofu apply, OpenTofu destroy, Packer build, or Ansible mutation

#### Scenario: Keep CI platform replaceable
- **WHEN** the repository is validated by a different CI platform in the future
- **THEN** that CI platform SHALL be able to invoke the same repository-owned offline commands
- **AND** validation semantics SHALL NOT depend on GitHub Actions-specific behavior

#### Scenario: Defer secret scanning from first CI implementation
- **WHEN** the first P0 CI workflow is implemented
- **THEN** it SHALL NOT be required to run `gitleaks`, `trufflehog`, or another secret scanner
- **AND** secret scanning SHALL be left to a later change after the baseline and false-positive strategy are reviewed
