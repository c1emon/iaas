## MODIFIED Requirements

### Requirement: Separate SKS8300 configuration workflow
The system SHALL provide XikeOS configuration management through a configuration
workflow separate from the read-only facts workflow, using native
`c1emon.xikeos` resource modules directly as the primary lifecycle engine and
repository role/playbook code only for policy orchestration.

#### Scenario: Keep read-only facts separate from configuration changes
- **WHEN** an operator runs the read-only facts playbook
- **THEN** the playbook SHALL NOT perform configuration mutation
- **AND** configuration changes SHALL require a separate configuration workflow or role

#### Scenario: Use native XikeOS platform for configuration execution
- **WHEN** the configuration workflow is invoked for a XikeOS switch
- **THEN** it SHALL use `ansible_network_os: c1emon.xikeos.xikeos` for terminal and cliconf behavior
- **AND** it SHALL keep host connection and credentials supplied by inventory or runtime variables

#### Scenario: Preserve repository orchestration around collection modules
- **WHEN** the configuration workflow delegates a supported resource to a `c1emon.xikeos` module
- **THEN** repository-level apply gates, allowed-state policy, reporting, and module ordering SHALL still apply
- **AND** repository logic SHALL NOT duplicate collection resource schemas, field validation, diffing, command rendering, or platform behavior

#### Scenario: Keep configuration role only as policy orchestrator
- **WHEN** a configuration role remains in the repository
- **THEN** it SHALL be documented and tested as a repository safety/orchestration layer
- **AND** it SHALL not be required for operators who choose to call `c1emon.xikeos` lifecycle resource modules directly outside the repository workflow
