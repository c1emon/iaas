## MODIFIED Requirements

### Requirement: Source-of-truth and generated-output map
The operator documentation SHALL identify Astra authored sources, their authority boundaries, and committed generated outputs.

#### Scenario: Operator edits inventory
- **WHEN** an operator wants to change declared infrastructure, service, foundation, or device metadata
- **THEN** the root README SHALL identify the relevant files under `environments/astra/inventory/` and `environments/astra/ansible/`
- **AND** it SHALL identify the PVE cluster and VM inventories as authoritative for PVE topology and VM lifecycle facts
- **AND** it SHALL direct the operator to the existing generation and stale-output check workflows

#### Scenario: Operator reviews generated files
- **WHEN** generated outputs are documented
- **THEN** the root README SHALL identify committed non-sensitive artifacts under `environments/astra/generated/`
- **AND** detailed state, cache, and observation handling SHALL be linked rather than duplicated
