## ADDED Requirements

### Requirement: Action-specific offline template check
The system SHALL select the input and existing request validator for publish, cleanup or retire according to pve-template check options.action, defaulting to publish when omitted. It SHALL reject unsupported actions without falling back to publication. Check SHALL remain offline without credentials, state changes or facility writes, and SHALL report the selected action and normalized request digest. Existing accept and recover check dispatch SHALL remain available.

#### Scenario: Check a retirement request
- **WHEN** check selects action=retire with a valid retire input
- **THEN** it SHALL validate that input using the retirement validator and succeed without requiring publication inputs or performing retirement

#### Scenario: Check a cleanup request
- **WHEN** check selects action=cleanup with a valid cleanup input
- **THEN** it SHALL validate that input using the cleanup validator without loading the original execution directory or performing cleanup

#### Scenario: Check publication or omit action
- **WHEN** check selects publish or omits action
- **THEN** it SHALL validate the selected request/publish input using the publication validator

#### Scenario: Reject invalid requests and actions
- **WHEN** the selected request violates its action-specific contract or the action is unsupported
- **THEN** check SHALL fail closed without network, state changes or facility writes

#### Scenario: Ignore unrelated action material
- **WHEN** an environment declares inputs for several actions and unrelated inputs or facility credential files are unavailable
- **THEN** check SHALL read only the selected action inputs and SHALL NOT require those unrelated materials
