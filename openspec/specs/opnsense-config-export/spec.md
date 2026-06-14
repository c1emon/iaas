# opnsense-config-export Specification

## Purpose

Define the OPNsense configuration export workflow, including how repository
automation captures firewall configuration snapshots safely without embedding
environment-specific secrets in source control.
## Requirements
### Requirement: Read-only OPNsense export
The system SHALL provide a read-only export workflow for selected OPNsense configuration and operational facts without modifying OPNsense state.

#### Scenario: Export selected OPNsense targets
- **WHEN** the operator runs the OPNsense export workflow with valid API credentials
- **THEN** the system exports firewall aliases, Unbound host overrides, Unbound forwarding entries, DHCPv4 lease facts, DHCPv6 lease facts, and DHCPv6 prefix lease facts

#### Scenario: No live configuration mutation
- **WHEN** the OPNsense export workflow completes successfully
- **THEN** the workflow has not created, updated, deleted, reloaded, restarted, or reconciled any OPNsense configuration or service

### Requirement: Local ignored export artifacts
The system SHALL write generated OPNsense export artifacts to a local path that is ignored by Git by default.

#### Scenario: Export artifacts are not staged accidentally
- **WHEN** the operator runs the OPNsense export workflow
- **THEN** generated export files are placed under an ignored export directory and do not appear as untracked files in normal Git status output

### Requirement: Separate configuration candidates from observed facts
The system SHALL distinguish declarative-management candidates from observed-only DHCP facts in the export output or documentation.

#### Scenario: First-stage management candidates are identifiable
- **WHEN** the operator reviews export output
- **THEN** firewall aliases, Unbound host overrides, and Unbound forwarding entries are identifiable as first-stage declarative-management candidates

#### Scenario: DHCP remains observed-only
- **WHEN** the operator reviews DHCPv4 leases, DHCPv6 leases, or DHCPv6 prefix leases
- **THEN** those outputs are identified as observed facts and not desired-state configuration to be applied

### Requirement: Credential injection through environment
The system SHALL use environment-provided OPNsense API credentials for export operations and SHALL NOT store real credentials in repository files.

#### Scenario: Missing credentials fail safely
- **WHEN** the operator runs the export workflow without OPNsense API credentials in the environment
- **THEN** the workflow fails before attempting OPNsense API export calls and reports the missing credential requirement

#### Scenario: Repository files contain only secret references
- **WHEN** the export workflow is configured for local execution
- **THEN** repository files contain only secret references or variable lookups and not real OPNsense API key or secret values

### Requirement: Export workflow validation
The system SHALL include validation commands for the export workflow using the uv-managed Ansible toolchain.

#### Scenario: Playbook syntax is valid
- **WHEN** the operator runs the documented syntax-check command
- **THEN** Ansible validates the export workflow syntax successfully

#### Scenario: YAML and Ansible linting pass
- **WHEN** the operator runs the documented lint commands
- **THEN** the repository YAML and export workflow pass linting without errors

### Requirement: Export and alias management boundary
The system SHALL document that generated OPNsense firewall alias exports are observations of live state and are not the direct source applied by the alias management workflow.

#### Scenario: Operator reviews exported firewall aliases
- **WHEN** the operator reviews generated OPNsense firewall alias export artifacts
- **THEN** the documentation identifies them as observed live state that may inform, but does not directly drive, additive alias management

#### Scenario: Operator prepares alias desired state
- **WHEN** the operator prepares aliases for the alias management workflow
- **THEN** the documentation directs the operator to use the hand-written desired-state YAML source rather than editing generated export artifacts
