## ADDED Requirements

### Requirement: Observation and recovery inputs are checked offline
Existing check entrypoints SHALL validate affected current deadline, observation, diagnostic and recovery contracts, action-specific required fields, relationships and runtime capability support without network, credential reads, provider initialization or facility side effects. Unsupported policy parameters or contract versions SHALL fail with safe input-file/field/reason diagnostics. Declarative image checking SHALL NOT use the planning host's current memory as proof of a separate execution host's capacity; optional passive executor observations SHALL be reported separately from configuration validity.

#### Scenario: Updated publication deadlines are missing
- **WHEN** a current publication input lacks required absolute deadline bindings or uses unsupported retry-policy fields
- **THEN** offline check SHALL reject the specific file/field/reason without credentials or network

#### Scenario: Check a pre-registration recovery request
- **WHEN** the selected current request declares the pre-registration evidence mode
- **THEN** check SHALL validate that mode's core binding and declared material requirements without performing resource discovery or asserting ownership
- **AND** resource association and cleanup eligibility SHALL remain online plan/start conclusions

#### Scenario: Validate a build for a remote executor
- **WHEN** supported build/test resource declarations are checked on a planning host
- **THEN** declarative check SHALL validate fields and capability relationships without claiming remote memory sufficiency or guest-start success

#### Scenario: Check ordinary PVE verification window inputs
- **WHEN** ordinary apply or independent verify has no separately declared observation deadline
- **THEN** offline check SHALL validate its existing current action inputs without requiring additional verification deadline or approval fields
- **AND** it SHALL still reject unsupported parameters; the actual internally frozen observation window SHALL be recorded at execution time
