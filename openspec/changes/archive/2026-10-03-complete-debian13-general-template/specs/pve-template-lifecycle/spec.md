## ADDED Requirements

### Requirement: Explicit publication without a NIC
Current publication SHALL accept hardware.bridge null as an explicit no-NIC selection. It SHALL omit net0 at native creation, verify absence of every netN attachment and retain the actual no-NIC configuration in template record. It SHALL NOT require caller-side post-publication removal.

#### Scenario: Publish a general offline template
- **WHEN** hardware.bridge is null and no interface-specific cloud-init default is declared
- **THEN** check/plan/apply SHALL preserve that selection and successful publication SHALL create and verify a template with no NIC

#### Scenario: Conflicting or unexpected networking
- **WHEN** a no-NIC request includes cloud_init_defaults.ip_config or the observed template has any netN
- **THEN** the dependent check or publication verification SHALL fail with a network field/reason
- **AND** missing or empty bridge SHALL NOT be silently treated as null
