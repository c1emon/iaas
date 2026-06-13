## ADDED Requirements

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
