## MODIFIED Requirements

### Requirement: Service metadata source of truth
The system SHALL support operator-authored service metadata at `environments/astra/inventory/services.yml`.

#### Scenario: Operator declares a service owned by a PVE VM
- **WHEN** an operator declares a service in `environments/astra/inventory/services.yml`
- **THEN** the declaration SHALL include a unique service name
- **AND** it SHALL include an `owner_vm` that references a VM declared in `environments/astra/inventory/vms.yml`
- **AND** it SHALL include one or more service endpoints
- **AND** it MAY include an operator-readable description

#### Scenario: Service metadata references an unknown VM
- **WHEN** a service declaration references an `owner_vm` that is not declared in Astra's VM inventory
- **THEN** service inventory validation SHALL fail before generated service documentation is accepted
- **AND** the failure SHALL identify the invalid service and missing VM reference

### Requirement: Generated service documentation
The system SHALL generate committed, non-sensitive service documentation from Astra service metadata.

#### Scenario: Operator regenerates service documentation
- **WHEN** an operator runs the repository generation workflow
- **THEN** the system SHALL generate `environments/astra/generated/docs/services.md` from `environments/astra/inventory/services.yml`
- **AND** the generated document SHALL include service names, owner VMs, endpoint details, exposure, auth, FQDNs when present, review hints when present, and warning records

#### Scenario: Generated service documentation escapes table cells
- **WHEN** service metadata or warning records contain Markdown table metacharacters such as pipes, line feeds, or carriage returns in values rendered inside Markdown table cells
- **THEN** generated `environments/astra/generated/docs/services.md` SHALL keep each logical record within its intended table row and column structure
- **AND** the renderer SHALL escape or normalize those values at the Markdown table boundary
- **AND** optional omitted display values SHALL continue to render with the existing placeholder behavior

#### Scenario: Generated service documentation is stale
- **WHEN** service metadata changes without regenerating committed service documentation
- **THEN** the generated-output check SHALL fail
- **AND** it SHALL report the stale Astra service documentation artifact

#### Scenario: Generated service documentation remains non-sensitive
- **WHEN** service documentation is generated or checked
- **THEN** the generated output SHALL NOT contain passwords, private keys, API token secrets, password hashes, or other runtime secrets
