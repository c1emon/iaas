## ADDED Requirements

### Requirement: Scoped non-mutating Python quality checks
Repository validation SHALL include Python lint and stricter type checks for an explicitly configured set of new boundary modules. The scope SHALL be consistent between local and CI execution and SHALL exclude vendored and generated code. Quality checks SHALL not modify files, contact infrastructure or require runtime credentials.

#### Scenario: Selected module violates a quality rule
- **WHEN** a configured source file contains an enabled lint violation or strict type error
- **THEN** the repository-owned quality gate fails in both fast and full validation
- **AND** no automatic fix or reformat is applied

#### Scenario: Unrelated legacy module is checked
- **WHEN** a legacy file outside the stricter scope is part of existing project validation
- **THEN** its previous type-checking mode remains in force
- **AND** the new gate does not trigger an unrelated repository-wide formatting migration

#### Scenario: CI and local checks run the same commit
- **WHEN** local and CI invoke the quality gate with the same locked tools and source tree
- **THEN** both use the same configured rule and path sets regardless of Git comparison base
