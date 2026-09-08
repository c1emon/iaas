## MODIFIED Requirements

### Requirement: Source-of-truth and generated-output map
The operator documentation SHALL identify explicitly selected environment sources, their authority boundaries, and committed generated outputs.

#### Scenario: Operator edits inventory
- **WHEN** an operator wants to change declared infrastructure, service, foundation, or device metadata
- **THEN** the root README SHALL identify the generic environment directory contract and its `inventory/` and `ansible/` inputs through the canonical operator documentation
- **AND** it SHALL identify the PVE cluster and VM inventories as authoritative for PVE topology and VM lifecycle facts
- **AND** it SHALL direct the operator to the existing generation and stale-output check workflows

#### Scenario: Operator reviews generated files
- **WHEN** generated outputs are documented
- **THEN** the root README SHALL identify the selected generated-output directory and which non-sensitive artifacts an environment repository may commit
- **AND** detailed state, cache, and observation handling SHALL be linked rather than duplicated

#### Scenario: Operator migrates an environment-specific invocation
- **WHEN** a supported runtime example previously relied on an Astra selector or default path
- **THEN** current documentation SHALL show the generic explicit environment/output inputs and changed helper names
- **AND** actual environment data and execution records SHALL be maintained by callers outside the runtime repository
- **AND** host helper migration SHALL retain its explicit online authorization boundary
