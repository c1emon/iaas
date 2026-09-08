## MODIFIED Requirements

### Requirement: Repository layers express ownership
The repository SHALL separate named environment configuration, reusable
automation, and the external platform-repository handoff boundary into explicit
ownership layers. Generic execution SHALL select an environment explicitly.

#### Scenario: Operator locates Astra environment data
- **WHEN** an operator reviews Astra inventory, Ansible data, runtime templates, generated deployment inputs, or the Astra OpenTofu root
- **THEN** existing tracked Astra artifacts SHALL remain under `environments/astra/` as environment-owned data, without making that directory an implicit runtime input

#### Scenario: Developer locates reusable automation
- **WHEN** a developer changes Python automation, reusable Ansible workflows, OpenTofu modules, Packer mechanisms, or PVE-node automation
- **THEN** those implementations SHALL be located under `automation/`
- **AND** concrete Astra PVE topology and VM declarations SHALL remain outside reusable automation

#### Scenario: Operator supplies an independent environment repository
- **WHEN** an operator selects a local or external environment directory explicitly
- **THEN** reusable automation SHALL consume that environment through the same generic path interface
- **AND** environment-specific inventories, policy and OpenTofu roots SHALL remain owned by that environment
- **AND** this change SHALL NOT require migration or deletion of existing real environment data

### Requirement: PVE and VM inventories are authoritative
The repository SHALL use the explicitly selected environment's PVE cluster and VM inventories as the authoritative declarations for PVE topology and VM lifecycle facts.

#### Scenario: PVE or VM facts are consumed
- **WHEN** validation, rendering, health expectations, preflight expectations, or deployment inputs require PVE topology or VM lifecycle facts
- **THEN** they SHALL derive those facts from the selected environment's `inventory/pve-cluster.yml` and `inventory/vms.yml`, or explicitly supplied equivalent input files
- **AND** reusable validation, rendering, and expectation code SHALL NOT require matching concrete Astra constants
- **AND** existing host-side wrapper protection envelopes MAY remain independent safety limits

#### Scenario: Invalid inventory relationships are declared
- **WHEN** inventory contains malformed, duplicate, unknown, contradictory, unsafe, or out-of-range relationships
- **THEN** validation SHALL fail before generation, online access, planning, or mutation
- **AND** structural, reference, network, provider-limit, lifecycle, and secret-safety checks SHALL remain in force

#### Scenario: Other environment data is authored
- **WHEN** service, foundation, Ansible, OPNsense, or switch data is not a PVE topology or VM lifecycle fact
- **THEN** it MAY remain authored in its existing domain-specific environment file
- **AND** this change SHALL NOT require every repeated repository value to be generated from one global source
