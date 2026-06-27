## ADDED Requirements

### Requirement: PVE inventory validation errors include field context
The system SHALL report expected PVE inventory validation failures with enough source-field context for operators to fix YAML input without reading Python tracebacks.

#### Scenario: VM static IP is malformed
- **WHEN** a VM declaration contains a `static_ip` value that cannot be parsed as an IP interface
- **THEN** offline PVE inventory validation SHALL fail before generation or provisioning
- **AND** it SHALL report the failure as a repository validation error
- **AND** the error message SHALL identify the affected VM and `static_ip` field
- **AND** the failure SHALL NOT require live PVE infrastructure access
