## ADDED Requirements

### Requirement: Explicit PVE guest verification remains outside offline validation
The system SHALL expose PVE guest verification as an explicit online operation separate from default offline validation.

#### Scenario: Operator requests guest verification
- **WHEN** an operator needs to validate guest-side readiness for declared PVE VMs
- **THEN** the operator SHALL use the explicit PVE guest verification command
- **AND** the command SHALL be repository-owned and documented alongside other explicit PVE operations

#### Scenario: Cloud CI runs default validation
- **WHEN** GitHub Actions or another cloud CI runner runs default validation
- **THEN** it SHALL NOT run PVE guest verification
- **AND** it SHALL NOT define guest SSH, PVE API, 1Password, or apply-capable credentials for that verification

#### Scenario: Validation documentation lists guest verification
- **WHEN** validation documentation lists available checks
- **THEN** it SHALL distinguish offline-safe checks from explicit PVE guest verification
- **AND** it SHALL state that PVE guest verification is read-only but still requires runtime guest SSH context
