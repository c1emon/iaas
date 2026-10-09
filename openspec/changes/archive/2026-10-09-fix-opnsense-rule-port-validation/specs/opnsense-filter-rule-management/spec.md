## MODIFIED Requirements

### Requirement: Explicit rule fields and states
The system SHALL require each declared managed filter rule to define explicit `scope`, `slug`, `state`, `enabled`, `sequence`, interface, action, IP protocol, protocol, source, and destination fields, SHALL allow `source_net` and `destination_net` as strings or YAML lists, and SHALL accept each port selector as one port within 1..65535, an explicit ascending inclusive `start-end` range within 1..65535, or a port-type alias (a singleton list is equivalent to its scalar), SHALL default omitted `source_invert` and `destination_invert` fields to `false`, and SHALL default omitted `source_port` and `destination_port` fields to empty strings.

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
- **WHEN** a declared port field contains exactly one valid selector
- **THEN** admission and provider conversion SHALL preserve that selector as a scalar

#### Scenario: Invalid rule port selector is rejected
- **WHEN** either port field contains multiple selectors, a comma-separated string, an out-of-range port, or malformed/descending/out-of-range range
- **THEN** check, plan and sending SHALL reject it before any device write, reporting the field and reason
- **AND** multiple ports SHALL require an explicit port-type alias without widening or implicit alias creation

#### Scenario: Rule refers to an incompatible alias
- **WHEN** declaration/context facts identify a port reference as an absent or non-port alias
- **THEN** check SHALL reject the field with its reason
- **AND** plan SHALL resolve and verify the effective alias type before device writes

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
