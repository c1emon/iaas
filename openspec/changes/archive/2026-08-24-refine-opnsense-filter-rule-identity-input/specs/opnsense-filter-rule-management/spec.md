## MODIFIED Requirements

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
The system SHALL require each declared managed filter rule to define explicit `scope`, `slug`, `state`, `enabled`, `sequence`, interface, action, IP protocol, protocol, source, and destination fields.

#### Scenario: Declared filter rule has required fields
- **WHEN** each declared filter rule defines all required identity, management, and match fields
- **THEN** the workflow can generate a module-compatible rule definition and submit it to OPNsense

#### Scenario: Declared filter rule is missing required fields
- **WHEN** any declared filter rule omits a required field
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
