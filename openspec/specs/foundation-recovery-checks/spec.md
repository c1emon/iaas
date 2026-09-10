# foundation-recovery-checks Specification

## Purpose
Define the foundation recovery inventory, generated recovery reference, offline
validation, explicit online health checks, and storage-network fact validation
needed before K3s platform recovery and storage PoCs.

## Requirements

### Requirement: Foundation recovery inventory
The system SHALL support an operator-authored foundation recovery inventory for cluster-external foundation hosts and services.

#### Scenario: Operator declares foundation hosts
- **WHEN** an operator declares foundation hosts in the foundation recovery inventory
- **THEN** each host SHALL have a unique name
- **AND** each host SHALL declare its role-relevant management identity or address
- **AND** each host SHALL declare whether it is a bare-metal host, VM, appliance, or external dependency

#### Scenario: Operator declares foundation services
- **WHEN** an operator declares foundation services in the foundation recovery inventory
- **THEN** each service SHALL have a unique name
- **AND** each service SHALL reference a declared foundation host or explicitly mark itself as an external dependency
- **AND** each service SHALL declare its runtime category such as `compose`, `systemd`, `appliance`, `external`, or `unknown`
- **AND** each service SHALL declare whether it is required before K3s recovery

#### Scenario: Inventory references secret material
- **WHEN** a foundation service needs credentials, API keys, tokens, or certificate private keys
- **THEN** the inventory SHALL represent those values as external secret references
- **AND** the inventory SHALL NOT contain decrypted secret values

### Requirement: Foundation recovery metadata validation
The system SHALL validate foundation recovery metadata before generated recovery documentation is accepted.

#### Scenario: Service dependency references another service
- **WHEN** a foundation service declares dependencies
- **THEN** each dependency SHALL reference a declared foundation service or declared external dependency
- **AND** validation SHALL fail if the dependency reference cannot be resolved

#### Scenario: Required startup service declares restore order
- **WHEN** a foundation service is marked as required before K3s recovery
- **THEN** the service SHALL declare a restore order value
- **AND** validation SHALL fail if two required startup services declare the same restore order value
- **AND** generated documentation SHALL present required startup services in restore order

#### Scenario: Service is recovery-critical
- **WHEN** a foundation service is marked as critical or required before K3s recovery
- **THEN** it SHALL declare a health check
- **AND** it SHALL declare backup or restore metadata
- **AND** it SHALL declare break-glass access metadata when an operator login path exists

#### Scenario: Known single point of failure is accepted
- **WHEN** a foundation host or service is a known single point of failure
- **THEN** the inventory SHALL allow that risk to be recorded explicitly
- **AND** generated documentation SHALL surface the accepted risk for operator review

### Requirement: Generated foundation recovery documentation
The system SHALL generate committed, non-sensitive foundation recovery documentation from the selected environment's foundation recovery inventory.

#### Scenario: Operator regenerates foundation recovery documentation
- **WHEN** an operator runs the foundation recovery documentation generation command
- **THEN** the system SHALL generate `docs/foundation-recovery.md` beneath the explicitly selected generated-output directory
- **AND** the generated document SHALL include the minimum startup set, recovery order, foundation hosts, foundation services, dependencies, health checks, backup/restore metadata, break-glass metadata, storage-network facts, and warnings

#### Scenario: Generated foundation recovery documentation is stale
- **WHEN** the selected foundation inventory changes without regenerating committed recovery documentation
- **THEN** the generated-output check SHALL fail
- **AND** it SHALL report the stale environment-specific artifact

#### Scenario: Generated foundation recovery documentation remains non-sensitive
- **WHEN** foundation recovery documentation is generated or checked
- **THEN** the generated output SHALL NOT contain passwords, private keys, API token secrets, password hashes, or other decrypted credential material
- **AND** external secret references MAY be rendered if they are reference identifiers rather than secret values

#### Scenario: Generated document describes its input
- **WHEN** foundation documentation identifies its source
- **THEN** it SHALL describe the selected logical input without a hard-coded Astra path or host-specific absolute path

### Requirement: Offline foundation checks
The system SHALL provide offline foundation validation and generated-output checks that do not require internal infrastructure access.

#### Scenario: Operator runs offline foundation checks
- **WHEN** an operator runs the offline foundation check command
- **THEN** the system SHALL validate the foundation recovery inventory schema, references, restore-order consistency, generated documentation freshness, and non-sensitive output rules
- **AND** it SHALL validate storage-network fact consistency declared in the inventory
- **AND** it SHALL NOT contact or mutate OPNsense, TrueNAS, DNS, Harbor, Authentik, sing-box, databases, switches, PVE, Docker hosts, or K3s nodes

#### Scenario: Cloud CI runs default offline validation
- **WHEN** cloud CI or a disconnected workstation runs default offline validation
- **THEN** foundation offline checks SHALL be able to run without OPNsense, TrueNAS, DNS, Harbor, Authentik, sing-box, database, switch, PVE, SSH, 1Password, or K3s credentials
- **AND** those checks SHALL NOT require live network routes to internal infrastructure

### Requirement: Explicit online foundation health checks
The system SHALL provide explicit read-only online health checks for declared foundation services.

#### Scenario: Operator requests foundation health checks
- **WHEN** an operator runs the explicit foundation health check command
- **THEN** the system SHALL evaluate declared service-level health checks such as TCP connect, HTTP/HTTPS health endpoint, DNS query, or read-only API status
- **AND** it SHALL report health status by foundation service
- **AND** it SHALL distinguish unreachable, failed, skipped, and passed checks

#### Scenario: Foundation health check command runs
- **WHEN** foundation health checks execute
- **THEN** they SHALL NOT deploy, restart, upgrade, restore, reconfigure, or delete any service
- **AND** they SHALL NOT create, update, or delete OPNsense, TrueNAS, DNS, Harbor, Authentik, sing-box, database, switch, PVE, Docker, systemd, or K3s state

#### Scenario: Foundation health checks require runtime context
- **WHEN** documentation or command help describes foundation health checks
- **THEN** it SHALL state that these checks are online read-only operations
- **AND** it SHALL distinguish them from offline-safe validation that can run without internal network access

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
