## MODIFIED Requirements

### Requirement: Separate SKS8300 configuration workflow
The system SHALL provide XikeOS configuration management through a configuration workflow separate from the read-only facts workflow, using native `c1emon.xikeos` resource modules as the primary lifecycle engine.

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
The system SHALL manage XikeOS configuration using declarative resource intent that maps to lifecycle-complete collection module schemas rather than arbitrary operator-provided CLI command lists.

#### Scenario: Declare VLAN intent
- **WHEN** the operator declares VLAN resources with collection-supported fields
- **THEN** the configuration workflow SHALL validate the intent against the `c1emon.xikeos.xikeos_vlans` resource schema
- **AND** it SHALL plan changes based on collection-native current state rather than blindly rendering commands
- **AND** it SHALL prefer `c1emon.xikeos.xikeos_vlans` for supported VLAN mutation when repository safety gates allow apply

#### Scenario: Declare interface and routing intent
- **WHEN** the operator declares supported base interface, L2 interface, L3 interface, LAG interface, static route, or ACL intent
- **THEN** the configuration workflow SHALL validate that intent against the corresponding lifecycle-complete `c1emon.xikeos` resource schema
- **AND** it SHALL prefer the matching lifecycle-safe collection module when repository safety gates allow apply

#### Scenario: Reject raw arbitrary configuration commands as primary interface
- **WHEN** the operator attempts to provide arbitrary configuration command strings as the primary configuration interface
- **THEN** the workflow SHALL reject that input
- **AND** it SHALL instruct the operator to use supported declarative resource intent or documented lifecycle-safe collection resource modules

### Requirement: Plan, diff, apply, and verify lifecycle
The system SHALL follow a fixed lifecycle for XikeOS configuration changes: collect current state, validate intent, compute a plan or module command set, apply only when explicitly enabled, verify post-state, and export a change report.

#### Scenario: Generate plan without applying by default
- **WHEN** the operator runs the configuration workflow without explicit apply enabled
- **THEN** the workflow SHALL collect current state through collection facts, gathered state, or resource module preview
- **AND** it SHALL generate a plan, rendered command set, check-mode result, or equivalent module preview
- **AND** it SHALL NOT send mutating configuration commands to the switch

#### Scenario: Apply only with explicit opt-in
- **WHEN** the operator sets `switch_config_apply: true`
- **THEN** the workflow MAY invoke lifecycle-safe `c1emon.xikeos` resource modules for supported resources
- **AND** it SHALL apply only changes generated from validated declarative intent
- **AND** it SHALL reject commands or requested operations that match forbidden destructive patterns

#### Scenario: Verify post-state after apply
- **WHEN** configuration changes have been applied
- **THEN** the workflow SHALL collect or inspect post-change state through `ansible_network_resources`, resource module after-state, or gathered resource output
- **AND** it SHALL verify that the resulting state satisfies the declared intent
- **AND** it SHALL report verification failures clearly

### Requirement: Resource registry for idempotent configuration
The system SHALL delegate XikeOS configuration resource identity, fields, diff, command generation, and verification behavior to lifecycle-complete `c1emon.xikeos` resource module schemas wherever available.

#### Scenario: Match resources by collection primary key
- **WHEN** the workflow compares desired resources against current state
- **THEN** it SHALL use the identity semantics of the corresponding collection resource module, such as VLAN ID for VLANs or resource name for interfaces
- **AND** it SHALL compute or request only the changes required to reach the desired state

#### Scenario: Respect collection field metadata
- **WHEN** a collection module schema marks a field as read-only, sensitive, required, defaulted, or unsupported
- **THEN** the workflow SHALL enforce or pass through that metadata during validation, planning, module invocation, render, and report generation

#### Scenario: Export old state, new intent, and diff
- **WHEN** the workflow generates a configuration plan or applies changes
- **THEN** it SHALL export a change report containing collection-native current state, desired intent, generated diff or module command set, and apply/verify status
- **AND** the report SHALL NOT expose plaintext secrets
