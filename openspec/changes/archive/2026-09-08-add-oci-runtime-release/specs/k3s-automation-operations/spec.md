## MODIFIED Requirements

### Requirement: Composed K3s intent and VM facts
The system SHALL require an explicit K3s intent document and an explicit
generated Ansible inventory for every operator workflow, and SHALL treat the
inventory as the source of VM-owned host and network facts.

Every online workflow SHALL additionally require an explicit non-empty scope
containing only nodes declared by the composed cluster model.

#### Scenario: Operator validates a cluster definition
- **WHEN** an operator provides K3s intent and a generated Ansible inventory
- **THEN** the system SHALL resolve every declared VM reference to exactly one inventory host
- **AND** it SHALL derive CPU architecture and SSH address from generated host facts, and derive node IP, prefix, and NIC network from the unique `pve_nics` entry matching the cluster-wide node-network role
- **AND** it SHALL reject unknown or duplicate host references and missing, ambiguous, or unusable node-network-role NIC facts

#### Scenario: K3s intent duplicates a VM fact
- **WHEN** K3s intent supplies a per-node IP address, interface, NIC-role override, architecture, SSH setting, VM resource, template, placement, gateway, DNS, or another VM-owned fact instead of referencing the generated inventory
- **THEN** validation SHALL fail rather than create a second source of truth

#### Scenario: No environment is selected
- **WHEN** an operator does not provide the required K3s intent or inventory
- **THEN** the system SHALL fail before contacting any host
- **AND** it SHALL NOT silently select the selected environment or an ad-hoc host list

### Requirement: Capability-only acceptance boundary
The system SHALL allow the K3s automation capability to be implemented and
validated without creating a real environment deployment.

#### Scenario: Capability implementation is accepted
- **WHEN** the change is validated without a declared environment K3s cluster
- **THEN** acceptance SHALL use synthetic VM inventory and K3s overlay fixtures, unit tests, Ansible syntax and lint checks, configuration rendering checks, and explicit safety-boundary tests
- **AND** it SHALL NOT require PVE apply, guest mutation, K3s installation, or live cluster access

#### Scenario: No live evidence exists
- **WHEN** only offline or synthetic validation has run
- **THEN** documentation and status reporting SHALL describe the capability as implemented but not deployed or live-qualified
