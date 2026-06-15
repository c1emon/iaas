## ADDED Requirements

### Requirement: Collection-native switch state schema
The system SHALL use `c1emon.xikeos` collection-native facts as the canonical switch state schema for XikeOS workflows.

#### Scenario: Expose native Ansible facts
- **WHEN** the read-only switch facts workflow completes successfully
- **THEN** the resulting structured state SHALL expose collection-provided `ansible_net_*` facts
- **AND** it SHALL expose collection-provided `ansible_network_resources` as the authoritative resource state

#### Scenario: Avoid repository-specific fact adaptation
- **WHEN** collection-native facts are available from `c1emon.xikeos.xikeos_facts`
- **THEN** the workflow SHALL NOT transform them into the former repository-specific `switch_facts` schema as the primary output
- **AND** downstream switch workflows SHALL consume `ansible_network_resources` directly

### Requirement: Native resource coverage baseline
The system SHALL treat lifecycle-complete `c1emon.xikeos` resource modules as the supported resource coverage baseline for switch configuration workflows.

#### Scenario: Support lifecycle-complete resources
- **WHEN** an operator declares switch configuration intent for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG interfaces, static routes, or ACLs
- **THEN** the configuration workflow SHALL map that intent to the corresponding lifecycle-complete `c1emon.xikeos` resource module
- **AND** planning, apply, and verification SHALL use collection-native resource state or module results

#### Scenario: Reject rendered-only resources for apply
- **WHEN** an operator declares intent for a XikeOS feature whose collection module is rendered-only in v0.2.x
- **THEN** the configuration workflow SHALL NOT treat that feature as lifecycle-apply supported
- **AND** it SHALL fail clearly or route it to a separately documented fallback path

### Requirement: Collection version baseline
The system SHALL use `c1emon.xikeos` v0.2.x as the collection capability baseline for native facts and lifecycle resources.

#### Scenario: Install expected collection capability set
- **WHEN** an operator installs repository Ansible collection requirements
- **THEN** the installed `c1emon.xikeos` version SHALL satisfy the v0.2.x baseline required for `xikeos_facts`, `ansible_network_resources`, and lifecycle resource states
- **AND** repository documentation SHALL identify Python parser runtime dependencies required by collection facts and resource modules
