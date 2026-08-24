# opnsense-filter-rule-management Specification

## Purpose
TBD - created by archiving change manage-opnsense-filter-rules. Update Purpose after archive.

## Requirements

### Requirement: Hand-written filter rule desired state
The system SHALL define OPNsense new firewall filter rules from a hand-written YAML source file using the `opnsense_filter_rules` variable.

#### Scenario: Desired filter rules are reviewed as source configuration
- **WHEN** an operator reviews the OPNsense filter rule management input
- **THEN** the desired filter rules are represented in a repository YAML file intended for manual review and editing

#### Scenario: Export artifacts are not used as the direct apply source
- **WHEN** the filter rule management workflow is run
- **THEN** it reads desired filter rules from the hand-written YAML source and not directly from generated export output or legacy CSV exports

### Requirement: New filter rule system only
The system SHALL manage OPNsense API-backed new firewall filter rules and SHALL NOT manage legacy firewall rules.

#### Scenario: Declared filter rule is applied
- **WHEN** the operator runs the filter rule management workflow with a declared rule
- **THEN** the workflow applies the rule through the OPNsense new filter rule API using `oxlorg.opnsense.rule_multi`

#### Scenario: Legacy rules remain outside scope
- **WHEN** legacy firewall rules exist in OPNsense
- **THEN** the filter rule management workflow does not import, update, delete, disable, or purge those legacy rules

### Requirement: Strict description identity
The system SHALL derive each managed filter rule `description` from required `scope` and `slug` fields as `iaas:opnsense:filter:<scope>:<slug>`, SHALL use that generated description as the immutable identity, and SHALL require both `scope` and `slug` to match `^[a-z0-9][a-z0-9-]*$`.

#### Scenario: Managed rule has valid identity description
- **WHEN** every declared filter rule has `scope` and `slug` values using lowercase letters, numbers, and hyphens
- **THEN** the workflow generates descriptions in `iaas:opnsense:filter:<scope>:<slug>` format and allows validation to continue

#### Scenario: Managed rule has invalid identity description
- **WHEN** a declared filter rule has a missing `scope` or `slug`, uppercase letters, underscores, spaces, appended labels, or otherwise fails the required identity part pattern
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the invalid identity part format

#### Scenario: Managed rule declares raw description
- **WHEN** a declared filter rule includes a direct `description` field in `opnsense_filter_rules`
- **THEN** the workflow fails before attempting OPNsense API write calls and reports that `description` is generated from `scope` and `slug`

### Requirement: Unique managed filter rule identity
The system SHALL require all generated managed filter rule descriptions to be globally unique.

#### Scenario: Duplicate managed descriptions are declared
- **WHEN** two or more declared filter rules have `scope` and `slug` values that generate the same `description`
- **THEN** the workflow fails before attempting OPNsense API write calls and reports duplicate managed filter rule identities

#### Scenario: Managed descriptions are unique
- **WHEN** every declared filter rule has a distinct generated `description`
- **THEN** the workflow can match each declared rule to at most one desired identity

### Requirement: Description-based matching
The system SHALL call `oxlorg.opnsense.rule_multi` with `match_fields` set to `['description']` for managed filter rules, using internally generated descriptions derived from `scope` and `slug`.

#### Scenario: Declared present rule does not exist
- **WHEN** the operator runs the filter rule management workflow with a declared filter rule using `state: present` whose generated description does not exist in OPNsense new filter rules
- **THEN** the workflow creates that declared rule in OPNsense with the generated description

#### Scenario: Declared present rule already exists
- **WHEN** the operator runs the filter rule management workflow with a declared filter rule using `state: present` whose generated description already exists in OPNsense new filter rules
- **THEN** the workflow updates the existing rule fields according to the desired YAML source

#### Scenario: Declared absent rule exists
- **WHEN** the operator runs the filter rule management workflow with a declared filter rule using `state: absent` whose generated description exists in OPNsense new filter rules
- **THEN** the workflow removes that declared rule from OPNsense

### Requirement: Explicit rule fields and states
The system SHALL require each declared managed filter rule to define explicit `scope`, `slug`, `state`, `enabled`, `sequence`, interface, action, IP protocol, protocol, source, and destination fields, SHALL allow `source_net`, `destination_net`, `source_port`, and `destination_port` to be declared either as strings or YAML lists, SHALL default omitted `source_invert` and `destination_invert` fields to `false`, and SHALL default omitted `source_port` and `destination_port` fields to empty strings.

#### Scenario: Declared filter rule has required fields
- **WHEN** each declared filter rule defines all required identity, management, and match fields
- **THEN** the workflow can generate a module-compatible rule definition and submit it to OPNsense

#### Scenario: Declared invert fields are omitted
- **WHEN** a declared filter rule omits `source_invert` or `destination_invert`
- **THEN** the workflow generates module input with the omitted invert field set to `false`

#### Scenario: Declared invert field is explicit true
- **WHEN** a declared filter rule sets `source_invert` or `destination_invert` to `true`
- **THEN** the workflow preserves the explicit `true` value in generated module input

#### Scenario: Declared net field uses a list
- **WHEN** a declared filter rule sets `source_net` or `destination_net` to a YAML list
- **THEN** the workflow converts that list to a comma-separated string before calling `oxlorg.opnsense.rule_multi`

#### Scenario: Declared net field uses a string
- **WHEN** a declared filter rule sets `source_net` or `destination_net` to a string
- **THEN** the workflow passes that string through to the generated module input unchanged

#### Scenario: Declared port field is explicit
- **WHEN** a declared filter rule sets `source_port` or `destination_port` to a port, range, or alias
- **THEN** the workflow preserves the explicit value in generated module input

#### Scenario: Declared port field uses a list
- **WHEN** a declared filter rule sets `source_port` or `destination_port` to a YAML list
- **THEN** the workflow converts that list to a comma-separated string before calling `oxlorg.opnsense.rule_multi`

#### Scenario: Declared port field uses a string
- **WHEN** a declared filter rule sets `source_port` or `destination_port` to a string
- **THEN** the workflow preserves the explicit value in generated module input

#### Scenario: Declared port fields are omitted
- **WHEN** a declared filter rule omits `source_port` or `destination_port`
- **THEN** the workflow generates module input with the omitted port field set to an empty string

#### Scenario: Declared filter rule is missing required fields
- **WHEN** any declared filter rule omits a required field other than optional invert or port fields
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the missing field requirement

#### Scenario: Declared filter rule uses invalid state
- **WHEN** a declared filter rule sets `state` to a value other than `present` or `absent`
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the allowed states

### Requirement: Sequence-based rule ordering
The system SHALL use each managed filter rule `sequence` field to control rule processing order and SHALL NOT include `sequence` in the matching identity.

#### Scenario: Rule sequence changes
- **WHEN** a declared filter rule keeps the same `scope` and `slug` but changes `sequence`
- **THEN** the workflow treats it as an update to the same managed rule rather than a different identity

#### Scenario: Managed rules are applied with explicit order
- **WHEN** the operator declares managed filter rules with sequence values
- **THEN** the workflow sends those sequence values to OPNsense so rule processing order follows the desired state

### Requirement: Preserve unmanaged filter rules
The system SHALL NOT delete, disable, or purge OPNsense filter rules that are absent from `opnsense_filter_rules`.

#### Scenario: Unlisted new filter rule exists
- **WHEN** OPNsense contains a new filter rule that is absent from `opnsense_filter_rules`
- **THEN** the filter rule management workflow leaves that rule present and unchanged

### Requirement: Filter rule apply after successful changes
The system SHALL apply or reload the OPNsense filter rule target after successfully applying declared filter rule changes.

#### Scenario: Filter rule apply changes OPNsense state
- **WHEN** the filter rule management workflow creates, updates, or removes a declared filter rule successfully
- **THEN** the workflow applies or reloads the OPNsense filter rule target so the changes become active

#### Scenario: Filter rule apply makes no changes
- **WHEN** the filter rule management workflow completes without creating, updating, or removing any declared filter rule
- **THEN** the workflow does not perform an unnecessary apply or reload operation

### Requirement: Safe credential handling for filter rule management
The system SHALL use environment-provided OPNsense API credentials for filter rule management and SHALL NOT store real credentials in repository files.

#### Scenario: Missing credentials fail safely
- **WHEN** the operator runs the filter rule management workflow without OPNsense API credentials in the environment
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the missing credential requirement

#### Scenario: Repository files contain no real API credentials
- **WHEN** the filter rule management workflow is configured for local execution
- **THEN** repository files contain only secret references or variable lookups and not real OPNsense API key or secret values

### Requirement: Filter rule management validation
The system SHALL include validation commands for the filter rule management workflow using the uv-managed Ansible toolchain.

#### Scenario: Playbook syntax is valid
- **WHEN** the operator runs the documented syntax-check command
- **THEN** Ansible validates the filter rule management workflow syntax successfully

#### Scenario: YAML and Ansible linting pass
- **WHEN** the operator runs the documented lint commands
- **THEN** the repository YAML and filter rule management workflow pass linting without errors
