## ADDED Requirements

### Requirement: PVE failures carry stable internal diagnostics
Repository-owned PVE API exceptions SHALL expose a stable safe reason description for authentication, optional endpoint absence, service unavailability and other API failure while preserving their existing inheritance and status-code interface. Diagnostic adoption SHALL not change preflight/health pass, warning, failure or skip policy.

#### Scenario: Optional PVE endpoint is absent
- **WHEN** the facade maps an absent optional endpoint to its existing not-configured exception
- **THEN** that exception also carries a controlled endpoint-unavailable reason
- **AND** each calling check retains its existing skip, warning or failure decision

#### Scenario: Secret appears in an SDK exception
- **WHEN** a backend exception includes token material or response body text
- **THEN** structured diagnostic fields omit it and the existing operator message remains redacted
- **AND** no new backend detail is exposed by serialization
