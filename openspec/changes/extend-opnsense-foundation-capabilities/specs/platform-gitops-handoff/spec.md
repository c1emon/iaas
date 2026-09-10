## ADDED Requirements

### Requirement: Address-correct endpoint identity verification
Handoff TLS verification SHALL distinguish DNS names from IPv4 and IPv6 literals while preserving authoritative CA trust and whole-scope readiness checks.

#### Scenario: Endpoint is an IP literal
- **WHEN** the declared endpoint is IPv4 or IPv6
- **THEN** verification SHALL validate the certificate IP SAN rather than a DNS hostname
- **AND** IPv6 host-and-port arguments SHALL use brackets

#### Scenario: Endpoint is a DNS name
- **WHEN** the declared endpoint is a DNS name
- **THEN** verification SHALL validate its DNS identity
- **AND** an incorrect identity or CA SHALL fail before writing the handoff bundle
