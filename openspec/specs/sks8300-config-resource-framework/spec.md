# sks8300-config-resource-framework Specification

## Purpose

Provide a safe declarative SKS8300-series configuration resource workflow that plans, diffs, applies only with explicit opt-in, verifies post-state, and remains separate from read-only facts collection.

## Requirements

### Requirement: Separate SKS8300 configuration workflow
The system SHALL provide XikeOS configuration management through a configuration workflow separate from the read-only facts workflow, using native `c1emon.xikeos` resource modules directly as the primary lifecycle engine and repository role/playbook code only for policy orchestration.

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

### Requirement: Declarative configuration intent
The system SHALL manage XikeOS configuration using collection-native resource module inputs rather than arbitrary operator-provided CLI command lists or repository-translated resource schemas.

#### Scenario: Declare VLAN intent
- **WHEN** the operator declares VLAN resources for the configuration workflow
- **THEN** the declaration SHALL use the `c1emon.xikeos.xikeos_vlans` module `state` and `config` schema
- **AND** the workflow SHALL pass that config directly to `c1emon.xikeos.xikeos_vlans` without translating repository-specific field aliases

#### Scenario: Declare interface and routing intent
- **WHEN** the operator declares base interface, L2 interface, L3 interface, LAG interface, static route, or ACL resources
- **THEN** each declaration SHALL use the corresponding lifecycle-complete `c1emon.xikeos` resource module `state` and `config` schema
- **AND** the workflow SHALL pass those configs directly to the matching collection module when repository safety gates allow preview or apply

#### Scenario: Reject raw arbitrary configuration commands as primary interface
- **WHEN** the operator attempts to provide arbitrary configuration command strings as the primary configuration interface
- **THEN** the workflow SHALL reject that input
- **AND** it SHALL instruct the operator to use collection-native resource module inputs or separately documented fallback workflows

#### Scenario: Reject repository-specific translated intent
- **WHEN** the operator provides the legacy `switch_config_intent` shape
- **THEN** the workflow SHALL reject that input
- **AND** it SHALL instruct the operator to use collection-native `switch_config_resources` entries with module `state` and `config` fields

### Requirement: Plan, diff, apply, and verify lifecycle
The system SHALL follow a lifecycle for XikeOS configuration changes where collection modules own resource validation, diff, check-mode preview, command generation, apply, and after-state, while the repository owns apply gating and reporting.

#### Scenario: Generate plan without applying by default
- **WHEN** the operator runs the configuration workflow without explicit apply enabled
- **THEN** the workflow SHALL invoke configured lifecycle-safe collection resource modules in check mode
- **AND** it SHALL aggregate module results such as `changed`, `commands`, `before`, and `after` as the plan
- **AND** it SHALL NOT send mutating configuration commands to the switch

#### Scenario: Apply only with explicit opt-in
- **WHEN** the operator sets `switch_config_apply: true`
- **THEN** the workflow MAY invoke lifecycle-safe `c1emon.xikeos` resource modules for configured resources
- **AND** it SHALL apply only module calls whose requested state is allowed by repository policy
- **AND** it SHALL reject requested states or returned command summaries that match forbidden destructive patterns

#### Scenario: Verify post-state through module results
- **WHEN** configuration changes have been previewed or applied
- **THEN** the workflow SHALL rely on collection module `before`, `after`, `commands`, gathered output, or check-mode results as the authoritative lifecycle result
- **AND** it SHALL report collection module failures clearly

### Requirement: Resource registry for idempotent configuration
The system SHALL delegate XikeOS configuration resource identity, fields, diff, command generation, and verification behavior to lifecycle-complete `c1emon.xikeos` resource module schemas wherever available.

#### Scenario: Match resources by collection primary key
- **WHEN** the workflow previews or applies desired resources
- **THEN** it SHALL rely on the corresponding collection module to interpret resource identity and compute the minimal changes required to reach desired state
- **AND** repository code SHALL NOT maintain a parallel primary-key registry for XikeOS resource schemas

#### Scenario: Respect collection field metadata
- **WHEN** a collection module schema marks a field as read-only, sensitive, required, defaulted, or unsupported
- **THEN** the workflow SHALL pass the config to the collection module and rely on that module to enforce the schema
- **AND** repository reporting SHALL avoid exposing module results in a way that leaks plaintext secrets

#### Scenario: Export module lifecycle report
- **WHEN** the workflow generates a configuration plan or applies changes
- **THEN** it SHALL export a change report containing requested collection-native resources, module preview/apply results, command summaries, apply status, and failure details
- **AND** the report SHALL NOT expose plaintext secrets

### Requirement: Configuration safety guardrails
The system SHALL include safety guardrails for SKS8300/XikeOS configuration workflows, including when the underlying mutation is performed by `c1emon.xikeos` resource modules.

#### Scenario: Restrict allowed states
- **WHEN** `switch_config_allowed_states` is configured
- **THEN** the workflow SHALL only preview or apply resource module calls whose `state` is included in that allowlist
- **AND** it SHALL reject requested states outside the allowlist before invoking mutating module execution

#### Scenario: Block destructive commands
- **WHEN** collection module command output or requested fallback raw config include destructive patterns such as `reload`, `erase`, `delete startup-config`, `write erase`, or equivalent reset operations
- **THEN** the workflow SHALL fail before apply
- **AND** it SHALL include the blocked operation in the failure message without exposing secrets

#### Scenario: Preserve auditability
- **WHEN** the workflow previews or applies configuration changes
- **THEN** it SHALL produce an auditable report of requested resources, collection module command summaries, change status, and module lifecycle result
- **AND** sensitive values SHALL be redacted from logs and reports

### Requirement: SKS8300 interface VLAN resource intent
The system SHALL support SKS8300 interface VLAN configuration through declarative `interfaces` resource intent in the existing configuration workflow.

#### Scenario: Declare access port VLAN intent
- **WHEN** an operator declares an interface resource with `mode: access` and an `access_vlan`
- **THEN** the configuration workflow SHALL validate the interface name, mode, and VLAN ID
- **AND** it SHALL plan changes by comparing the declared access VLAN against current parsed interface state
- **AND** it SHALL render interface configuration commands only from validated intent

#### Scenario: Declare trunk tagged VLAN intent
- **WHEN** an operator declares an interface resource with `mode: trunk` and `tagged_vlans`
- **THEN** the configuration workflow SHALL validate the tagged VLAN ID list
- **AND** it SHALL plan mode and tagged membership changes from current parsed interface state
- **AND** it SHALL verify post-state tagged VLAN membership after apply

#### Scenario: Declare hybrid tagged and untagged VLAN intent
- **WHEN** an operator declares an interface resource with `mode: hybrid`, `tagged_vlans`, and `untagged_vlans`
- **THEN** the configuration workflow SHALL validate all VLAN ID lists
- **AND** it SHALL plan tagged and untagged membership changes separately
- **AND** it SHALL verify that post-state satisfies the declared mode and VLAN membership

### Requirement: Interface configuration safety guardrails
The system SHALL include safety guardrails specific to SKS8300 interface VLAN resources.

#### Scenario: Reject unsupported interface fields
- **WHEN** an operator declares unsupported interface fields or raw interface commands
- **THEN** the configuration workflow SHALL reject the intent before rendering commands
- **AND** it SHALL report the unsupported fields without applying changes

#### Scenario: Reject inconsistent interface mode fields
- **WHEN** an operator declares interface fields inconsistent with the selected mode
- **THEN** the configuration workflow SHALL reject the intent before rendering commands
- **AND** it SHALL explain the mode-specific field requirement that failed

#### Scenario: Keep port changes apply-gated
- **WHEN** an operator runs the interface VLAN workflow without `switch_config_apply: true`
- **THEN** the workflow SHALL collect current state and produce a plan only
- **AND** it SHALL NOT send interface configuration commands to the switch

#### Scenario: Verify interface post-state after apply
- **WHEN** interface configuration commands have been applied
- **THEN** the workflow SHALL re-collect or inspect interface state
- **AND** it SHALL fail verification if mode, access VLAN, tagged VLANs, or untagged VLANs do not satisfy declared intent
