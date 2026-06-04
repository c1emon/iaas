## ADDED Requirements

### Requirement: Separate SKS8300 configuration workflow
The system SHALL provide SKS8300-series configuration management through a configuration workflow separate from the read-only facts workflow.

#### Scenario: Keep read-only facts separate from configuration changes
- **WHEN** an operator runs the read-only facts playbook
- **THEN** the playbook SHALL NOT perform configuration mutation
- **AND** configuration changes SHALL require a separate configuration workflow or role

#### Scenario: Use SKS8300 platform profile for configuration planning
- **WHEN** the configuration workflow is invoked
- **THEN** it SHALL use `switch_platform_profile: sks8300` to select SKS8300-specific parsing, validation, diff, render, and verification behavior
- **AND** it SHALL keep host connection and credentials supplied by inventory or runtime variables

### Requirement: Declarative configuration intent
The system SHALL manage SKS8300 configuration using declarative resource intent rather than arbitrary operator-provided CLI command lists.

#### Scenario: Declare VLAN intent
- **WHEN** the operator declares VLAN resources with IDs, names, and desired state
- **THEN** the configuration workflow SHALL validate the intent against the SKS8300 resource schema
- **AND** it SHALL plan changes based on current switch state rather than blindly rendering commands

#### Scenario: Reject raw arbitrary configuration commands as primary interface
- **WHEN** the operator attempts to provide arbitrary configuration command strings as the primary configuration interface
- **THEN** the workflow SHALL reject that input
- **AND** it SHALL instruct the operator to use supported declarative resource intent

### Requirement: Plan, diff, apply, and verify lifecycle
The system SHALL follow a fixed lifecycle for SKS8300 configuration changes: collect current state, parse facts, validate intent, compute diff, render candidate commands, apply only when explicitly enabled, verify post-state, and export a change report.

#### Scenario: Generate plan without applying by default
- **WHEN** the operator runs the configuration workflow without explicit apply enabled
- **THEN** the workflow SHALL collect current state and generate a plan or diff
- **AND** it SHALL NOT send mutating configuration commands to the switch

#### Scenario: Apply only with explicit opt-in
- **WHEN** the operator sets `switch_config_apply: true`
- **THEN** the workflow MAY send profile-rendered configuration commands to the switch
- **AND** it SHALL apply only commands generated from validated declarative intent
- **AND** it SHALL reject commands that match forbidden destructive patterns

#### Scenario: Verify post-state after apply
- **WHEN** configuration commands have been applied
- **THEN** the workflow SHALL collect or inspect post-change state
- **AND** it SHALL verify that the resulting state satisfies the declared intent
- **AND** it SHALL report verification failures clearly

### Requirement: Resource registry for idempotent configuration
The system SHALL define SKS8300 configuration resources in a resource registry that describes identity, fields, collection, diff, render, and verification behavior.

#### Scenario: Match resources by primary key
- **WHEN** the workflow compares desired VLAN resources against current state
- **THEN** it SHALL match VLANs by VLAN ID as the primary key
- **AND** it SHALL compute only the changes required to reach the desired state

#### Scenario: Respect field metadata
- **WHEN** a resource schema marks a field as read-only, sensitive, required, or defaulted
- **THEN** the workflow SHALL enforce that metadata during validation, diff, render, and report generation

#### Scenario: Export old state, new intent, and diff
- **WHEN** the workflow generates a configuration plan or applies changes
- **THEN** it SHALL export a change report containing current state, desired intent, generated diff, and apply/verify status
- **AND** the report SHALL NOT expose plaintext secrets

### Requirement: Configuration safety guardrails
The system SHALL include safety guardrails for SKS8300 configuration workflows.

#### Scenario: Restrict allowed operations
- **WHEN** `switch_config_allowed_operations` is configured
- **THEN** the workflow SHALL only plan and apply operations included in that allowlist
- **AND** it SHALL reject intent requiring operations outside the allowlist

#### Scenario: Block destructive commands
- **WHEN** rendered candidate commands include destructive patterns such as `reload`, `erase`, `delete startup-config`, `write erase`, or equivalent reset operations
- **THEN** the workflow SHALL fail before apply
- **AND** it SHALL include the blocked operation in the failure message without exposing secrets

#### Scenario: Preserve auditability
- **WHEN** the workflow plans or applies configuration changes
- **THEN** it SHALL produce an auditable report of planned operations, rendered command summaries, change status, and verification outcome
- **AND** sensitive values SHALL be redacted from logs and reports
