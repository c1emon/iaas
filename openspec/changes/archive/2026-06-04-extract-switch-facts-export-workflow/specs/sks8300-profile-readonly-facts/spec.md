## MODIFIED Requirements

### Requirement: Command-level raw export policy
The system SHALL decide raw output export eligibility and redaction using command-level policy from the SKS8300 profile, and SHALL expose that policy as export-plan data for caller-owned export workflows.

#### Scenario: Export non-sensitive raw command output
- **WHEN** raw output export is enabled by a caller-owned export workflow and a planned command is non-sensitive with raw export allowed
- **THEN** the profile-generated export plan SHALL include that command output with the command ID or documented filename mapping
- **AND** the caller-owned export workflow MAY write that planned item to the raw output directory

#### Scenario: Redact sensitive running configuration output
- **WHEN** raw output export is enabled by a caller-owned export workflow and the planned command is `show_running_config`
- **THEN** the profile-generated export plan SHALL provide only redacted running configuration output for that item
- **AND** it SHALL NOT expose plaintext management secrets as a file-safe export item

#### Scenario: Summarize command plan and collection
- **WHEN** raw output export is enabled by a caller-owned export workflow
- **THEN** the export workflow SHALL be able to summarize transport, terminal adapter, planned command IDs, collected result count, and normalized output lengths from role output variables
