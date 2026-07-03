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
The system SHALL generate committed, non-sensitive foundation recovery documentation from the foundation recovery inventory.

#### Scenario: Operator regenerates foundation recovery documentation
- **WHEN** an operator runs the foundation recovery documentation generation command
- **THEN** the system SHALL generate a Markdown document under `docs/generated/`
- **AND** the generated document SHALL include the minimum startup set, recovery order, foundation hosts, foundation services, dependencies, health checks, backup/restore metadata, break-glass metadata, storage-network facts, and warnings

#### Scenario: Generated foundation recovery documentation is stale
- **WHEN** the foundation recovery inventory changes without regenerating committed foundation recovery documentation
- **THEN** the generated-output check SHALL fail
- **AND** it SHALL report the stale foundation recovery documentation artifact

#### Scenario: Generated foundation recovery documentation remains non-sensitive
- **WHEN** foundation recovery documentation is generated or checked
- **THEN** the generated output SHALL NOT contain passwords, private keys, API token secrets, password hashes, or other decrypted credential material
- **AND** external secret references MAY be rendered if they are reference identifiers rather than secret values

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
The system SHALL model and validate storage-network facts needed before K3s storage PoCs.

#### Scenario: Operator declares storage network facts
- **WHEN** an operator declares storage-network facts in the foundation recovery inventory
- **THEN** the inventory SHALL identify the storage VLAN or network name
- **AND** it SHALL identify the expected storage subnet or endpoint facts
- **AND** it SHALL identify the TrueNAS storage endpoint used for storage-backed workloads

#### Scenario: Operator declares K3s storage access scope
- **WHEN** the inventory describes future K3s storage access
- **THEN** it SHALL express that only VM-based K3s nodes are intended to access the storage VLAN in the first phase
- **AND** it SHALL NOT require bare-metal K3s nodes to host workloads that need storage VLAN access

#### Scenario: Storage-network facts conflict
- **WHEN** storage-network facts in the foundation inventory are internally inconsistent, missing required endpoint data, or conflict with the declared K3s storage access scope
- **THEN** offline foundation validation SHALL fail
- **AND** the failure SHALL identify the inconsistent storage-network field for operator correction

#### Scenario: Storage-network validation runs
- **WHEN** storage-network validation runs
- **THEN** it SHALL validate declared facts only
- **AND** it SHALL NOT configure VLANs, switch ports, OPNsense interfaces, host routes, K3s nodes, or TrueNAS storage services
