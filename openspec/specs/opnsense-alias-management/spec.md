# opnsense-alias-management Specification

## Purpose
Define the safe, additive workflow for managing OPNsense firewall aliases from hand-written desired state.

## Requirements

### Requirement: Hand-written alias desired state
The system SHALL define OPNsense firewall aliases from a hand-written YAML source file that is separate from generated export artifacts.

#### Scenario: Desired aliases are reviewed as source configuration
- **WHEN** an operator reviews the OPNsense alias management input
- **THEN** the desired aliases are represented in a repository YAML file intended for manual review and editing

#### Scenario: Export artifacts are not used as the direct apply source
- **WHEN** the alias management workflow is run
- **THEN** it reads desired aliases from the hand-written YAML source and not directly from generated export output

### Requirement: Additive alias apply workflow
The system SHALL provide an Ansible workflow that creates or updates aliases listed in the desired YAML source without deleting, disabling, or purging aliases that are not listed.

#### Scenario: Listed alias does not exist
- **WHEN** the operator runs the alias apply workflow with a desired alias that does not exist in OPNsense
- **THEN** the workflow creates that alias in OPNsense

#### Scenario: Listed alias already exists
- **WHEN** the operator runs the alias apply workflow with a desired alias that already exists in OPNsense
- **THEN** the workflow updates the listed alias fields according to the desired YAML source

#### Scenario: Unlisted alias exists
- **WHEN** OPNsense contains an alias that is absent from the desired YAML source
- **THEN** the workflow leaves that alias present and enabled state unchanged

### Requirement: Alias reload after successful changes
The system SHALL reload the OPNsense alias target after successfully applying desired alias changes.

#### Scenario: Alias apply succeeds
- **WHEN** the alias apply workflow completes alias create or update operations successfully
- **THEN** the workflow reloads the OPNsense alias target once so the changes become active

### Requirement: Safe credential handling for alias management
The system SHALL use environment-provided OPNsense API credentials for alias management and SHALL NOT store real credentials in repository files.

#### Scenario: Missing credentials fail safely
- **WHEN** the operator runs the alias management workflow without OPNsense API credentials in the environment
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the missing credential requirement

#### Scenario: Repository files contain no real API credentials
- **WHEN** the alias management workflow is configured for local execution
- **THEN** repository files contain only secret references or variable lookups and not real OPNsense API key or secret values

### Requirement: Alias management validation
The system SHALL include validation commands for the alias management workflow using the uv-managed Ansible toolchain.

#### Scenario: Playbook syntax is valid
- **WHEN** the operator runs the documented syntax-check command
- **THEN** Ansible validates the alias management workflow syntax successfully

#### Scenario: YAML and Ansible linting pass
- **WHEN** the operator runs the documented lint commands
- **THEN** the repository YAML and alias management workflow pass linting without errors
