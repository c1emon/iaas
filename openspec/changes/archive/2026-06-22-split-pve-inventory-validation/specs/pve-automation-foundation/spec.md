## ADDED Requirements

### Requirement: Stable offline inventory validation boundary
The system SHALL keep offline PVE inventory validation as a stable boundary that can be refactored internally without changing operator-facing validation commands or generated artifacts.

#### Scenario: Refactor validation internals without operator workflow changes
- **WHEN** the implementation splits validation code into separate modules
- **THEN** existing validation and generation commands SHALL continue to work with the same inputs
- **AND** committed generated artifacts SHALL remain unchanged when source YAML is unchanged
- **AND** online PVE checks SHALL remain separate from offline validation
