## MODIFIED Requirements

### Requirement: Explicit rule fields and states
The system SHALL require each declared managed filter rule to define explicit `scope`, `slug`, `state`, `enabled`, `sequence`, interface, action, IP protocol, protocol, source, and destination fields, SHALL allow `source_net` and `destination_net` to be declared either as strings or YAML lists, and SHALL default omitted `source_invert` and `destination_invert` fields to `false`.

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

#### Scenario: Declared filter rule is missing required fields
- **WHEN** any declared filter rule omits a required field other than optional invert fields
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the missing field requirement

#### Scenario: Declared filter rule uses invalid state
- **WHEN** a declared filter rule sets `state` to a value other than `present` or `absent`
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the allowed states
