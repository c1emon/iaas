## MODIFIED Requirements

### Requirement: Explicit common primitive package
The system SHALL provide an explicit Python common primitive package for helper code that is shared across repository-owned inventory tooling.

#### Scenario: Inventory tools use shared primitive helpers
- **WHEN** PVE inventory or service metadata code needs shared validation errors, assertion helpers, basic YAML/JSON/text I/O, CLI validation failure handling, generated-output content comparison, or Markdown table-cell escaping
- **THEN** those shared helpers SHALL be available from `iaas_automation.common`
- **AND** callers SHALL NOT need to import domain-neutral helpers through `iaas_automation.pve_inventory` or `iaas_automation.services_inventory`

#### Scenario: Common helpers remain domain-neutral
- **WHEN** helper code is added to the common primitive layer
- **THEN** it SHALL be limited to domain-neutral primitives such as errors, basic type/schema assertions, file I/O, CLI boundary helpers, or Markdown table-cell escaping
- **AND** it SHALL NOT encode PVE cluster policy, VM schema policy, service endpoint policy, OPNsense policy, OpenTofu resource shape, Ansible inventory domain rules, cloud-init artifact rules, or online runtime adapter behavior

### Requirement: Dependency direction remains acyclic and domain-safe
The system SHALL keep inventory domain packages dependent on common primitives rather than on each other for shared helper behavior.

#### Scenario: Services inventory no longer imports PVE internals
- **WHEN** service metadata validation, rendering, I/O, or CLI code uses shared helper behavior
- **THEN** it SHALL import that helper behavior from `iaas_automation.common`
- **AND** it SHALL NOT import PVE inventory internals for domain-neutral helper behavior

#### Scenario: Common primitives avoid domain imports
- **WHEN** Python imports for the common primitive layer are evaluated
- **THEN** `iaas_automation.common` SHALL NOT import from `iaas_automation.pve_inventory` or `iaas_automation.services_inventory`
- **AND** common primitive modules SHALL be reusable by both domains without creating import cycles
