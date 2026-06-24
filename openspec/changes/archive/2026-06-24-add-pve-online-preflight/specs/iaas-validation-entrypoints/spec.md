## ADDED Requirements

### Requirement: Explicit online PVE preflight remains outside offline validation
The system SHALL expose PVE online preflight as an explicit credentialed operation separate from default offline validation.

#### Scenario: Operator requests PVE online readiness checks
- **WHEN** an operator needs to validate live PVE readiness before plan/apply-like workflows
- **THEN** the operator SHALL use the explicit PVE preflight command
- **AND** the command SHALL be repository-owned and documented alongside other explicit PVE operations

#### Scenario: Cloud CI runs default validation
- **WHEN** GitHub Actions or another cloud CI runner runs default validation
- **THEN** it SHALL NOT run PVE online preflight
- **AND** it SHALL NOT define PVE API, SSH, 1Password, or apply-capable credentials for that preflight

#### Scenario: Online operation boundaries are documented
- **WHEN** validation documentation lists available checks
- **THEN** it SHALL distinguish offline-safe checks from the explicit PVE online preflight
- **AND** it SHALL state that PVE online preflight is read-only but still requires runtime PVE context
