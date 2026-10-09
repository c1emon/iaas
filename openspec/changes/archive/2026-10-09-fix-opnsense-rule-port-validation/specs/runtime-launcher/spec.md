## ADDED Requirements

### Requirement: Safe public error and warning continuity
The runtime and launcher SHALL preserve critical error and warning information across protected Ansible tasks, subprocess capture, runtime public JSON and final terminal output without printing credentials, raw configuration, provider responses or uncontrolled exception text. Public messages SHALL be reconstructed from a fixed catalog with bounded approved fields.

#### Scenario: Protected task fails
- **WHEN** a no_log task fails or is unreachable
- **THEN** public output SHALL retain error classification and safe task metadata
- **AND** recognized static assertion gates SHALL retain their value-free reason
- **AND** warning presence/count SHALL remain visible while warning text stays protected

#### Scenario: Provider returns a recognized API failure
- **WHEN** an OPNsense save or activation returns field validation, authentication, permission or timeout evidence
- **THEN** the task SHALL sanitize that evidence before publishing it
- **AND** runtime and launcher SHALL display the approved field, reason and HTTP code when available
- **AND** no_log SHALL NOT be bypassed to access hidden callback payloads

#### Scenario: Runtime protects raw subprocess output
- **WHEN** a child process fails
- **THEN** runtime JSON and launcher terminal output SHALL retain the phase and exit status plus approved diagnostics
- **AND** incomplete capture and process-start failure SHALL remain explicit failures
- **AND** unknown diagnostics SHALL NOT be replaced by raw stdout/stderr

#### Scenario: Successful operation has warnings
- **WHEN** an operation succeeds but carries protected warnings or the native OPNsense evidence limitation
- **THEN** runtime JSON and launcher terminal output SHALL preserve the warning

#### Scenario: Malicious or unrecognized diagnostic text
- **WHEN** captured output or runtime diagnostics contain arbitrary code, message or field values
- **THEN** only known codes and approved fields SHALL be published with cataloged messages
- **AND** diagnostic lists and capture scanning SHALL remain bounded
