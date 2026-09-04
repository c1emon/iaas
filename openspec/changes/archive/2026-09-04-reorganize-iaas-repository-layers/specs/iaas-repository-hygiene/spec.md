## MODIFIED Requirements

### Requirement: Human architecture documentation follows source-of-truth facts
Current human-maintained architecture documentation SHALL not contradict Astra's authoritative authored facts.

#### Scenario: PVE node facts are documented
- **WHEN** current architecture documentation states concrete PVE node facts such as node names, management addresses, or roles
- **THEN** those facts SHALL match `environments/astra/inventory/pve-cluster.yml` or be explicitly marked historical/uncertain
- **AND** current documentation SHALL be corrected when it conflicts with Astra inventory

#### Scenario: Historical documentation records an old path or fact
- **WHEN** an immutable OpenSpec archive or prominently labeled historical decision records its original context
- **THEN** it MAY retain old paths or superseded facts as historical evidence
- **AND** it SHALL NOT be presented as the current operator source of truth
