## ADDED Requirements

### Requirement: Export and alias management boundary
The system SHALL document that generated OPNsense firewall alias exports are observations of live state and are not the direct source applied by the alias management workflow.

#### Scenario: Operator reviews exported firewall aliases
- **WHEN** the operator reviews generated OPNsense firewall alias export artifacts
- **THEN** the documentation identifies them as observed live state that may inform, but does not directly drive, additive alias management

#### Scenario: Operator prepares alias desired state
- **WHEN** the operator prepares aliases for the alias management workflow
- **THEN** the documentation directs the operator to use the hand-written desired-state YAML source rather than editing generated export artifacts
