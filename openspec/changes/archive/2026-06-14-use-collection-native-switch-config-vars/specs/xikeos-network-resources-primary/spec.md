## MODIFIED Requirements

### Requirement: Native resource coverage baseline
The system SHALL treat lifecycle-complete `c1emon.xikeos` resource modules as the supported resource coverage baseline for switch configuration workflows and SHALL use their native module schemas as the repository configuration input contract.

#### Scenario: Support lifecycle-complete resources
- **WHEN** an operator declares switch configuration for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG interfaces, static routes, or ACLs
- **THEN** the configuration workflow SHALL route each declaration to the corresponding lifecycle-complete `c1emon.xikeos` resource module
- **AND** the declaration SHALL use that module's collection-native `state` and `config` schema
- **AND** planning, apply, and verification SHALL use collection module results rather than repository-local resource definitions

#### Scenario: Reject rendered-only resources for apply
- **WHEN** an operator declares configuration for a XikeOS feature whose collection module is rendered-only in v0.2.x
- **THEN** the configuration workflow SHALL NOT include that feature in the supported collection-native switch configuration resource set
- **AND** any such feature SHALL require a separately documented fallback workflow or future lifecycle-complete collection module support
