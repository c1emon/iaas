# sks8300-config-resource-framework Specification

## Purpose

Provide a safe declarative SKS8300-series configuration resource workflow that plans, diffs, applies only with explicit opt-in, verifies post-state, and remains separate from read-only facts collection.
## Requirements
### Requirement: Separate SKS8300 configuration workflow
The system SHALL provide SKS8300/XikeOS-series configuration management through a configuration workflow separate from the read-only facts workflow, using native `c1emon.xikeos` resource modules where they satisfy the workflow safety requirements.

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
- **THEN** repository-level apply gates, allowed-operation policy, reporting, and verification expectations SHALL still apply

### Requirement: Declarative configuration intent
The system SHALL manage SKS8300/XikeOS configuration using declarative resource intent and lifecycle-safe collection modules where available, rather than arbitrary operator-provided CLI command lists.

#### Scenario: Declare VLAN intent
- **WHEN** the operator declares VLAN resources with IDs, names, and desired state
- **THEN** the configuration workflow SHALL validate the intent against the supported repository or collection resource schema
- **AND** it SHALL plan changes based on current switch state rather than blindly rendering commands
- **AND** it SHALL prefer `c1emon.xikeos.xikeos_vlans` for supported VLAN mutation when repository safety gates allow apply

#### Scenario: Declare interface intent
- **WHEN** the operator declares supported base, L2, L3, or LAG interface intent
- **THEN** the configuration workflow SHALL validate that intent against supported resource schemas
- **AND** it SHALL prefer matching lifecycle-safe `c1emon.xikeos` interface resource modules when repository safety gates allow apply

#### Scenario: Reject raw arbitrary configuration commands as primary interface
- **WHEN** the operator attempts to provide arbitrary configuration command strings as the primary configuration interface
- **THEN** the workflow SHALL reject that input
- **AND** it SHALL instruct the operator to use supported declarative resource intent or documented lifecycle-safe collection resource modules

### Requirement: Plan, diff, apply, and verify lifecycle
The system SHALL follow a fixed lifecycle for SKS8300/XikeOS configuration changes: collect current state, validate intent, compute a plan or module command set, apply only when explicitly enabled, verify post-state, and export a change report.

#### Scenario: Generate plan without applying by default
- **WHEN** the operator runs the configuration workflow without explicit apply enabled
- **THEN** the workflow SHALL collect current state and generate a plan, diff, rendered command set, check-mode result, or equivalent module preview
- **AND** it SHALL NOT send mutating configuration commands to the switch

#### Scenario: Apply only with explicit opt-in
- **WHEN** the operator sets `switch_config_apply: true`
- **THEN** the workflow MAY invoke lifecycle-safe `c1emon.xikeos` resource modules or validated rendered commands for supported resources
- **AND** it SHALL apply only changes generated from validated declarative intent
- **AND** it SHALL reject commands or requested operations that match forbidden destructive patterns

#### Scenario: Verify post-state after apply
- **WHEN** configuration changes have been applied
- **THEN** the workflow SHALL collect or inspect post-change state through collection facts, resource module after-state, or compatibility verification logic
- **AND** it SHALL verify that the resulting state satisfies the declared intent
- **AND** it SHALL report verification failures clearly

### Requirement: Resource registry for idempotent configuration
The system SHALL define or delegate SKS8300/XikeOS configuration resources through schemas that describe identity, fields, collection, diff or command generation, and verification behavior.

#### Scenario: Match resources by primary key
- **WHEN** the workflow compares desired VLAN resources against current state
- **THEN** it SHALL match VLANs by VLAN ID as the primary key
- **AND** it SHALL compute or request only the changes required to reach the desired state

#### Scenario: Respect field metadata
- **WHEN** a repository schema or collection module schema marks a field as read-only, sensitive, required, defaulted, or unsupported
- **THEN** the workflow SHALL enforce that metadata during validation, planning, module invocation, render, and report generation

#### Scenario: Export old state, new intent, and diff
- **WHEN** the workflow generates a configuration plan or applies changes
- **THEN** it SHALL export a change report containing current state, desired intent, generated diff or module command set, and apply/verify status
- **AND** the report SHALL NOT expose plaintext secrets

### Requirement: Configuration safety guardrails
The system SHALL include safety guardrails for SKS8300/XikeOS configuration workflows, including when the underlying mutation is performed by `c1emon.xikeos` resource modules.

#### Scenario: Restrict allowed operations
- **WHEN** `switch_config_allowed_operations` is configured
- **THEN** the workflow SHALL only plan, invoke, and apply operations included in that allowlist
- **AND** it SHALL reject intent requiring operations outside the allowlist

#### Scenario: Block destructive commands
- **WHEN** rendered candidate commands, collection module command output, or requested fallback raw config include destructive patterns such as `reload`, `erase`, `delete startup-config`, `write erase`, or equivalent reset operations
- **THEN** the workflow SHALL fail before apply
- **AND** it SHALL include the blocked operation in the failure message without exposing secrets

#### Scenario: Preserve auditability
- **WHEN** the workflow plans or applies configuration changes
- **THEN** it SHALL produce an auditable report of planned operations, collection module command summaries, change status, and verification outcome
- **AND** sensitive values SHALL be redacted from logs and reports
