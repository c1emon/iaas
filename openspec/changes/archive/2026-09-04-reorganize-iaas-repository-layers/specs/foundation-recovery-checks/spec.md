## MODIFIED Requirements

### Requirement: Generated foundation recovery documentation
The system SHALL generate committed, non-sensitive foundation recovery documentation from Astra's foundation recovery inventory.

#### Scenario: Operator regenerates foundation recovery documentation
- **WHEN** an operator runs the foundation recovery documentation generation command
- **THEN** the system SHALL generate `environments/astra/generated/docs/foundation-recovery.md`
- **AND** the generated document SHALL include the minimum startup set, recovery order, foundation hosts, foundation services, dependencies, health checks, backup/restore metadata, break-glass metadata, storage-network facts, and warnings

#### Scenario: Generated foundation recovery documentation is stale
- **WHEN** Astra's foundation inventory changes without regenerating committed recovery documentation
- **THEN** the generated-output check SHALL fail
- **AND** it SHALL report the stale environment-specific artifact

#### Scenario: Generated foundation recovery documentation remains non-sensitive
- **WHEN** foundation recovery documentation is generated or checked
- **THEN** the generated output SHALL NOT contain passwords, private keys, API token secrets, password hashes, or other decrypted credential material
- **AND** external secret references MAY be rendered if they are reference identifiers rather than secret values
