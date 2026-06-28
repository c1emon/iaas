# python-common-primitives Specification

## Purpose
Define an explicit Python common primitive layer for domain-neutral helper code
shared across repository-owned inventory tooling without coupling domain packages
to each other.

## Requirements
### Requirement: Explicit common primitive package
The system SHALL provide an explicit Python common primitive package for helper code that is shared across repository-owned inventory tooling.

#### Scenario: Inventory tools use shared primitive helpers
- **WHEN** PVE inventory or service metadata code needs shared validation errors, assertion helpers, basic YAML/JSON/text I/O, CLI validation failure handling, generated-output content comparison, or Markdown table-cell escaping
- **THEN** those shared helpers SHALL be available from a `scripts.common` package or equivalent explicit common primitive layer
- **AND** callers SHALL NOT need to import domain-neutral helpers through `scripts.pve_inventory` or `scripts.services_inventory` packages

#### Scenario: Common helpers remain domain-neutral
- **WHEN** helper code is added to the common primitive layer
- **THEN** it SHALL be limited to domain-neutral primitives such as errors, basic type/schema assertions, file I/O, CLI boundary helpers, or Markdown table-cell escaping
- **AND** it SHALL NOT encode PVE cluster policy, VM schema policy, service endpoint policy, OPNsense policy, OpenTofu resource shape, Ansible inventory domain rules, cloud-init artifact rules, or online runtime adapter behavior

### Requirement: Dependency direction remains acyclic and domain-safe
The system SHALL keep inventory domain packages dependent on common primitives rather than on each other for shared helper behavior.

#### Scenario: Services inventory no longer imports PVE internals
- **WHEN** service metadata validation, rendering, I/O, or CLI code uses shared helper behavior
- **THEN** it SHALL import that helper behavior from the common primitive layer
- **AND** it SHALL NOT import `scripts.pve_inventory.errors`, `scripts.pve_inventory.validation_common`, `scripts.pve_inventory.io`, or other PVE inventory internals for domain-neutral helper behavior

#### Scenario: Common primitives avoid domain imports
- **WHEN** Python imports for the common primitive layer are evaluated
- **THEN** common primitive modules SHALL NOT import from `scripts.pve_inventory` or `scripts.services_inventory`
- **AND** common primitive modules SHALL be reusable by both PVE inventory and service metadata tooling without creating import cycles

### Requirement: Refactor preserves inventory tool behavior
The system SHALL preserve existing operator-visible behavior while moving primitive helper ownership.

#### Scenario: Existing offline checks remain safe
- **WHEN** operators or CI run the repository's default offline validation path after the primitive extraction
- **THEN** it SHALL remain offline-safe
- **AND** it SHALL NOT require PVE API access, OPNsense API access, switch access, SSH access, 1Password access, runtime secrets, or mutation-capable infrastructure credentials

#### Scenario: Generated outputs remain stable
- **WHEN** source-of-truth inventory files are unchanged and generated-output checks are run after the primitive extraction
- **THEN** generated PVE outputs and generated service documentation SHALL remain unchanged except for explicitly documented intentional changes
- **AND** stale or missing generated outputs SHALL continue to be reported with actionable file paths

#### Scenario: CLI validation failures remain operator-readable
- **WHEN** PVE inventory or services inventory CLI commands fail due to expected validation errors after the primitive extraction
- **THEN** they SHALL exit with status `1`
- **AND** they SHALL print a concise validation failure to stderr with the existing `FAIL validation: ` prefix
- **AND** they SHALL NOT print a Python traceback for expected validation failures
- **AND** they SHALL NOT disclose runtime secrets or credential material
