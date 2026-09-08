## MODIFIED Requirements

### Requirement: Service metadata source of truth
The system SHALL support operator-authored service metadata from the explicitly selected environment's `inventory/services.yml` or explicit equivalent file.

#### Scenario: Operator declares a service owned by a PVE VM
- **WHEN** an operator declares a service in the selected service inventory
- **THEN** the declaration SHALL include a unique service name
- **AND** it SHALL include an `owner_vm` that references a VM declared in the explicitly selected VM inventory for the same environment
- **AND** it SHALL include one or more service endpoints
- **AND** it MAY include an operator-readable description

#### Scenario: Service metadata references an unknown VM
- **WHEN** a service declaration references an `owner_vm` that is not declared in the selected environment's VM inventory
- **THEN** service inventory validation SHALL fail before generated service documentation is accepted
- **AND** the failure SHALL identify the invalid service and missing VM reference

### Requirement: Generated service documentation
The system SHALL generate committed, non-sensitive service documentation from the selected environment's service metadata.

#### Scenario: Operator regenerates service documentation
- **WHEN** an operator runs the repository generation workflow
- **THEN** the system SHALL generate `docs/services.md` beneath the selected generated-output directory from the explicitly selected service and VM inventories
- **AND** the generated document SHALL include service names, owner VMs, endpoint details, exposure, auth, FQDNs when present, review hints when present, and warning records

#### Scenario: Generated service documentation escapes table cells
- **WHEN** service metadata or warning records contain Markdown table metacharacters such as pipes, line feeds, or carriage returns in values rendered inside Markdown table cells
- **THEN** the generated service document SHALL keep each logical record within its intended table row and column structure
- **AND** the renderer SHALL escape or normalize those values at the Markdown table boundary
- **AND** optional omitted display values SHALL continue to render with the existing placeholder behavior

#### Scenario: Generated service documentation is stale
- **WHEN** service metadata changes without regenerating committed service documentation
- **THEN** the generated-output check SHALL fail
- **AND** it SHALL report the stale environment-specific service documentation artifact

#### Scenario: Generated service documentation remains non-sensitive
- **WHEN** service documentation is generated or checked
- **THEN** the generated output SHALL NOT contain passwords, private keys, API token secrets, password hashes, or other runtime secrets

#### Scenario: Generated document describes its input
- **WHEN** service documentation identifies its source
- **THEN** it SHALL describe the selected logical inputs without a hard-coded Astra path or host-specific absolute path
