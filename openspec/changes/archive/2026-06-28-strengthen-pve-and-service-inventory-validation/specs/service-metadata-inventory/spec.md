## MODIFIED Requirements

### Requirement: Generated service documentation
The system SHALL generate committed, non-sensitive service documentation from service metadata.

#### Scenario: Operator regenerates service documentation
- **WHEN** an operator runs the repository generation workflow
- **THEN** the system SHALL generate `docs/generated/services.md` from `inventory/services.yml`
- **AND** the generated document SHALL include service names, owner VMs, endpoint details, exposure, auth, FQDNs when present, and review hints when present
- **AND** it SHALL include warning records when service metadata has warning conditions

#### Scenario: Generated service documentation escapes table cells
- **WHEN** service metadata or warning records contain Markdown table metacharacters such as pipes, line feeds, or carriage returns in values rendered inside Markdown table cells
- **THEN** generated `docs/generated/services.md` SHALL keep each logical record within its intended table row and column structure
- **AND** the renderer SHALL escape or normalize those values at the Markdown table boundary
- **AND** optional omitted display values SHALL continue to render with the existing placeholder behavior

#### Scenario: Generated service documentation is stale
- **WHEN** service metadata changes without regenerating committed service documentation
- **THEN** the generated-output check SHALL fail
- **AND** it SHALL report the stale service documentation artifact

#### Scenario: Generated service documentation remains non-sensitive
- **WHEN** service documentation is generated or checked
- **THEN** the generated output SHALL NOT contain passwords, private keys, API token secrets, password hashes, or other runtime secrets
