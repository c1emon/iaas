## MODIFIED Requirements

### Requirement: Storage-network fact validation
The system SHALL support optional, application-neutral storage facts in foundation schema version 2 while preserving explicitly documented legacy schema version 1 field layout and storage scope. Dependency correctness and probe-safety requirements SHALL apply to both versions.

#### Scenario: Foundation inventory has no storage policy
- **WHEN** a schema version 2 inventory declares hosts and services without storage networks or access policy
- **THEN** validation and recovery rendering SHALL succeed without requiring TrueNAS, K3s or a fixed deployment phase

#### Scenario: Operator declares storage network facts
- **WHEN** schema version 2 includes storage networks
- **THEN** each declared network SHALL carry `name`, `subnet` and a neutral `endpoint` IP address within that subnet, with optional `vlan_id` and `notes`
- **AND** a provided VLAN ID SHALL be an integer in 1..4094; duplicate names and unknown fields SHALL fail validation
- **AND** optional storage access SHALL describe caller-selected node classes and network references without forcing VM-only access or all-network selection
- **AND** `storage_access` SHALL contain `node_classes` (`vm` and/or `bare-metal`), `storage_networks` referencing declared networks and optional `notes`, rejecting duplicates and unknown fields

#### Scenario: Operator declares K3s storage access scope
- **WHEN** schema version 2 declares storage access for K3s
- **THEN** the inventory SHALL preserve the caller's explicit node classes and referenced network subset without imposing a fixed deployment phase
- **AND** schema version 1 SHALL retain its documented legacy scope through the compatibility adapter

#### Scenario: Storage-network facts conflict
- **WHEN** declared network facts omit required endpoint data or conflict with their subnet or access references
- **THEN** offline validation SHALL fail with the inconsistent field identified

#### Scenario: Legacy inventory is supplied
- **WHEN** the caller supplies schema version 1
- **THEN** the runtime SHALL preserve its field layout and storage scope through a documented compatibility path
- **AND** compatibility SHALL NOT preserve accepted dependency cycles, missing explicit DNS resolvers or unverified HTTPS
- **AND** migration to schema version 2 SHALL be explicit without automatically rewriting caller files

#### Scenario: Storage-network validation runs
- **WHEN** validation or rendering processes storage facts
- **THEN** it SHALL NOT configure switches, firewalls, host routes, K3s or storage services
- **AND** generated sections SHALL reflect only declared facts

## ADDED Requirements

### Requirement: Dependency-consistent recovery metadata
Foundation recovery validation SHALL reject impossible dependencies and preserve a deterministic dependency-consistent required startup order.

#### Scenario: Dependency graph is invalid
- **WHEN** a service references itself, creates a cycle, uses an unresolved or ambiguous reference, or declares a restore order less than or equal to its dependency's declared order
- **THEN** validation SHALL fail before generating accepted recovery documentation

#### Scenario: Required startup set omits a prerequisite
- **WHEN** a required-before-K3s service depends on another declared service that is not in the required startup set
- **THEN** validation SHALL fail and require an explicit consistent declaration
- **AND** explicitly declared external dependency hosts SHALL remain leaves rather than invented services

#### Scenario: Valid dependency order is rendered
- **WHEN** required services have unique explicit order values consistent with their dependency graph
- **THEN** output SHALL be deterministic independently of YAML item order
- **AND** accepted single-point-of-failure and recovery metadata SHALL remain visible

### Requirement: Trustworthy bounded foundation probes
Foundation probes SHALL verify declared endpoint identity and parse supported responses within finite bounds without selecting an implicit public dependency.

#### Scenario: HTTPS identity is invalid
- **WHEN** certificate or hostname validation fails using system trust or the caller's explicit CA
- **THEN** the probe SHALL report failure rather than pass an unverified connection

#### Scenario: A private CA is selected
- **WHEN** the caller supplies `health_check.ca_file` for an HTTPS endpoint, including a generic API probe using HTTPS
- **THEN** a relative path SHALL resolve against the selected inventory's directory and the probe SHALL use that CA for certificate and hostname verification
- **AND** validation SHALL reject this field on non-HTTPS probes and SHALL NOT silently fall back to unverified TLS when CA loading fails

#### Scenario: DNS resolver is omitted
- **WHEN** a DNS health declaration has no explicit resolver
- **THEN** validation SHALL fail before sending a query
- **AND** the runtime SHALL NOT default to a public resolver

#### Scenario: Supported DNS record is returned
- **WHEN** a response contains the requested A, AAAA, CNAME, TXT, SRV or ANY data
- **THEN** the probe SHALL parse and evaluate the declared expected-answer semantics accurately
- **AND** it SHALL validate response source, transaction identity and question correspondence

#### Scenario: DNS packet is malformed
- **WHEN** a response has an invalid offset, truncation, cyclic compression pointer or unsupported shape
- **THEN** parsing SHALL terminate within bounded work and classify failure
- **AND** remaining service probes SHALL still be evaluated

#### Scenario: Probe output is recorded
- **WHEN** any probe succeeds or fails
- **THEN** console results SHALL identify the service and outcome without exposing URL credentials, query secrets or raw sensitive responses
