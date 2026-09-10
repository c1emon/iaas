## ADDED Requirements

### Requirement: Provider-compatible existing resource admission
Before writes, the runtime SHALL validate every desired resource against locally provable field semantics and the pinned Collection's basic primitive constraints.

#### Scenario: A later gateway record violates a known numeric bound
- **WHEN** a desired batch includes a record such as latency_low 0, loss_high 100 or interval 10000 that the pinned 26.1.11 Collection rejects
- **THEN** the entire batch SHALL fail local validation before credentials, API access or earlier-record mutation
- **AND** Python and Ansible admission SHALL agree on supported numeric and inversion semantics

#### Scenario: Dependency constraints are refreshed
- **WHEN** the explicitly installed Collection baseline changes
- **THEN** representative boundary tests SHALL compare the accepted primitive ranges with that baseline
- **AND** the runtime SHALL NOT copy the entire server validation model or relax default-gateway ownership

### Requirement: Type-specific extended alias validation
The offline validator SHALL accept the managed types `host`, `network`, `port`, `urltable` and `networkgroup` with exact resource-specific fields, preserving existing static-alias behavior.

#### Scenario: URL table fields are invalid
- **WHEN** URL content is empty or malformed, a present URL table lacks `updatefreq_days`, or that value is not a decimal string of at least 0.1 days with at most one fractional digit and an unchanged finite numeric round-trip through the pinned Collection
- **THEN** validation SHALL fail with field context before credentials or network access
- **AND** URL reachability and downloaded contents SHALL NOT be checked during offline validation

#### Scenario: Fields do not belong to the alias type
- **WHEN** a non-URL-table alias includes refresh fields, an unsupported type is supplied, or an unknown field is present
- **THEN** validation SHALL fail without coercion or silently discarded input
- **AND** the existing required common fields SHALL remain required, including for absent declarations

#### Scenario: A frequency would be rounded by the dependency
- **WHEN** the caller supplies a value such as `"0.01"` or `"0.15"`
- **THEN** offline validation SHALL reject it rather than allow the Collection to change the requested frequency

### Requirement: Locally provable alias reference validation
The validator SHALL validate local group dependencies while distinguishing unresolved external references from invalid local references.

#### Scenario: Local dependency is invalid
- **WHEN** a surviving present group has duplicate members, self-reference, a locally detectable cycle, a local absent member or a local non-address member
- **THEN** validation SHALL fail before credential preflight or mutation

#### Scenario: Reference is not declared locally
- **WHEN** a surviving present group member is a valid alias name but has no local declaration
- **THEN** offline validation SHALL preserve it as an unresolved external reference
- **AND** offline success SHALL NOT claim that it exists or is compatible on the appliance
- **AND** the explicit online alias workflow SHALL resolve it before writes

#### Scenario: A group and its members are all marked absent
- **WHEN** absent records have valid required field shapes and syntax
- **THEN** offline validation SHALL NOT reject them because obsolete group content references an absent or missing member
- **AND** online removal ordering SHALL be derived from live dependencies rather than caller-supplied obsolete member content
