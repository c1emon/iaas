## MODIFIED Requirements

### Requirement: Root offline validation command surface
The system SHALL expose root-level commands for routine offline validation that can be run by both local operators and CI.

#### Scenario: Run the aggregate offline gate
- **WHEN** an operator or CI runs the root aggregate check command
- **THEN** the system SHALL run only offline-safe validation targets
- **AND** it SHALL include stale generated output detection for PVE outputs and service metadata documentation
- **AND** it SHALL include relevant Python tests for PVE inventory validation and service Markdown rendering hardening
- **AND** it SHALL include YAML linting for source-of-truth files
- **AND** it SHALL include OpenTofu formatting and offline validation where practical
- **AND** it SHALL NOT perform online infrastructure access or mutation

### Requirement: Validation CLI failures are operator-readable
The system SHALL convert expected repository validation failures at CLI boundaries into stable operator-readable errors.

#### Scenario: PVE inventory CLI receives invalid operator-authored input
- **WHEN** a PVE inventory CLI command fails because source-of-truth input is invalid, including hardened identifier or static IP validation failures
- **THEN** the command SHALL exit with status `1`
- **AND** it SHALL print a concise validation failure message to stderr
- **AND** it SHALL identify enough source-field context for operator correction
- **AND** it SHALL NOT print a Python traceback for that expected validation failure
- **AND** it SHALL NOT disclose runtime secrets or credential material

#### Scenario: Services inventory CLI receives invalid operator-authored input
- **WHEN** a services inventory CLI command fails because source-of-truth input is invalid
- **THEN** the command SHALL exit with status `1`
- **AND** it SHALL print a concise validation failure message to stderr
- **AND** it SHALL NOT print a Python traceback for that expected validation failure
- **AND** it SHALL NOT disclose runtime secrets or credential material
